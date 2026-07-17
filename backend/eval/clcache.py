from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.models import ExistenceStatus


class CachedCourtListener:
    """Disk-caches CourtListener lookups. CL throttles this token at 100/hour, so the eval
    must never re-fetch what it has already seen. Ambiguous (transient 429) results are not
    cached, and resolve waits out the throttle window rather than letting a burst of 429s
    poison eval items as ambiguous."""

    RESOLVE_RETRIES = 5
    RESOLVE_WAIT_S = 25.0

    def __init__(self, inner, cache_dir: Path):
        self.inner = inner
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, citation: str) -> Path:
        return self.dir / f"res-{hashlib.sha256(citation.encode()).hexdigest()[:20]}.json"

    def resolve(self, citation: str):
        p = self._resolve_path(citation)
        if p.exists():
            ex, cid, url = json.loads(p.read_text())
            return ExistenceStatus(ex), cid, url
        for attempt in range(self.RESOLVE_RETRIES):
            existence, cid, url = self.inner.resolve(citation)
            if existence in (ExistenceStatus.FOUND, ExistenceStatus.NOT_FOUND):
                p.write_text(json.dumps([existence.value, cid, url]))
                return existence, cid, url
            if attempt < self.RESOLVE_RETRIES - 1:
                time.sleep(self.RESOLVE_WAIT_S)
        return existence, cid, url

    def opinion_text(self, cluster_id: int) -> str:
        p = self.dir / f"op-{cluster_id}.txt"
        if p.exists():
            return p.read_text()
        text = self.inner.opinion_text(cluster_id)
        if text:
            p.write_text(text)
        return text

    def case_year(self, cluster_id: int) -> int | None:
        p = self.dir / f"year-{cluster_id}.json"
        if p.exists():
            return json.loads(p.read_text())
        year = self.inner.case_year(cluster_id)
        if year is not None:
            p.write_text(json.dumps(year))
        return year
