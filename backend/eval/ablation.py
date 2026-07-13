"""Run the classification harness across retrieval configs to isolate each change's contribution.

baseline      -> coarse chunks, no reranker            (the original RAG)
finer         -> finer chunks, no reranker             (granularity only)
rerank        -> coarse chunks + voyage-rerank-2.5      (the advanced retriever)
rerank_finer  -> finer chunks + voyage-rerank-2.5       (retriever + granularity)
rerank_meta   -> rerank + court/year metadata check     (the second improvement)
"""
from __future__ import annotations

import json

from app.config import Settings
from eval.harness import DATA_DIR, compute_metrics, load_dataset, run

CONFIGS = [
    ("baseline", dict(chunk_target_tokens=1000, rerank_enabled=False, metadata_check=False)),
    ("finer", dict(chunk_target_tokens=500, rerank_enabled=False, metadata_check=False)),
    ("rerank", dict(chunk_target_tokens=1000, rerank_enabled=True, metadata_check=False)),
    ("rerank_finer", dict(chunk_target_tokens=500, rerank_enabled=True, metadata_check=False)),
    ("rerank_meta", dict(chunk_target_tokens=1000, rerank_enabled=True, metadata_check=True)),
]

HEADLINE_COLS = [
    "clean_verified_rate",
    "false_positive_rate_on_clean",
    "fabrication_recall",
    "detection_recall_overall",
    "exact_verdict_accuracy",
]


def main():
    items = load_dataset()
    summary = []
    for name, overrides in CONFIGS:
        print(f"\n=== CONFIG {name}: {overrides} ===\n")
        results = run(items, use_vectors=True, settings=Settings(**overrides))
        (DATA_DIR / f"results_{name}.jsonl").write_text("\n".join(r.model_dump_json() for r in results) + "\n")
        metrics = compute_metrics(results)
        metrics["config"] = overrides
        (DATA_DIR / f"metrics_{name}.json").write_text(json.dumps(metrics, indent=2))
        summary.append((name, metrics))

    print("\n\n================ ABLATION SUMMARY ================")
    header = f"{'config':15}" + "".join(f"{c[:14]:>16}" for c in HEADLINE_COLS) + f"{'wrongcourt_flag':>18}"
    print(header)
    for name, m in summary:
        h = m["headline"]
        wc = m["per_class"].get("wrong_court_year", {}).get("flag_accuracy")
        line = f"{name:15}" + "".join(f"{str(h.get(c)):>16}" for c in HEADLINE_COLS) + f"{str(wc):>18}"
        print(line)
    print(f"\nWrote metrics_<config>.json and results_<config>.jsonl to {DATA_DIR}")


if __name__ == "__main__":
    main()
