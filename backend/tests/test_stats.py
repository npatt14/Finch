from eval.schema import EvalResult
from eval.stats import bootstrap_ci, mcnemar_exact


def _res(i, correct=True, cite=None):
    return EvalResult(
        id=f"i{i}", klass="clean_verbatim", citation=cite or f"c{i}",
        expected_verdict="verified", expected_flag=False,
        actual_verdict="verified" if correct else "not_supported",
        actual_flag=not correct, correct=correct,
        existence="found", quote_status="verbatim", holding_status="supported", confidence=1.0,
    )


def test_mcnemar_known_value():
    a = [_res(i, correct=i >= 8) for i in range(10)]
    b = [_res(i, correct=i >= 2) for i in range(10)]
    out = mcnemar_exact(a, b)
    assert out["discordant_a_only"] == 0
    assert out["discordant_b_only"] == 6
    assert out["p_value"] == 0.0312


def test_mcnemar_identical_results():
    a = [_res(i) for i in range(10)]
    assert mcnemar_exact(a, a)["p_value"] == 1.0


def test_bootstrap_ci_degenerate_all_correct():
    rs = [_res(i) for i in range(12)]
    lo, hi = bootstrap_ci(rs, lambda s: sum(r.correct for r in s) / len(s), n_boot=200, seed=1)
    assert lo == hi == 1.0


def test_bootstrap_ci_brackets_point_estimate():
    rs = [_res(i, correct=i % 2 == 0) for i in range(40)]
    lo, hi = bootstrap_ci(rs, lambda s: sum(r.correct for r in s) / len(s), n_boot=500, seed=1)
    assert lo <= 0.5 <= hi
    assert lo < hi
