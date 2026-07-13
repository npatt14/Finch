from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.models import ExistenceStatus


class CachedCourtListener:
    """Disk-caches CourtListener lookups. CL throttles this token at 100/hour, so the eval
    must never re-fetch what it has already seen. Ambiguous (transient 429) results are not cached."""

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
        existence, cid, url = self.inner.resolve(citation)
        if existence in (ExistenceStatus.FOUND, ExistenceStatus.NOT_FOUND):
            p.write_text(json.dumps([existence.value, cid, url]))
        return existence, cid, url

    def opinion_text(self, cluster_id: int) -> str:
        p = self.dir / f"op-{cluster_id}.txt"
        if p.exists():
            return p.read_text()
        text = self.inner.opinion_text(cluster_id)
        if text:
            p.write_text(text)
        return text
