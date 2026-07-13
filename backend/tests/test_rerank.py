import httpx

from app.config import Settings
from app.rerank import VoyageReranker, make_reranker
from app.vectorstore import SessionVectorStore, make_qdrant_client
from tests.test_vectorstore import HashEmbedder, _chunks


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.voyageai.com/v1")


def test_voyage_reranker_parses_and_orders():
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 2, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]})

    rr = VoyageReranker("key", client=_client(handler))
    assert rr.rerank("q", ["a", "b", "c"], top_k=2) == [(2, 0.9), (0, 0.5)]


def test_voyage_reranker_retries_on_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={})
        return httpx.Response(200, json={"data": [{"index": 0, "relevance_score": 1.0}]})

    rr = VoyageReranker("key", client=_client(handler))
    assert rr.rerank("q", ["a"], top_k=1) == [(0, 1.0)]
    assert calls["n"] == 2


def test_reranker_empty_documents_short_circuits():
    def handler(request):
        raise AssertionError("should not call API for empty documents")

    rr = VoyageReranker("key", client=_client(handler))
    assert rr.rerank("q", [], top_k=5) == []


class FakeReranker:
    """Ranks longest document first — deterministic, no network."""

    def rerank(self, query, documents, top_k):
        order = sorted(range(len(documents)), key=lambda i: -len(documents[i]))
        return [(i, 1.0) for i in order[:top_k]]


def test_search_applies_reranker_and_reorders():
    store = SessionVectorStore(HashEmbedder(), make_qdrant_client("", ""), "rr1", reranker=FakeReranker(), candidates=10)
    store.index_chunks(_chunks())
    hits = store.search("anything", k=2)
    assert len(hits) == 2
    assert len(hits[0].text) >= len(hits[1].text)


def test_make_reranker_gated_by_flag():
    assert make_reranker(Settings(voyage_api_key="k", rerank_enabled=False)) is None
    assert make_reranker(Settings(voyage_api_key="k", rerank_enabled=True)) is not None
    assert make_reranker(Settings(voyage_api_key="", rerank_enabled=True)) is None
