from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph
from eval.harness import FLAG_VERDICTS, compute_metrics, verify_item
from eval.schema import BenchItem, EvalResult
from tests.test_graph import BRIEF, make_test_services


def _item(**kw):
    base = dict(
        id="x1",
        klass="clean_verbatim",
        citation="347 U.S. 483",
        case_name="Brown v. Board of Education",
        brief_text=BRIEF,
        quote=None,
        claim=None,
        expected_verdict="verified",
        expected_flag=False,
    )
    base.update(kw)
    return BenchItem(**base)


def test_verify_item_runs_full_pipeline_from_brief_text():
    services = make_test_services()
    graph = build_graph(services, checkpointer=MemorySaver())
    res = verify_item(graph, _item(), "t")
    assert res.actual_verdict == "verified"
    assert res.correct
    assert res.actual_flag == (res.actual_verdict in FLAG_VERDICTS)
    assert res.retrieved_contexts


def test_verify_item_handles_unextractable_brief():
    services = make_test_services()
    graph = build_graph(services, checkpointer=MemorySaver())
    res = verify_item(graph, _item(id="x2", brief_text="No citations appear in this text at all."), "t")
    assert res.actual_verdict == "error"
    assert res.error


def _eval_result(i, klass, verdict, expected_verdict="verified", expected_flag=False):
    return EvalResult(
        id=f"r{i}", klass=klass, citation=f"c{i}", expected_verdict=expected_verdict,
        expected_flag=expected_flag, actual_verdict=verdict,
        actual_flag=verdict in FLAG_VERDICTS, correct=verdict == expected_verdict,
        existence="found", quote_status="no_quote", holding_status="not_evaluated", confidence=1.0,
    )


def test_real_case_called_fabricated_headline():
    results = [
        _eval_result(1, "clean_verbatim", "verified"),
        _eval_result(2, "clean_verbatim", "fabricated"),
        _eval_result(3, "fabricated_cite", "fabricated", expected_verdict="fabricated", expected_flag=True),
    ]
    m = compute_metrics(results)
    assert m["headline"]["real_case_called_fabricated"] == 0.5


def test_exists_only_is_not_a_flag():
    assert "exists_only" not in FLAG_VERDICTS
    assert "verified" not in FLAG_VERDICTS
    assert FLAG_VERDICTS == {"altered", "not_supported", "unverifiable", "fabricated"}
