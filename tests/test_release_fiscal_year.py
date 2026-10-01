from scripts.q4_release_parser import extract_fiscal_year


def test_extract_fiscal_year_accepts_common_release_labels():
    cases = {
        "Fourth quarter fiscal year 2026 results": 2026,
        "Full year 2026 financial results": 2026,
        "Q4 FY2026 earnings release": 2026,
        "Q4 FY 2026 earnings release": 2026,
        "fourth quarter 2026 results": 2026,
    }
    for text, expected in cases.items():
        assert extract_fiscal_year(text) == expected


def test_extract_fiscal_year_remains_fail_closed_without_year_identity():
    assert extract_fiscal_year("Fourth quarter results") is None