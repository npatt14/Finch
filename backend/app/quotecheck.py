from __future__ import annotations

import re

from rapidfuzz import fuzz

from app.models import QuoteStatus

_ALTERED_THRESHOLD = 85.0


def _normalize(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = re.sub(r"\[([a-zA-Z])\]", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _segments(quote: str) -> list[str]:
    parts = re.split(r"\.\.\.|…", quote)
    return [p for p in (part.strip() for part in parts) if p]


def check_quote(quote: str, opinion_text: str) -> tuple[QuoteStatus, float]:
    if not quote or not quote.strip():
        return QuoteStatus.NO_QUOTE, 0.0
    haystack = _normalize(opinion_text)
    segs = [_normalize(s) for s in _segments(quote)]
    if not segs:
        return QuoteStatus.NO_QUOTE, 0.0
    if all(seg in haystack for seg in segs):
        return QuoteStatus.VERBATIM, 1.0
    score = min(fuzz.partial_ratio(seg, haystack) for seg in segs)
    if score >= _ALTERED_THRESHOLD:
        return QuoteStatus.ALTERED, score / 100
    return QuoteStatus.NOT_FOUND, score / 100
