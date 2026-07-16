from app.metadata import (
    apply_attribution,
    attribution_mismatch,
    parse_asserted_attribution,
    parse_asserted_for_span,
    reporter_court_level,
)
from app.models import Verdict


def _span(brief, cite):
    pos = brief.find(cite)
    return parse_asserted_for_span(brief, pos, pos + len(cite))


def test_span_parse_ignores_court_named_inside_the_quote():
    brief = (
        'As the court explained in Brown v. Board of Education, 347 U.S. 483, the opinion states that '
        '"They brought this action in the United States District Court for the Eastern District of South Carolina."'
    )
    assert _span(brief, "347 U.S. 483") == (None, None)


def test_span_parse_reads_the_introducing_clause():
    brief = 'As the Ninth Circuit held in 1998 in Roe v. Wade, 410 U.S. 113, "the opinion says x"'
    assert _span(brief, "410 U.S. 113") == ("Ninth Circuit", "1998")


def test_span_parse_scopes_to_nearest_clause_in_multi_cite():
    brief = "The Ninth Circuit decided Smith, 100 F.3d 1. In Brown, 347 U.S. 483, the Court held x."
    assert _span(brief, "347 U.S. 483") == (None, None)


def test_parse_finds_circuit_and_year():
    court, year = parse_asserted_attribution('As the Ninth Circuit held in 1998 in Roe v. Wade, 410 U.S. 113, "x"')
    assert court == "Ninth Circuit"
    assert year == "1998"


def test_parse_ignores_generic_reference():
    court, year = parse_asserted_attribution("As the court explained in Brown, 347 U.S. 483, the opinion states x")
    assert court is None
    assert year is None


def test_reporter_court_level():
    assert reporter_court_level("347 U.S. 483") == "supreme"
    assert reporter_court_level("883 F.3d 2450") == "appeals"
    assert reporter_court_level("410 F. Supp. 2d 100") == "district"


def test_mismatch_flags_wrong_court_and_year():
    reason = attribution_mismatch("410 U.S. 113", "Ninth Circuit", "1998", 1973)
    assert reason and "1998" in reason and "1973" in reason and "Ninth Circuit" in reason


def test_mismatch_none_when_consistent():
    assert attribution_mismatch("347 U.S. 483", None, "1954", 1954) is None


def test_apply_overrides_verified_to_altered():
    verdict, reason = apply_attribution(Verdict.VERIFIED, "410 U.S. 113", "Ninth Circuit", "1998", 1973)
    assert verdict == Verdict.ALTERED
    assert reason


def test_apply_does_not_downgrade_already_flagged():
    verdict, _ = apply_attribution(Verdict.FABRICATED, "410 U.S. 113", "Ninth Circuit", "1998", 1973)
    assert verdict == Verdict.FABRICATED


def test_attribution_upgrades_exists_only():
    v, reason = apply_attribution(Verdict.EXISTS_ONLY, "347 U.S. 483", "Ninth Circuit", "1998", 1954)
    assert v == Verdict.ALTERED
    assert reason
