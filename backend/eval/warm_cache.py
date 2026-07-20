"""Resolve every distinct benchmark citation once into the eval disk cache. The citation
lookup endpoint allows 250 requests per day, so this waits out the throttle window instead
of burning quota on doomed retries. Cached answers make harness runs cost zero lookups."""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.config import Settings
from app.courtlistener import CourtListenerClient
from app.models import ExistenceStatus
from eval.clcache import CachedCourtListener

DATA_DIR = Path(__file__).parent / "data"
THROTTLE_WAIT_S = 420.0


def main():
    cites: dict[str, None] = {}
    for line in (DATA_DIR / "briefbench_v2.jsonl").read_text().splitlines():
        if line.strip():
            cites[json.loads(line)["citation"]] = None
    cl = CachedCourtListener(CourtListenerClient(token=Settings().courtlistener_token), DATA_DIR / "clcache")
    cl.RESOLVE_RETRIES = 1
    pending = list(cites)
    print(f"{len(pending)} distinct citations")
    passes = 0
    while pending and passes < 40:
        passes += 1
        still = []
        for cite in pending:
            existence, cid, _ = cl.resolve(cite)
            if existence == ExistenceStatus.AMBIGUOUS:
                still.append(cite)
            else:
                print(f"  ok {cite}: {existence.value}")
            time.sleep(2.0)
        pending = still
        if pending:
            print(f"pass {passes}: {len(pending)} still throttled, sleeping {THROTTLE_WAIT_S:.0f}s")
            time.sleep(THROTTLE_WAIT_S)
    if pending:
        print(f"GAVE UP on {len(pending)}: {pending}")
    else:
        print("ALL CITATIONS CACHED")


if __name__ == "__main__":
    main()
