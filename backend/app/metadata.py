from __future__ import annotations

import re

from app.models import Verdict

_CIRCUITS = (
    r"(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Federal|D\.?\s?C\.?)"
)
_COURT_RX = re.compile(
    rf"\b{_CIRCUITS}\s+Circuit\b|\bCourt of Appeals\b|\bSupreme Court\b|\bDistrict Court\b|\bDistrict of \w+",
    re.I,
)
_YEAR_RX = re.compile(r"\b(1[789]\d\d|20\d\d)\b")
_PRIOR_CITE = re.compile(
    r"\d+\s+(?:U\.?\s?S\.?|S\.?\s?Ct\.?|L\.?\s?Ed\.?(?:\s?2d)?|F\.?\s?(?:2d|3d|4th|App'?x)|F\.?\s?Supp\.?(?:\s?[23]d)?)\s+\d+",
    re.I,
)


def parse_asserted_attribution(text: str) -> tuple[str | None, str | None]:
    """Pull the court and year a brief attributes to a citation. A brief that says nothing
    specific ('as the court explained') yields (None, None) and never triggers a mismatch."""
    court_match = _COURT_RX.search(text or "")
    year_match = _YEAR_RX.search(text or "")
    court = court_match.group(0).strip() if court_match else None
    year = year_match.group(0) if year_match else None
    return court, year


def parse_asserted_for_span(text: str, cite_start: int, cite_end: int) -> tuple[str | None, str | None]:
    """Read the attribution from the clause introducing this citation only. The quoted opinion text
    follows the citation (excluded by looking only before it), and any prior citation ends the prior
    clause (excluded by cutting after the last reporter token), so a court named elsewhere in the
    brief is never mistaken for this citation's asserted court."""
    pre = text[max(0, cite_start - 220) : cite_start]
    prior = list(_PRIOR_CITE.finditer(pre))
    if prior:
        pre = pre[prior[-1].end() :]
    return parse_asserted_attribution(pre + text[cite_start:cite_end])


def reporter_court_level(citation: str) -> str | None:
    if re.search(r"\bU\.?\s?S\.?\b|\bS\.?\s?Ct\.?\b|\bL\.?\s?Ed\b", citation):
        return "supreme"
    if re.search(r"\bF\.?\s?Supp", citation):
        return "district"
    if re.search(r"\bF\.?\s?(2d|3d|4th|App)", citation):
        return "appeals"
    return None


def _asserted_court_level(court: str) -> str | None:
    c = court.lower()
    if "supreme" in c:
        return "supreme"
    if "circuit" in c or "court of appeals" in c:
        return "appeals"
    if "district" in c:
        return "district"
    return None


def attribution_mismatch(
    citation: str, asserted_court: str | None, asserted_year: str | None, actual_year: int | None
) -> str | None:
    reasons: list[str] = []
    if asserted_year and actual_year and int(asserted_year) != actual_year:
        reasons.append(f"the brief dates {citation} to {asserted_year}, but it was decided in {actual_year}")
    if asserted_court:
        expected = reporter_court_level(citation)
        asserted = _asserted_court_level(asserted_court)
        if expected and asserted and expected != asserted:
            reasons.append(
                f"the brief attributes {citation} to the {asserted_court}, "
                f"but {citation} is published in a {expected}-court reporter"
            )
    return "; ".join(reasons) or None


def apply_attribution(
    verdict: Verdict,
    citation: str,
    asserted_court: str | None,
    asserted_year: str | None,
    actual_year: int | None,
) -> tuple[Verdict, str | None]:
    reason = attribution_mismatch(citation, asserted_court, asserted_year, actual_year)
    if reason and verdict in (Verdict.VERIFIED, Verdict.EXISTS_ONLY):
        return Verdict.ALTERED, reason
    return verdict, reason
