"""Run the harness across retrieval configs on identical data. Disk caches for CourtListener and
embeddings make retrieval inputs identical across configs; only the adjudicator varies run to run."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.config import Settings
from eval.harness import DATA_DIR, PRESETS, load_dataset, run_named

CONFIGS = [
    ("baseline", PRESETS["baseline"]),
    ("finer", dict(chunk_target_tokens=500, rerank_enabled=False, metadata_check=False)),
    ("rerank", dict(chunk_target_tokens=1000, rerank_enabled=True, metadata_check=False)),
    ("rerank_meta", PRESETS["final"]),
]

HEADLINE_COLS = [
    "real_case_called_fabricated",
    "false_positive_rate_on_clean",
    "fabrication_recall",
    "detection_recall_overall",
    "exact_verdict_accuracy",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--dataset", default=str(DATA_DIR / "briefbench_v2_dev.jsonl"))
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    items = load_dataset(Path(args.dataset))
    summaries = []
    for cfg_name, overrides in CONFIGS:
        print(f"\n=== CONFIG {cfg_name}: {overrides} ===\n")
        out_dir = DATA_DIR / "runs" / args.name / cfg_name
        summary = run_named(items, out_dir, Settings(**overrides), args.runs)
        summaries.append((cfg_name, summary))

    print("\n\n================ ABLATION SUMMARY (mean over runs) ================")
    print(f"{'config':13}" + "".join(f"{c[:18]:>20}" for c in HEADLINE_COLS))
    for cfg_name, s in summaries:
        row = "".join(f"{str(s.get(c, {}).get('mean')):>20}" for c in HEADLINE_COLS)
        print(f"{cfg_name:13}" + row)
    print(f"\nWrote per run artifacts under {DATA_DIR / 'runs' / args.name}")


if __name__ == "__main__":
    main()
