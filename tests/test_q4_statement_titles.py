from scripts.q4_release_parser import find_statement_titles


def test_statement_title_discovery_accepts_issuer_neutral_variants():
    content = """
    Condensed Consolidated Balance Sheets
    Three Months Ended
    Condensed Consolidated Statements of Operations
    Three Months Ended
    Condensed Consolidated Statements of Cash Flows
    Three Months Ended
    """
    titles = find_statement_titles(content)
    assert list(titles) == ["balance", "operations", "cash_flows"]
    assert titles["balance"][0] < titles["operations"][0] < titles["cash_flows"][0]


def test_statement_title_discovery_supports_financial_position_wording():
    content = """
    Consolidated Statements of Financial Position
    Three Months Ended
    Consolidated Statements of Operations and Comprehensive Income (Loss)
    Three Months Ended
    Consolidated Statements of Cash Flows
    Three Months Ended
    """
    titles = find_statement_titles(content)
    assert set(titles) == {"balance", "operations", "cash_flows"}


def test_statement_title_discovery_supports_nonstandard_statement_order():
    content = """
    Consolidated Statements of Operations
    Consolidated Balance Sheets
    Consolidated Statements of Cash Flows
    """
    titles = find_statement_titles(content)
    assert set(titles) == {"balance", "operations", "cash_flows"}
    assert titles["operations"][0] < titles["balance"][0] < titles["cash_flows"][0]
