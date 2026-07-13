from __future__ import annotations

import time

import httpx


class VoyageReranker:
    """Cross-encoder reranker. Scores each (query, passage) pair jointly, unlike the bi-encoder
    embedder that scores them independently, so it re-sorts candidates by true relevance."""

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-2.5",
        client: httpx.Client | None = None,
        max_retries: int = 6,
    ):
        self.model = model
        self.max_retries = max_retries
        self._client = client or httpx.Client(
            base_url="https://api.voyageai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )

    def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        r = None
        for attempt in range(self.max_retries):
            r = self._client.post(
                "/rerank",
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_k": min(top_k, len(documents)),
                },
            )
            if r.status_code == 429 and attempt < self.max_retries - 1:
                retry_after = r.headers.get("retry-after")
                time.sleep(float(retry_after) if retry_after else min(2**attempt, 20))
                continue
            break
        r.raise_for_status()
        data = r.json()["data"]
        return [(d["index"], d["relevance_score"]) for d in data]


def make_reranker(settings) -> VoyageReranker | None:
    if settings.rerank_enabled and settings.voyage_api_key:
        return VoyageReranker(settings.voyage_api_key, settings.rerank_model)
    return None
