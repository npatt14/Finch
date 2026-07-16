from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from app.config import Settings
from app.graph import build_graph
from app.services import build_services
from eval.clcache import CachedCourtListener
from eval.embcache import CachedEmbedder
from eval.schema import (
    ADVERSARIAL_INJECTION,
    CLEAN_VERBATIM,
    FABRICATED_CITE,
    UNVERIFIABLE_RECENT,
    BenchItem,
    EvalResult,
)

DATA_DIR = Path(__file__).parent / "data"
FLAG_VERDICTS = {"altered", "not_supported", "unverifiable", "fabricated"}
PRESETS = {
    "baseline": dict(chunk_target_tokens=1000, rerank_enabled=False, metadata_check=False),
    "final": dict(chunk_target_tokens=1000, rerank_enabled=True, metadata_check=True),
}


def load_dataset(path: Path | None = None) -> list[BenchItem]:
    path = path or DATA_DIR / "briefbench_v2_dev.jsonl"
    return [BenchItem.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def build_eval_graph(settings: Settings):
    services = build_services(settings)
    services.embedder = CachedEmbedder(services.embedder, DATA_DIR / "embcache")
    services.cl = CachedCourtListener(services.cl, DATA_DIR / "clcache")
    return build_graph(services, checkpointer=MemorySaver())


def _error_result(item: BenchItem, message: str) -> EvalResult:
    return EvalResult(
        id=item.id, klass=item.klass, citation=item.citation, case_name=item.case_name,
        expected_verdict=item.expected_verdict, expected_flag=item.expected_flag,
        actual_verdict="error", actual_flag=False, correct=False,
        existence="error", quote_status="error", holding_status="error",
        confidence=0.0, error=message,
    )


def verify_item(graph, item: BenchItem, run_id: str) -> EvalResult:
    t0 = time.time()
    session = f"eval-{run_id}-{item.id}"
    state = graph.invoke(
        {"text": item.brief_text, "session_id": session},
        {"configurable": {"thread_id": session}},
    )
    results = state.get("results", [])
    match = next((r for r in results if r["citation"] == item.citation), None)
    if match is None and results:
        match = results[0]
    if match is None:
        return _error_result(item, "no citation unit extracted")
    verdict = match["verdict"]
    return EvalResult(
        id=item.id,
        klass=item.klass,
        citation=item.citation,
        case_name=item.case_name,
        expected_verdict=item.expected_verdict,
        expected_flag=item.expected_flag,
        actual_verdict=verdict,
        actual_flag=verdict in FLAG_VERDICTS,
        correct=verdict == item.expected_verdict,
        existence=match["existence"],
        quote_status=match["quote_status"],
        holding_status=match["holding_status"],
        confidence=match["confidence"],
        explanation=match.get("explanation", ""),
        warnings=state.get("warnings", []),
        retrieved_contexts=match.get("retrieved_contexts", []),
        reference_holding=item.reference_holding,
        latency_s=round(time.time() - t0, 2),
    )


def run(items: list[BenchItem], graph, run_id: str, throttle: float = 0.4, on_result=None) -> list[EvalResult]:
    results = []
    for i, item in enumerate(items, 1):
        try:
            res = verify_item(graph, item, run_id)
        except Exception as exc:
            res = _error_result(item, str(exc))
        results.append(res)
        if on_result:
            on_result(res)
        print(
            f"  [{i}/{len(items)}] {item.klass:22} {item.citation:26} "
            f"exp={item.expected_verdict:12} got={res.actual_verdict}"
        )
        if throttle:
            time.sleep(throttle)
    return results


def _rate(num, den):
    return round(num / den, 3) if den else None


def compute_metrics(results: list[EvalResult]) -> dict:
    by_class: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_class[r.klass].append(r)

    real = [r for r in results if r.klass != FABRICATED_CITE]
    clean = by_class.get(CLEAN_VERBATIM, [])
    fab = by_class.get(FABRICATED_CITE, [])
    recent = by_class.get(UNVERIFIABLE_RECENT, [])
    inject = by_class.get(ADVERSARIAL_INJECTION, [])
    should_flag = [r for r in results if r.expected_flag]

    per_class = {}
    for klass, rs in sorted(by_class.items()):
        per_class[klass] = {
            "n": len(rs),
            "verdict_accuracy": _rate(sum(r.correct for r in rs), len(rs)),
            "flag_accuracy": _rate(sum(r.actual_flag == r.expected_flag for r in rs), len(rs)),
        }

    lat = sorted(r.latency_s for r in results if r.latency_s)
    return {
        "n_items": len(results),
        "errors": sum(r.actual_verdict == "error" for r in results),
        "headline": {
            "real_case_called_fabricated": _rate(
                sum(r.actual_verdict == "fabricated" for r in real), len(real)
            ),
            "false_positive_rate_on_clean": _rate(sum(r.actual_flag for r in clean), len(clean)),
            "clean_verified_rate": _rate(sum(not r.actual_flag for r in clean), len(clean)),
            "fabrication_recall": _rate(sum(r.actual_verdict == "fabricated" for r in fab), len(fab)),
            "detection_recall_overall": _rate(sum(r.actual_flag for r in should_flag), len(should_flag)),
            "injection_resistance": _rate(sum(r.actual_flag for r in inject), len(inject)),
            "recent_not_miscalled_fabricated": _rate(
                sum(r.actual_verdict != "fabricated" for r in recent), len(recent)
            ),
            "exact_verdict_accuracy": _rate(sum(r.correct for r in results), len(results)),
        },
        "per_class": per_class,
        "latency_s": {
            "p50": lat[len(lat) // 2] if lat else None,
            "p95": lat[int(len(lat) * 0.95)] if lat else None,
            "max": lat[-1] if lat else None,
        },
    }


def aggregate(metric_dicts: list[dict]) -> dict:
    agg = {}
    for key in metric_dicts[0]["headline"]:
        vals = [m["headline"][key] for m in metric_dicts if m["headline"][key] is not None]
        if not vals:
            agg[key] = {"mean": None, "sd": None, "runs": []}
            continue
        agg[key] = {
            "mean": round(statistics.mean(vals), 3),
            "sd": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
            "runs": vals,
        }
    return agg


def _load_run_results(path: Path) -> list[EvalResult]:
    if not path.exists():
        return []
    return [EvalResult.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def run_named(items: list[BenchItem], out_dir: Path, settings: Settings, n_runs: int, throttle: float = 0.4) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_metrics = []
    for n in range(1, n_runs + 1):
        results_path = out_dir / f"results_r{n}.jsonl"
        done = {r.id for r in _load_run_results(results_path)}
        todo = [it for it in items if it.id not in done]
        if done:
            print(f"  resuming run {n}: {len(done)} items already checkpointed")
        if todo:
            graph = build_eval_graph(settings)
            with results_path.open("a") as f:
                def checkpoint(r, f=f):
                    f.write(r.model_dump_json() + "\n")
                    f.flush()

                run(todo, graph, run_id=f"{out_dir.name}-r{n}", throttle=throttle, on_result=checkpoint)
        results = _load_run_results(results_path)
        metrics = compute_metrics(results)
        (out_dir / f"metrics_r{n}.json").write_text(json.dumps(metrics, indent=2))
        all_metrics.append(metrics)
        print(f"\n--- run {n}/{n_runs} headline ---")
        print(json.dumps(metrics["headline"], indent=2))
    summary = aggregate(all_metrics)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _stratify(items: list[BenchItem], per_class: int) -> list[BenchItem]:
    buckets: dict[str, list[BenchItem]] = defaultdict(list)
    for it in items:
        buckets[it.klass].append(it)
    return [it for klass in sorted(buckets) for it in buckets[klass][:per_class]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--dataset", default=str(DATA_DIR / "briefbench_v2_dev.jsonl"))
    ap.add_argument("--config", choices=sorted(PRESETS), default="final")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--per-class", type=int, default=0)
    args = ap.parse_args()
    items = load_dataset(Path(args.dataset))
    if args.per_class:
        items = _stratify(items, args.per_class)
    settings = Settings(**PRESETS[args.config])
    out_dir = DATA_DIR / "runs" / args.name
    print(f"Running {len(items)} items x {args.runs} runs [{args.config}] -> {out_dir}\n")
    summary = run_named(items, out_dir, settings, args.runs)
    print("\n=== SUMMARY (mean over runs) ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
