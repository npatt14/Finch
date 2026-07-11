from app.models import QuoteStatus
from app.quotecheck import check_quote

OPINION = (
    "We conclude that in the field of public education the doctrine of "
    '"separate but equal" has no place. Separate educational facilities '
    "are inherently unequal."
)


def test_verbatim_with_brackets_and_curly_quotes():
    status, score = check_quote("[S]eparate educational facilities are inherently unequal.", OPINION)
    assert status == QuoteStatus.VERBATIM
    assert score == 1.0


def test_ellipsis_segments_all_present():
    status, _ = check_quote("in the field of public education … inherently unequal", OPINION)
    assert status == QuoteStatus.VERBATIM


def test_altered_quote_detected():
    status, score = check_quote(
        "Separate educational institutions are inherently unequal.", OPINION
    )
    assert status == QuoteStatus.ALTERED
    assert 0.85 <= score <= 1.0


def test_fabricated_quote_not_found():
    status, _ = check_quote("The Constitution requires busing in all districts.", OPINION)
    assert status == QuoteStatus.NOT_FOUND


def test_empty_quote():
    assert check_quote("", OPINION)[0] == QuoteStatus.NO_QUOTE
