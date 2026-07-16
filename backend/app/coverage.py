from __future__ import annotations

import re
from datetime import date

_DATABASE_CITE = re.compile(r"\b(WL|LEXIS)\b", re.IGNORECASE)
_AUTHORITATIVE = re.compile(
    r"\b\d{1,4}\s+(U\.\s?S\.|S\.\s?Ct\.|L\.\s?Ed\.(\s?2d)?|F\.\s?(2d|3d|4th))\s+\d{1,5}\b"
)
_RECENT_WINDOW_YEARS = 2


def corpus_covers(citation: str, year: int | None = None, today: date | None = None) -> bool:
    """Corpus absence proves nonexistence only for reporters CourtListener fully covers.
    Database cites and very recent decisions can be real yet missing."""
    if _DATABASE_CITE.search(citation):
        return False
    current = (today or date.today()).year
    if year is not None and year > current - _RECENT_WINDOW_YEARS:
        return False
    return bool(_AUTHORITATIVE.search(citation))
