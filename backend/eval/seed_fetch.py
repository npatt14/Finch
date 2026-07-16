"""Pull ordinary published circuit cases from CourtListener search as benchmark seeds.
Live API. Run once; output is committed so generation is reproducible."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from app.config import Settings

DATA_DIR = Path(__file__).parent / "data"
BASE = "https://www.courtlistener.com/api/rest/v4"
COURTS = ["ca1", "ca2", "ca3", "ca4", "ca5", "ca6", "ca7", "ca8", "ca9", "ca10", "ca11", "cadc"]
PER_COURT = 5


def fetch_seeds(token: str) -> list[dict]:
    headers = {"Authorization": f"Token {token}"} if token else {}
    client = httpx.Client(headers=headers, timeout=30)
    seeds = []
    for court in COURTS:
        r = client.get(
            f"{BASE}/search/",
            params={
                "type": "o",
                "court": court,
                "filed_after": "1985-01-01",
                "filed_before": "2018-12-31",
                "order_by": "dateFiled asc",
                "stat_Published": "on",
            },
        )
        r.raise_for_status()
        kept = 0
        for hit in r.json().get("results", []):
            cites = [c for c in (hit.get("citation") or []) if isinstance(c, str)]
            reporter_cite = next((c for c in cites if " F." in c), None)
            cluster_id = hit.get("cluster_id")
            if not reporter_cite or not cluster_id:
                continue
            year = (hit.get("dateFiled") or "")[:4]
            seeds.append(
                {
                    "citation": reporter_cite,
                    "case_name": hit.get("caseName"),
                    "cluster_id": cluster_id,
                    "court": court,
                    "year": int(year) if year.isdigit() else None,
                }
            )
            kept += 1
            if kept >= PER_COURT:
                break
        print(f"  {court}: {kept} seeds")
        time.sleep(1.0)
    return seeds


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seeds = fetch_seeds(Settings().courtlistener_token)
    out = DATA_DIR / "seeds_v2.json"
    out.write_text(json.dumps(seeds, indent=2))
    print(f"wrote {len(seeds)} seeds to {out}")


if __name__ == "__main__":
    main()
