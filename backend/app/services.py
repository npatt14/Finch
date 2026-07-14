from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from qdrant_client import QdrantClient

from app.config import Settings
from app.courtlistener import CachingCourtListener, CourtListenerClient
from app.escalate import TavilyClient
from app.llm import make_chat_fn, make_extract_fn, make_judge_fn
from app.rerank import make_reranker
from app.vectorstore import SessionVectorStore, make_embedder, make_qdrant_client


@dataclass
class Services:
    settings: Settings
    cl: CourtListenerClient
    tavily: TavilyClient
    llm_extract: Callable[[str], str]
    llm_judge: Callable[[str, str], str]
    llm_chat: Callable[[str, str], str]
    embedder: object
    qdrant: QdrantClient
    reranker: object = None

    def vstore(self, session_id: str) -> SessionVectorStore:
        return SessionVectorStore(
            self.embedder, self.qdrant, session_id, self.reranker, self.settings.retrieval_candidates
        )


def build_services(settings: Settings) -> Services:
    return Services(
        settings=settings,
        cl=CachingCourtListener(CourtListenerClient(token=settings.courtlistener_token)),
        tavily=TavilyClient(settings.tavily_api_key),
        llm_extract=make_extract_fn(settings),
        llm_judge=make_judge_fn(settings),
        llm_chat=make_chat_fn(settings),
        embedder=make_embedder(settings),
        qdrant=make_qdrant_client(settings.qdrant_url, settings.qdrant_api_key),
        reranker=make_reranker(settings),
    )
