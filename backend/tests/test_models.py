import pytest

from app.models import (
    ExistenceStatus as E,
    HoldingStatus as H,
    QuoteStatus as Q,
    Verdict as V,
    decide_verdict,
)


@pytest.mark.parametrize(
    "existence,quote,holding,conf,expected",
    [
        (E.NOT_FOUND, Q.NO_QUOTE, H.NOT_EVALUATED, 0.0, V.FABRICATED),
        (E.FOUND_WEB, Q.NO_QUOTE, H.NOT_EVALUATED, 0.0, V.UNVERIFIABLE),
        (E.AMBIGUOUS, Q.NO_QUOTE, H.NOT_EVALUATED, 0.0, V.UNVERIFIABLE),
        (E.FOUND, Q.VERBATIM, H.SUPPORTED, 0.9, V.VERIFIED),
        (E.FOUND, Q.NO_QUOTE, H.SUPPORTED, 0.9, V.VERIFIED),
        (E.FOUND, Q.ALTERED, H.SUPPORTED, 0.9, V.ALTERED),
        (E.FOUND, Q.VERBATIM, H.PARTIALLY_SUPPORTED, 0.9, V.ALTERED),
        (E.FOUND, Q.NOT_FOUND, H.SUPPORTED, 0.9, V.NOT_SUPPORTED),
        (E.FOUND, Q.VERBATIM, H.CONTRADICTED, 0.9, V.NOT_SUPPORTED),
        (E.FOUND, Q.VERBATIM, H.NOT_ADDRESSED, 0.9, V.NOT_SUPPORTED),
        (E.FOUND, Q.VERBATIM, H.SUPPORTED, 0.4, V.UNVERIFIABLE),
        (E.FOUND, Q.NOT_FOUND, H.CONTRADICTED, 0.55, V.NOT_SUPPORTED),
        (E.FOUND, Q.NOT_FOUND, H.SUPPORTED, 0.3, V.NOT_SUPPORTED),
        (E.FOUND, Q.VERBATIM, H.CONTRADICTED, 0.4, V.NOT_SUPPORTED),
        (E.FOUND, Q.VERBATIM, H.NOT_ADDRESSED, 0.4, V.NOT_SUPPORTED),
        (E.FOUND, Q.ALTERED, H.SUPPORTED, 0.3, V.ALTERED),
        (E.FOUND, Q.VERBATIM, H.NOT_EVALUATED, 1.0, V.VERIFIED),
        (E.FOUND, Q.NO_QUOTE, H.NOT_EVALUATED, 1.0, V.EXISTS_ONLY),
        (E.FOUND, Q.NO_QUOTE, H.NOT_EVALUATED, 0.0, V.UNVERIFIABLE),
    ],
)
def test_decide_verdict(existence, quote, holding, conf, expected):
    assert decide_verdict(existence, quote, holding, conf) == expected


def test_uncovered_corpus_miss_is_unverifiable():
    v = decide_verdict(E.NOT_FOUND, Q.NO_QUOTE, H.NOT_EVALUATED, 1.0, corpus_authoritative=False)
    assert v == V.UNVERIFIABLE


def test_covered_corpus_miss_stays_fabricated():
    v = decide_verdict(E.NOT_FOUND, Q.NO_QUOTE, H.NOT_EVALUATED, 1.0, corpus_authoritative=True)
    assert v == V.FABRICATED


def test_holding_assessment_clamps_confidence():
    from app.models import HoldingAssessment, HoldingStatus

    assert HoldingAssessment(status=HoldingStatus.SUPPORTED, confidence=1.7).confidence == 1.0
    assert HoldingAssessment(status=HoldingStatus.SUPPORTED, confidence=-0.2).confidence == 0.0
