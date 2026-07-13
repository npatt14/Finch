from __future__ import annotations

import hashlib
import json
from pathlib import Path


class CachedEmbedder:
    """Disk-caches embeddings so repeat runs (e.g. retrieval A/B tests) never re-pay Voyage."""

    def __init__(self, inner, cache_dir: Path):
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, text: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(text.encode()).hexdigest()}.json"

    def _get(self, text: str):
        p = self._path(text)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def _put(self, text: str, vec):
        self._path(text).write_text(json.dumps(vec))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list = [None] * len(texts)
        misses, miss_idx = [], []
        for i, t in enumerate(texts):
            v = self._get(t)
            if v is None:
                misses.append(t)
                miss_idx.append(i)
            else:
                out[i] = v
        if misses:
            fresh = self.inner.embed_documents(misses)
            for k, i in enumerate(miss_idx):
                out[i] = fresh[k]
                self._put(misses[k], fresh[k])
        return out

    def embed_query(self, text: str) -> list[float]:
        v = self._get(text)
        if v is None:
            v = self.inner.embed_query(text)
            self._put(text, v)
        return v
