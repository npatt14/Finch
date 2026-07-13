import hashlib
import math

from app.chunking import Chunk
from app.vectorstore import SessionVectorStore, make_qdrant_client


class HashEmbedder:
    dim = 32

    def _vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        raw = [b / 255 for b in h[: self.dim]]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def _chunks():
    return [
        Chunk(text="separate educational facilities are inherently unequal", index=0,
              meta={"citation": "347 U.S. 483", "case_name": "Brown", "position": 0}),
        Chunk(text="the defendant must be informed of the right to remain silent", index=1,
              meta={"citation": "384 U.S. 436", "case_name": "Miranda", "position": 0}),
    ]


def test_index_and_search_roundtrip():
    store = SessionVectorStore(HashEmbedder(), make_qdrant_client("", ""), "sess1")
    n = store.index_chunks(_chunks())
    assert n == 2
    hits = store.search("separate educational facilities are inherently unequal", k=1)
    assert hits and hits[0].meta["citation"] == "347 U.S. 483"


def test_citation_filter_restricts_results():
    store = SessionVectorStore(HashEmbedder(), make_qdrant_client("", ""), "sess2")
    store.index_chunks(_chunks())
    hits = store.search("anything at all", k=5, citation="384 U.S. 436")
    assert hits and all(h.meta["citation"] == "384 U.S. 436" for h in hits)


def test_citation_payload_index_is_created():
    client = make_qdrant_client("", "")
    calls = []
    original = client.create_payload_index

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    client.create_payload_index = spy
    store = SessionVectorStore(HashEmbedder(), client, "idxtest")
    store.index_chunks(_chunks())
    assert any(k.get("field_name") == "citation" for k in calls)


def test_drop_removes_collection():
    client = make_qdrant_client("", "")
    store = SessionVectorStore(HashEmbedder(), client, "sess3")
    store.index_chunks(_chunks())
    store.drop()
    assert not client.collection_exists(store.collection)
