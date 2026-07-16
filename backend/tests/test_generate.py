from eval.generate import (
    COURT_LABEL,
    INJECTIONS,
    _brief,
    _fabricated_cites,
    _recent_cites,
    _sentences,
    _wrong_attribution,
)


def test_fabricated_cites_are_plausible_and_deterministic():
    cites = _fabricated_cites()
    assert cites == _fabricated_cites()
    assert len(cites) >= 12
    for cite, name in cites:
        vol, series, page = cite.split(" ", 2)
        assert series in ("F.3d", "F.4th")
        assert 1 <= int(vol) <= (999 if series == "F.3d" else 200)
        assert 1 <= int(page) <= 1400
        assert " v. " in name


def test_recent_cites_are_outside_corpus_coverage():
    from app.coverage import corpus_covers

    for cite, name, year in _recent_cites():
        assert not corpus_covers(cite, year)


def test_wrong_attribution_never_matches_actual():
    court, year = _wrong_attribution(idx=3, actual_court="ca9", actual_year=2004)
    assert court != COURT_LABEL["ca9"]
    assert year != 2004


def test_brief_templates_rotate_and_embed_parts():
    b0 = _brief(0, "Smith v. Jones", "100 F.3d 1 (1st Cir. 1996)", quote="the rule applies", claim="The rule applies.")
    b1 = _brief(1, "Smith v. Jones", "100 F.3d 1 (1st Cir. 1996)", quote="the rule applies", claim="The rule applies.")
    assert b0 != b1
    for b in (b0, b1):
        assert "Smith v. Jones" in b and "100 F.3d 1" in b and "the rule applies" in b


def test_sentences_prefers_holding_language():
    text = (
        "The clerk entered the judgment on March 3. "
        "We hold that the statute requires exhaustion of administrative remedies before filing suit. "
        "The parties briefed the issue extensively over several months of motion practice."
    )
    sents = _sentences(text)
    assert sents[0].startswith("We hold")


def test_injection_variants_are_distinct():
    assert len(set(INJECTIONS)) == len(INJECTIONS) >= 5
