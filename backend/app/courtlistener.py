from __future__ import annotations

import re
import time

import httpx

from app.models import ExistenceStatus

_STATUS_MAP = {200: ExistenceStatus.FOUND, 300: ExistenceStatus.AMBIGUOUS, 404: ExistenceStatus.NOT_FOUND}
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _opinion_body(op: dict) -> str:
    if op.get("plain_text"):
        return op["plain_text"]
    for field in ("html_with_citations", "html", "html_lawbox", "xml_harvard"):
        if op.get(field):
            return _strip_html(op[field])
    return ""


def _backoff_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return min(2**attempt, 8)


class CourtListenerClient:
    def __init__(
        self,
        token: str = "",
        base_url: str = "https://www.courtlistener.com/api/rest/v4",
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Token {token}"} if token else {}
        self._client = client or httpx.Client(headers=headers, timeout=30)

    def _send(self, send):
        r = None
        for attempt in range(_MAX_RETRIES):
            try:
                r = send()
            except httpx.TransportError:
                if attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(_backoff_delay(attempt, None))
                continue
            if r.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                time.sleep(_backoff_delay(attempt, r.headers.get("retry-after")))
                continue
            return r
        return r

    def resolve(self, citation: str) -> tuple[ExistenceStatus, int | None, str | None]:
        try:
            r = self._send(lambda: self._client.post(f"{self.base_url}/citation-lookup/", data={"text": citation}))
            r.raise_for_status()
            items = r.json()
        except (httpx.HTTPError, ValueError):
            return ExistenceStatus.AMBIGUOUS, None, None
        if not items:
            return ExistenceStatus.NOT_FOUND, None, None
        item = items[0]
        status = _STATUS_MAP.get(item.get("status"), ExistenceStatus.AMBIGUOUS)
        clusters = item.get("clusters") or []
        if status == ExistenceStatus.FOUND and clusters:
            c = clusters[0]
            url = c.get("absolute_url") or ""
            full = f"https://www.courtlistener.com{url}" if url.startswith("/") else url
            return status, c.get("id"), full
        if status == ExistenceStatus.FOUND and not clusters:
            return ExistenceStatus.AMBIGUOUS, None, None
        return status, None, None

    def case_year(self, cluster_id: int) -> int | None:
        try:
            r = self._send(lambda: self._client.get(f"{self.base_url}/clusters/{cluster_id}/"))
            r.raise_for_status()
            date_filed = (r.json().get("date_filed") or "")[:4]
        except (httpx.HTTPError, ValueError):
            return None
        return int(date_filed) if date_filed.isdigit() else None

    def opinion_text(self, cluster_id: int) -> str:
        try:
            r = self._send(lambda: self._client.get(f"{self.base_url}/opinions/", params={"cluster": cluster_id}))
            r.raise_for_status()
            results = r.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return ""
        # CourtListener type codes sort by primacy: 010combined < 020lead < 030concurrence < 040dissent
        ranked = sorted(results, key=lambda op: op.get("type") or "999")
        for op in ranked:
            t = op.get("type") or ""
            if t and t < "030":
                body = _opinion_body(op)
                if body:
                    return body
        bodies = [b for b in (_opinion_body(op) for op in ranked) if b]
        return "\n\n".join(bodies)


class CachingCourtListener:
    """Process-lifetime in-memory cache over a CourtListenerClient. CourtListener throttles a
    token at roughly 100 requests per hour, so re-verifying the same citations must not re-spend
    the quota. Only durable answers are cached. Transient failures (AMBIGUOUS, empty opinion,
    missing year) are never cached, so a rate-limited miss is retried on the next run instead of
    being frozen into a wrong verdict."""

    def __init__(self, inner):
        self.inner = inner
        self._resolve_cache: dict[str, tuple[ExistenceStatus, int | None, str | None]] = {}
        self._opinion_cache: dict[int, str] = {}
        self._year_cache: dict[int, int | None] = {}

    def resolve(self, citation: str) -> tuple[ExistenceStatus, int | None, str | None]:
        if citation in self._resolve_cache:
            return self._resolve_cache[citation]
        result = self.inner.resolve(citation)
        if result[0] in (ExistenceStatus.FOUND, ExistenceStatus.NOT_FOUND):
            self._resolve_cache[citation] = result
        return result

    def case_year(self, cluster_id: int) -> int | None:
        if cluster_id in self._year_cache:
            return self._year_cache[cluster_id]
        year = self.inner.case_year(cluster_id)
        if year is not None:
            self._year_cache[cluster_id] = year
        return year

    def opinion_text(self, cluster_id: int) -> str:
        if cluster_id in self._opinion_cache:
            return self._opinion_cache[cluster_id]
        text = self.inner.opinion_text(cluster_id)
        if text:
            self._opinion_cache[cluster_id] = text
        return text
