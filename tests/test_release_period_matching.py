"""Regression tests for compact earnings-release period labels."""
from run_analysis import _release_matches_period
from scripts.sec_edgar_fetch import extract_index_exhibits


def test_iren_q4_fy26_release_matches_compact_label_and_report_date():
    text = "IREN Reports FY26 Results — FY26 and Q4 FY26 Financial Results — Quarter ended June 30, 2026"
    assert _release_matches_period(text, "2026-06-30", "Q4", 2026)


def test_release_period_match_rejects_wrong_fiscal_year():
    text = "Q4 FY25 Financial Results — Quarter ended June 30, 2025"
    assert not _release_matches_period(text, "2026-06-30", "Q4", 2026)


def test_sec_index_discovers_nonstandard_exhibit_filename_without_treating_xbrl_as_exhibit():
    html = """
    <table class="tableFile">
      <tr><td>2</td><td>EX-99.1</td><td><a href="/Archives/edgar/data/1/2/results.htm">results.htm</a></td><td>EX-99.1</td></tr>
      <tr><td>3</td><td>XBRL</td><td><a href="/Archives/edgar/data/1/2/company_pre.xml">company_pre.xml</a></td><td>EX-101.PRE</td></tr>
    </table>
    """
    exhibits = extract_index_exhibits(html, "https://www.sec.gov/Archives/edgar/data/1/2")
    assert exhibits == {
        "99.1": {
            "name": "results.htm",
            "url": "https://www.sec.gov/Archives/edgar/data/1/2/results.htm",
        }
    }
