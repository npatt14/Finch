import json

from langgraph.checkpoint.memory import MemorySaver

from app.config import Settings
from app.graph import build_graph, chat_answer
from app.models import ExistenceStatus, Verdict
from app.services import Services
from app.vectorstore import make_qdrant_client
from tests.test_vectorstore import HashEmbedder

BRIEF = (
    'In Brown v. Board of Education, 347 U.S. 483 (1954), the Court held that '
    '"[s]eparate educational facilities are inherently unequal." '
    "Plaintiff relies on Varghese v. China Southern Airlines, 925 F.3d 1339 (11th Cir. 2019)."
)

OPINION = (
    "We conclude that in the field of public education the doctrine of separate but equal "
    "has no place. Separate educational facilities are inherently unequal."
)


class FakeCL:
    def resolve(self, citation):
        if citation == "347 U.S. 483":
            return ExistenceStatus.FOUND, 105, "https://cl.test/brown"
        return ExistenceStatus.NOT_FOUND, None, None

    def opinion_text(self, cluster_id):
        return OPINION


class FakeTavily:
    def search_citation(self, citation, case_name):
        return False, ["https://web.test/search"]


def fake_extract(prompt):
    return json.dumps(
        {
            "units": [
                {
                    "unit_id": 1,
                    "quotes": ["[S]eparate educational facilities are inherently unequal."],
                    "claim": "Separate schools are inherently unequal.",
                },
                {"unit_id": 2, "quotes": [], "claim": "Tolling was recognized."},
            ]
        }
    )


def fake_judge(system, user):
    return json.dumps({"status": "supported", "confidence": 0.95, "explanation": "direct match"})


def make_test_services():
    return Services(
        settings=Settings(_env_file=None),
        cl=FakeCL(),
        tavily=FakeTavily(),
        llm_extract=fake_extract,
        llm_judge=fake_judge,
        llm_chat=lambda s, u: "The quote appears in the opinion.",
        embedder=HashEmbedder(),
        qdrant=make_qdrant_client("", ""),
    )


def test_graph_end_to_end_verdicts():
    services = make_test_services()
    graph = build_graph(services, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    state = graph.invoke({"text": BRIEF, "session_id": "t1"}, config)
    results = {r["citation"]: r for r in state["results"]}
    assert results["347 U.S. 483"]["verdict"] == Verdict.VERIFIED.value
    assert results["925 F.3d 1339"]["verdict"] == Verdict.FABRICATED.value
    assert results["925 F.3d 1339"]["search_trail"]


def test_graph_survives_embedding_failure():
    services = make_test_services()

    class Boom:
        def embed_documents(self, texts):
            raise RuntimeError("429 rate limited")

        def embed_query(self, text):
            raise RuntimeError("429 rate limited")

    services.embedder = Boom()
    graph = build_graph(services, checkpointer=MemorySaver())
    state = graph.invoke({"text": BRIEF, "session_id": "t3"}, {"configurable": {"thread_id": "t3"}})
    results = {r["citation"]: r for r in state["results"]}
    assert results["347 U.S. 483"]["verdict"] == Verdict.VERIFIED.value
    assert results["925 F.3d 1339"]["verdict"] == Verdict.FABRICATED.value


def test_chat_answers_from_thread_state():
    services = make_test_services()
    graph = build_graph(services, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t2"}}
    graph.invoke({"text": BRIEF, "session_id": "t2"}, config)
    answer = chat_answer(services, graph, "t2", "Where does the quote appear?")
    assert "opinion" in answer.lower()
