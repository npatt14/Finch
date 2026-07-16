"""Sample audited claims for hand labeling, then score human agreement with the generated labels."""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from eval.harness import load_dataset
from eval.schema import CLEAN_VERBATIM, OVERSTATED_HOLDING

DATA_DIR = Path(__file__).parent / "data"
SEED = 20260716
CSV_PATH = DATA_DIR / "human_audit.csv"


def make_template(n: int):
    items = [
        it
        for it in load_dataset(DATA_DIR / "briefbench_v2.jsonl")
        if it.klass in (CLEAN_VERBATIM, OVERSTATED_HOLDING)
    ]
    random.Random(SEED).shuffle(items)
    with CSV_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "reference_holding", "claim", "generated_label", "human_label"])
        for it in items[:n]:
            label = "faithful" if it.klass == CLEAN_VERBATIM else "overstated"
            w.writerow([it.id, it.reference_holding, it.claim, label, ""])
    print(f"wrote {min(n, len(items))} rows to {CSV_PATH}; fill human_label with faithful or overstated")


def score():
    with CSV_PATH.open() as f:
        rows = [r for r in csv.DictReader(f) if r["human_label"].strip()]
    if not rows:
        print("no human labels filled in yet")
        return
    agree = sum(r["human_label"].strip().lower() == r["generated_label"] for r in rows)
    print(f"labeled {len(rows)}, agreement {agree}/{len(rows)} = {agree / len(rows):.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    ap.add_argument("-n", type=int, default=25)
    args = ap.parse_args()
    score() if args.score else make_template(args.n)


if __name__ == "__main__":
    main()
