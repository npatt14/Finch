"""Freeze a dev/holdout split at the seed case level so no opinion appears on both sides.
Tune only on dev. Run holdout once per release and report it unmodified."""
from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

from eval.schema import BenchItem

DATA_DIR = Path(__file__).parent / "data"
SEED = 20260716


def split_items(
    items: list[BenchItem], holdout_fraction: float = 0.3, seed: int = SEED
) -> tuple[list[BenchItem], list[BenchItem]]:
    by_seed: dict[str, list[BenchItem]] = defaultdict(list)
    for it in items:
        by_seed[it.citation].append(it)
    seeds = sorted(by_seed)
    random.Random(seed).shuffle(seeds)
    cut = round(len(seeds) * holdout_fraction)
    holdout = [it for s in seeds[:cut] for it in by_seed[s]]
    dev = [it for s in seeds[cut:] for it in by_seed[s]]
    return dev, holdout


def main():
    src = DATA_DIR / "briefbench_v2.jsonl"
    items = [BenchItem.model_validate_json(line) for line in src.read_text().splitlines() if line.strip()]
    dev, holdout = split_items(items)
    (DATA_DIR / "briefbench_v2_dev.jsonl").write_text("\n".join(i.model_dump_json() for i in dev) + "\n")
    (DATA_DIR / "briefbench_v2_holdout.jsonl").write_text("\n".join(i.model_dump_json() for i in holdout) + "\n")
    print(f"dev {len(dev)} items, holdout {len(holdout)} items, from {len(items)} total")


if __name__ == "__main__":
    main()
