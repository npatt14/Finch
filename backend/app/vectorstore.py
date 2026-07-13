from __future__ import annotations

import time
import uuid

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.chunking import Chunk


def make_qdrant_client(url: str, api_key: str) -> QdrantClient:
    if not url:
        return QdrantClient(":memory:")
    return QdrantClient(url=url, api_key=api_key or None)


class VoyageEmbedder:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None, max_retries: int = 6):
        self.model = model
        self.max_retries = max_retries
        self._client = client or httpx.Client(
            base_url="https://api.voyageai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        r = None
        for attempt in range(self.max_retries):
            r = self._client.post(
                "/embeddings", json={"model": self.model, "input": texts, "input_type": input_type}
            )
            if r.status_code == 429 and attempt < self.max_retries - 1:
                retry_after = r.headers.get("retry-after")
                time.sleep(float(retry_after) if retry_after else min(2**attempt, 20))
                continue
            break
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


def make_embedder(settings):
    if settings.voyage_api_key:
        return VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
    raise RuntimeError("no embedding key configured")


class SessionVectorStore:
    def __init__(self, embedder, client: QdrantClient, session_id: str):
        self.embedder = embedder
        self.client = client
        self.collection = f"finch_{session_id}"

    def _ensure(self, dim: int):
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )

    def index_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        vectors = self.embedder.embed_documents([c.text for c in chunks])
        self._ensure(len(vectors[0]))
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": c.text, "index": c.index, **c.meta},
            )
            for c, vec in zip(chunks, vectors)
        ]
        self.client.upsert(self.collection, points)
        return len(points)

    def search(self, query: str, k: int = 5, citation: str | None = None) -> list[Chunk]:
        if not self.client.collection_exists(self.collection):
            return []
        flt = None
        if citation:
            flt = Filter(must=[FieldCondition(key="citation", match=MatchValue(value=citation))])
        hits = self.client.query_points(
            self.collection,
            query=self.embedder.embed_query(query),
            limit=k,
            query_filter=flt,
        ).points
        out = []
        for h in hits:
            p = dict(h.payload or {})
            text = p.pop("text", "")
            index = p.pop("index", 0)
            out.append(Chunk(text=text, index=index, meta=p))
        return out

    def drop(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
