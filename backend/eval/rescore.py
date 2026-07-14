"""Re-derive verdicts on the saved ablation results using the current decide_verdict, without
re-running the pipeline. The adjudicator outputs (existence, quote, holding, confidence) are held
fixed, so this isolates the verdict-composition change and costs no API calls. Metadata overrides
are preserved: they only touch VERIFIED-base wrong_court items, which the fix does not alter."""
from __future__ import annotations

import json

from app.models import (
    ExistenceStatus as E,
    HoldingStatus as H,
    QuoteStatus as Q,
    Verdict as V,
    decide_verdict,
)
from eval.harness import DATA_DIR, compute_metrics
from eval.schema import EvalResult

CONFIGS = ["baseline", "finer", "rerank", "rerank_finer", "rerank_meta"]
COLS = ["clean_verified_rate", "false_positive_rate_on_clean", "fabrication_recall",
        "detection_recall_overall", "exact_verdict_accuracy"]


def _old_decide(e, q, h, conf, threshold=0.6):
    if e == E.NOT_FOUND:
        return V.FABRICATED
    if e in (E.FOUND_WEB, E.AMBIGUOUS):
        return V.UNVERIFIABLE
    if conf < threshold:
        return V.UNVERIFIABLE
    if q == Q.NOT_FOUND:
        return V.NOT_SUPPORTED
    if h in (H.CONTRADICTED, H.NOT_ADDRESSED):
        return V.NOT_SUPPORTED
    if q == Q.ALTERED or h == H.PARTIALLY_SUPPORTED:
        return V.ALTERED
    return V.VERIFIED


def _rescore(r: EvalResult) -> EvalResult:
    if r.actual_verdict == "error":
        return r
    e, q, h, conf = E(r.existence), Q(r.quote_status), H(r.holding_status), r.confidence
    base_old = _old_decide(e, q, h, conf)
    base_new = decide_verdict(e, q, h, conf)
    if r.actual_verdict != base_old.value:
        new_verdict = r.actual_verdict if base_new == base_old else base_new.value
    else:
        new_verdict = base_new.value
    return r.model_copy(update={
        "actual_verdict": new_verdict,
        "actual_flag": new_verdict != "verified",
        "correct": new_verdict == r.expected_verdict,
    })


def main():
    print(f"{'config':14}{'clean_ver':>11}{'clean_fp':>10}{'fab':>7}{'detect':>9}{'exact':>8}{'wrongct':>9}")
    for name in CONFIGS:
        p = DATA_DIR / f"results_{name}.jsonl"
        if not p.exists():
            continue
        results = [EvalResult.model_validate_json(x) for x in p.read_text().splitlines() if x.strip()]
        rescored = [_rescore(r) for r in results]
        metrics = compute_metrics(rescored)
        old = json.loads((DATA_DIR / f"metrics_{name}.json").read_text())
        metrics["config"] = old.get("config")
        p.write_text("\n".join(r.model_dump_json() for r in rescored) + "\n")
        (DATA_DIR / f"metrics_{name}.json").write_text(json.dumps(metrics, indent=2))
        h = metrics["headline"]
        wc = metrics["per_class"].get("wrong_court_year", {}).get("flag_accuracy")
        old_h = old["headline"]
        print(f"{name:14}{h['clean_verified_rate']!s:>11}{h['false_positive_rate_on_clean']!s:>10}"
              f"{h['fabrication_recall']!s:>7}{h['detection_recall_overall']!s:>9}"
              f"{h['exact_verdict_accuracy']!s:>8}{wc!s:>9}   (was exact {old_h['exact_verdict_accuracy']})")


if __name__ == "__main__":
    main()
