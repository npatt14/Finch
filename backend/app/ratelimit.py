from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float, now: Callable[[], float] = time.time):
        self.max = max_events
        self.window = window_seconds
        self._now = now
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str = "__global__") -> bool:
        if self.max <= 0:
            return True
        now = self._now()
        dq = self._events[key]
        cutoff = now - self.window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self.max:
            return False
        dq.append(now)
        return True
