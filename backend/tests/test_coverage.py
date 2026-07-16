from datetime import date

from app.coverage import corpus_covers

TODAY = date(2026, 7, 16)


def test_database_cites_never_covered():
    assert not corpus_covers("2025 WL 1188342", None, TODAY)
    assert not corpus_covers("2024 U.S. Dist. LEXIS 90112", None, TODAY)


def test_recent_years_not_covered():
    assert not corpus_covers("118 F.4th 221", 2026, TODAY)
    assert not corpus_covers("118 F.4th 221", 2025, TODAY)


def test_published_reporters_covered():
    assert corpus_covers("347 U.S. 483", 1954, TODAY)
    assert corpus_covers("925 F.3d 1339", 2019, TODAY)
    assert corpus_covers("288 F.4th 1502", None, TODAY)


def test_unknown_reporters_not_covered():
    assert not corpus_covers("13 Cal. 5th 903", 2022, TODAY)
    assert not corpus_covers("100 F. Supp. 3d 12", 2015, TODAY)
