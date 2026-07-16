from langgraph.checkpoint.memory import MemorySaver

from app.config import Settings
from app.graph import build_graph, chat_answer
from app.models import (
    ExistenceStatus,
    ExtractionPayload,
    HoldingAssessment,
    HoldingStatus,
    UnitAttachment,
    Verdict,
)
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
    return ExtractionPayload(
        units=[
            UnitAttachment(
                unit_id=1,
                quotes=["[S]eparate educational facilities are inherently unequal."],
                claim="Separate schools are inherently unequal.",
            ),
            UnitAttachment(unit_id=2, quotes=[], claim="Tolling was recognized."),
        ]
    )


def fake_judge(system, user):
    return HoldingAssessment(status=HoldingStatus.SUPPORTED, confidence=0.95, explanation="direct match")


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


def test_make_checkpointer_defaults_to_memory():
    from app.graph import make_checkpointer

    cp = make_checkpointer(Settings(_env_file=None, database_url=""))
    assert isinstance(cp, MemorySaver)


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


def test_missing_uncovered_cite_is_unverifiable():
    from app.graph import _verify_one
    from app.models import CitationUnit

    services = make_test_services()
    unit = CitationUnit(unit_id=1, citation="2025 WL 1188342", case_name="Reyes v. Coastal Dynamics")
    result = _verify_one(services, unit, "t4")
    assert result.verdict == Verdict.UNVERIFIABLE


def test_missing_covered_cite_stays_fabricated():
    from app.graph import _verify_one
    from app.models import CitationUnit

    services = make_test_services()
    unit = CitationUnit(unit_id=1, citation="925 F.3d 1339", case_name="Varghese")
    result = _verify_one(services, unit, "t5")
    assert result.verdict == Verdict.FABRICATED


def test_existence_only_unit_is_exists_only():
    from app.graph import _verify_one
    from app.models import CitationUnit

    services = make_test_services()
    unit = CitationUnit(unit_id=1, citation="347 U.S. 483", case_name="Brown v. Board of Education")
    result = _verify_one(services, unit, "t6")
    assert result.verdict == Verdict.EXISTS_ONLY
    assert "existence" in result.explanation.lower() or "exists" in result.explanation.lower()


def test_graph_degrades_honestly_when_extraction_fails():
    services = make_test_services()

    def boom(prompt):
        raise RuntimeError("gateway down")

    services.llm_extract = boom
    graph = build_graph(services, checkpointer=MemorySaver())
    state = graph.invoke({"text": BRIEF, "session_id": "t7"}, {"configurable": {"thread_id": "t7"}})
    assert any("Quote attachment degraded" in w for w in state["warnings"])
    results = {r["citation"]: r for r in state["results"]}
    assert results["347 U.S. 483"]["verdict"] == Verdict.EXISTS_ONLY.value


def test_result_carries_retrieved_contexts():
    services = make_test_services()
    graph = build_graph(services, checkpointer=MemorySaver())
    state = graph.invoke({"text": BRIEF, "session_id": "t8"}, {"configurable": {"thread_id": "t8"}})
    results = {r["citation"]: r for r in state["results"]}
    assert results["347 U.S. 483"]["retrieved_contexts"]
