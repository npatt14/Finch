"""Cluster bootstrap CIs and exact McNemar for paired harness runs. Items generated from the
same seed case share an opinion, so resampling is by citation, not by item."""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from eval.harness import compute_metrics
from eval.schema import EvalResult

HEADLINE_KEYS = [
    "real_case_called_fabricated",
    "false_positive_rate_on_clean",
    "fabrication_recall",
    "detection_recall_overall",
    "injection_resistance",
    "recent_not_miscalled_fabricated",
    "exact_verdict_accuracy",
]


def load_results(path: Path) -> list[EvalResult]:
    return [EvalResult.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]


def bootstrap_ci(results, stat_fn, n_boot: int = 2000, seed: int = 7, alpha: float = 0.05):
    clusters = defaultdict(list)
    for r in results:
        clusters[r.citation].append(r)
    keys = sorted(clusters)
    rng = random.Random(seed)
    stats = []
    for _ in range(n_boot):
        sample = []
        for _ in keys:
            sample.extend(clusters[rng.choice(keys)])
        value = stat_fn(sample)
        if value is not None:
            stats.append(value)
    if len(stats) < n_boot // 2:
        return None, None
    stats.sort()
    lo = stats[int(len(stats) * alpha / 2)]
    hi = stats[min(len(stats) - 1, int(len(stats) * (1 - alpha / 2)))]
    return round(lo, 3), round(hi, 3)


def mcnemar_exact(results_a: list[EvalResult], results_b: list[EvalResult]) -> dict:
    by_id_b = {r.id: r for r in results_b}
    a_only = b_only = 0
    for ra in results_a:
        rb = by_id_b.get(ra.id)
        if rb is None:
            continue
        if ra.correct and not rb.correct:
            a_only += 1
        elif rb.correct and not ra.correct:
            b_only += 1
    n = a_only + b_only
    if n == 0:
        return {"discordant_a_only": 0, "discordant_b_only": 0, "p_value": 1.0}
    k = min(a_only, b_only)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return {"discordant_a_only": a_only, "discordant_b_only": b_only, "p_value": round(min(p, 1.0), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--compare")
    ap.add_argument("--boot", type=int, default=2000)
    args = ap.parse_args()
    a = load_results(Path(args.results))
    print(f"n={len(a)} clusters={len({r.citation for r in a})}\n")
    headline = compute_metrics(a)["headline"]
    for key in HEADLINE_KEYS:
        lo, hi = bootstrap_ci(a, lambda s, k=key: compute_metrics(s)["headline"][k], n_boot=args.boot)
        print(f"{key:34} {headline[key]}  95% ci [{lo}, {hi}]")
    if args.compare:
        b = load_results(Path(args.compare))
        print("\nmcnemar on exact verdict correctness vs compare file:")
        print(json.dumps(mcnemar_exact(a, b), indent=2))


if __name__ == "__main__":
    main()
