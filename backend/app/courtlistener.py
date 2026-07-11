from __future__ import annotations

import re

import httpx

from app.models import ExistenceStatus

_STATUS_MAP = {200: ExistenceStatus.FOUND, 300: ExistenceStatus.AMBIGUOUS, 404: ExistenceStatus.NOT_FOUND}


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


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

    def resolve(self, citation: str) -> tuple[ExistenceStatus, int | None, str | None]:
        try:
            r = self._client.post(f"{self.base_url}/citation-lookup/", data={"text": citation})
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

    def opinion_text(self, cluster_id: int) -> str:
        try:
            r = self._client.get(f"{self.base_url}/opinions/", params={"cluster": cluster_id})
            r.raise_for_status()
            results = r.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return ""
        for op in results:
            if op.get("plain_text"):
                return op["plain_text"]
        for op in results:
            for field in ("html_with_citations", "html", "html_lawbox", "xml_harvard"):
                if op.get(field):
                    return _strip_html(op[field])
        return ""
