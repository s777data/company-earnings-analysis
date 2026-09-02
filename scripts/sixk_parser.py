#!/usr/bin/env python3
"""Parser for foreign issuer 6-K HTML financial statement exhibits.

Extracts financial metrics from HTML table content in 6-K exhibits
(for companies like KLAR that file 6-K instead of 10-Q).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class Context:
    start: str | None
    end: str
    instant: bool
    dimensions: tuple[str, ...]


# IFRS concept mapping - maps our internal metric names to IFRS labels in the tables
# Using tuples of (label, exact_match_flag) where exact_match_flag=True means 
# the label must match the full row start (not just a substring)
IFRS_LABELS = {
    "revenue": [
        ("Total revenue", True),
        ("Revenue", True),
        ("Total Revenue", True),
    ],
    "gross_profit": [
        ("Gross profit", True),
        ("Gross Profit", True),
    ],
    "operating_income": [
        ("Operating profit (loss)", True),
        ("Operating profit", True),
        ("Operating income (loss)", True),
        ("Operating Income", True),
    ],
    "net_income": [
        ("Net profit (loss)", True),
        ("Net profit", True),
        ("Net income (loss)", True),
        ("Profit (loss) for the period", True),
        ("Net Income", True),
    ],
    "eps_diluted": [
        ("Diluted", True),
        ("Net profit (loss) per share", True),
        ("Earnings per share diluted", True),
    ],
    "operating_cash_flow": [
        ("Net cash provided by (used in) operating activities", True),
        ("Cash flows from operating activities", True),
        ("Operating cash flow", True),
    ],
    "capex": [
        ("Payments to acquire property, plant and equipment", True),
        ("Capital expenditures", True),
        ("Purchase of property, plant and equipment", True),
    ],
    "stock_based_compensation": [
        ("Share-based payments expense", True),
        ("Share-based compensation", True),
        ("Stock-based compensation", True),
    ],
    "depreciation_amortization": [
        ("Depreciation, amortization and impairments", True),
        ("Depreciation and amortization", True),
        ("Depreciation, depletion and amortization", True),
    ],
    "backlog": [
        ("Revenue remaining performance obligation", True),
        ("Backlog", True),
    ],
    "cash": [
        ("Cash and cash equivalents", True),
        ("Cash and cash equivalents at carrying value", True),
    ],
    "total_assets": [
        ("Total assets", True),
        ("Total Assets", True),
    ],
    "total_liabilities": [
        ("Total liabilities", True),
        ("Total Liabilities", True),
    ],
    "total_equity": [
        ("Total equity excluding non-controlling interests", True),
        ("Total equity", True),
        ("Equity attributable to owners of the parent", True),
        ("Stockholders' equity", True),
    ],
    "long_term_debt": [
        ("Notes payable and other borrowings", True),
        ("Long-term debt", True),
        ("Long term debt", True),
        ("Borrowings", True),
    ],
    "shares_diluted": [
        ("Weighted average number of ordinary shares - diluted", True),
        ("Diluted shares", True),
        ("Weighted average diluted shares", True),
    ],
    "provision_for_credit_losses": [
        ("Provision for credit losses", True),
    ],
    "funding_costs": [
        ("Funding costs", True),
        ("Total funding costs", True),
    ],
    "transaction_margin": [
        ("Transaction margin dollars", True),
        ("Transaction margin", True),
    ],
    "adjusted_operating_income": [
        ("Adjusted operating income (loss)", True),
        ("Adjusted operating income", True),
    ],
    "consumer_receivables": [
        ("Consumer receivables at amortized cost", True),
        ("Consumer receivables", True),
    ],
    "consumer_deposits": [
        ("Consumer deposits", True),
    ],
}

# Map our metrics to the statement sections they appear in
STATEMENT_SECTIONS = {
    "profit_or_loss": [
        "revenue", "gross_profit", "operating_income", "net_income", 
        "eps_diluted", "provision_for_credit_losses", "funding_costs",
        "transaction_margin", "adjusted_operating_income",
        "stock_based_compensation", "depreciation_amortization"
    ],
    "financial_position": [
        "cash", "total_assets", "total_liabilities", "total_equity",
        "long_term_debt", "consumer_receivables", "consumer_deposits"
    ],
    "cash_flows": [
        "operating_cash_flow", "capex"
    ],
    "changes_in_equity": [
        "shares_diluted"
    ],
}


def _clean_value(text: str) -> float | None:
    """Extract numeric value from table cell text."""
    if not text or text.strip() in ("—", "–", "-", "", "N/A", "n/a"):
        return None
    # Remove currency symbols, commas, parentheses for negatives
    cleaned = text.replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
    # Handle millions/billions notation
    multiplier = 1
    if "million" in cleaned.lower() or "m" == cleaned.lower()[-1:]:
        multiplier = 1_000_000
        cleaned = cleaned.lower().replace("million", "").replace("m", "").strip()
    elif "billion" in cleaned.lower() or "b" == cleaned.lower()[-1:]:
        multiplier = 1_000_000_000
        cleaned = cleaned.lower().replace("billion", "").replace("b", "").strip()
    elif "thousand" in cleaned.lower() or "k" == cleaned.lower()[-1:]:
        multiplier = 1_000
        cleaned = cleaned.lower().replace("thousand", "").replace("k", "").strip()
    
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def _find_financial_table(content: str, table_type: str) -> str | None:
    """Find a specific financial statement table by looking for its column headers.
    
    table_type: "profit_loss", "financial_position", "cash_flows", "changes_in_equity"
    """
    # Column header patterns for each table type - be very specific
    if table_type == "profit_loss":
        header_patterns = [
            r"Three Months Ended.*Six Months Ended.*USD millions",
            r"Three Months Ended.*June 30.*2026.*June 30.*2025.*Six Months Ended.*June 30.*2026.*June 30.*2025",
        ]
    elif table_type == "financial_position":
        header_patterns = [
            r"Interim condensed consolidated statement of financial position.*USD millions.*June 30.*2026.*December 31.*2025",
            r"statement of financial position.*USD millions.*Note.*June 30.*2026.*December 31.*2025",
        ]
    elif table_type == "cash_flows":
        header_patterns = [
            r"Interim condensed consolidated statement of cash flows.*Six Months Ended.*June 30.*2026.*June 30.*2025",
            r"statement of cash flows.*Six Months Ended.*USD millions.*June 30.*2026.*June 30.*2025",
        ]
    elif table_type == "changes_in_equity":
        header_patterns = [
            r"Interim condensed consolidated statement of changes in equity.*USD millions.*Balance as of",
            r"statement of changes in equity.*USD millions.*Share capital",
        ]
    else:
        return None
    
    # Find the position of the header
    header_idx = -1
    for pattern in header_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            header_idx = match.start()
            break
    
    if header_idx == -1:
        return None
    
    # Find the end of this table - look for next major section
    end_patterns = [
        r"Interim condensed consolidated statement of (comprehensive|financial position|changes|cash flows)",
        r"^Note \d+",
        r"^KLARNA GROUP PLC",
    ]
    
    end_idx = len(content)
    for pattern in end_patterns:
        for match in re.finditer(pattern, content[header_idx + 100:], re.MULTILINE):
            candidate = header_idx + 100 + match.start()
            if candidate > header_idx:
                end_idx = min(end_idx, candidate)
                break
    
    return content[header_idx:end_idx]


def _split_table_rows(table_text: str) -> list[str]:
    """Split a flattened table text into logical rows based on known row starters."""
    # Known row starting labels in order
    row_starters = [
        "Transaction and service revenue",
        "Gain on sale of consumer",
        "Interest income",
        "Total revenue",
        "Processing and servicing costs",
        "Provision for credit losses",
        "Funding costs",
        "Technology and product",
        "Sales and marketing",
        "Customer service and operations",
        "General and administrative",
        "Depreciation, amortization and",
        "Operating expenses",
        "Operating profit",
        "Other income",
        "Profit (loss) before taxes",
        "Tax (expense) benefit",
        "Net profit (loss)",
        "Whereof attributable to:",
        "Non-controlling interests",
        "Net profit (loss) per share",
        "Diluted",
        "Cash and cash equivalents",
        "Debt securities",
        "Consumer receivables at amortized cost",
        "Consumer receivables at fair value through OCI",
        "Consumer receivables at fair value through profit or loss",
        "Other financial assets at amortized cost",
        "Settlement, trade and other receivables",
        "Property and equipment",
        "Goodwill",
        "Intangible assets",
        "Deferred tax assets",
        "Other assets",
        "Total assets",
        "Accounts payable and accrued expenses",
        "Consumer deposits",
        "Payables to merchants",
        "Notes payable and other borrowings",
        "Deferred tax liabilities",
        "Other liabilities",
        "Total liabilities",
        "Share capital",
        "Additional paid in capital",
        "Reserves",
        "Retained earnings",
        "Total equity excluding non-controlling interests",
        "Non-controlling interests",
        "Total equity",
        "Total equity and liabilities",
        "Operating activities",
        "Profit (loss) before taxes",
        "Income taxes paid",
        "Interest expense paid",
        "Interest income received",
        "Adjustments for non-cash items",
        "Depreciation, amortization and impairment",
        "Share-based payments",
        "Provision for credit losses",
        "Financial items including fair value effects",
        "Changes in the assets and liabilities",
        "Change in consumer receivables",
        "Change in other financial assets",
        "Change in settlement, trade and other receivables",
        "Change in notes payable and other borrowings",
    ]
    
    # Split by finding each row starter
    rows = []
    pos = 0
    while pos < len(table_text):
        # Find next row starter
        next_pos = len(table_text)
        next_starter = None
        for starter in row_starters:
            idx = table_text.find(starter, pos + 1)
            if idx >= 0 and idx < next_pos:
                next_pos = idx
                next_starter = starter
        
        if pos > 0:  # Not the first iteration (which starts at header)
            row = table_text[pos:next_pos].strip()
            if row:
                rows.append(row)
        
        if next_starter is None:
            break
        pos = next_pos
    
    return rows


def _extract_table_values(row_text: str, expected_cols: int = 4) -> list[float]:
    """Extract numeric values from a table row, skipping note numbers.
    
    Table rows have format: Label .... note# value1 value2 value3 value4
    or: Label value1 value2 (for balance sheet with 2 columns)
    
    The note number is typically a small integer (1-99) that appears before
    the actual financial values which are typically larger (hundreds+).
    """
    # Split by multiple spaces or dots
    parts = re.split(r'\s{2,}|\.{3,}', row_text)
    values = []
    for part in parts:
        nums = re.findall(r'\(?[\d,]+\.?\d*\)?', part)
        for n in nums:
            val = _clean_value(n)
            if val is not None:
                values.append(val)
    
    # Filter out likely note numbers
    # Note numbers are typically small integers (< 100) that appear at the start
    # Actual financial values are typically larger (>= 100) or negative
    filtered = []
    for i, v in enumerate(values):
        # Skip if it's a likely note number: small positive integer at the beginning
        if i == 0 and 0 < v < 100 and v == int(v):
            # Check if the next values are much larger in magnitude
            if len(values) > 1 and abs(values[1]) >= 100:
                continue
        filtered.append(v)
    
    # If we have more values than expected columns, the first ones might be note numbers
    if len(filtered) > expected_cols:
        # Keep the last expected_cols values
        filtered = filtered[-expected_cols:]
    
    return filtered


def _match_label_in_row(row: str, labels: list[tuple[str, bool]]) -> bool:
    """Check if any label matches the row precisely.
    
    All labels use exact_match=True, meaning the row must start with the label
    followed by a separator (dots, spaces) and then numbers - not more words.
    """
    row_stripped = row.lstrip()
    for label, _ in labels:
        label_lower = label.lower()
        row_lower = row_stripped.lower()
        
        # Check if row starts with label
        if row_lower.startswith(label_lower):
            # After the label, we expect only separators (dots, spaces) then numbers
            # Not more words like "and liabilities"
            after_label = row_lower[len(label_lower):]
            
            # Skip leading separators
            i = 0
            while i < len(after_label) and after_label[i] in ' \t.':
                i += 1
            
            # Now we should see either end of string, or a number (digit, -, ( )
            if i >= len(after_label):
                return True  # End of string
            
            next_char = after_label[i]
            if next_char.isdigit() or next_char in '-(':
                return True  # Followed by a number
            
            # If it's a letter, it's more words (e.g., "and liabilities")
            # So this is not a match
    return False


def _parse_profit_loss_table(table_text: str) -> dict[str, dict[str, float | None]]:
    """Parse the profit or loss statement table."""
    results = {metric: {} for metric in STATEMENT_SECTIONS["profit_or_loss"]}
    
    rows = _split_table_rows(table_text)
    
    for row in rows:
        for metric, labels in IFRS_LABELS.items():
            if metric not in STATEMENT_SECTIONS["profit_or_loss"]:
                continue
            if _match_label_in_row(row, labels) and not any(excl in row.lower() for excl in ["note", "attributable", "per share", "whereof", "comprehensive", "exchange", "basic", "earnings per share"]):
                # Profit/loss table has 4 columns (Q2, Q2 prior, H1, H1 prior)
                values = _extract_table_values(row, expected_cols=4)
                
                if len(values) >= 4:
                    results[metric]["Q2_2026"] = values[0]
                    results[metric]["Q2_2025"] = values[1]
                    results[metric]["H1_2026"] = values[2]
                    results[metric]["H1_2025"] = values[3]
                elif len(values) >= 2:
                    results[metric]["Q2_2026"] = values[0]
                    results[metric]["Q2_2025"] = values[1]
                break
    
    return results


def _parse_financial_position_table(table_text: str) -> dict[str, dict[str, float | None]]:
    """Parse the statement of financial position (balance sheet) table."""
    results = {metric: {} for metric in STATEMENT_SECTIONS["financial_position"]}
    
    rows = _split_table_rows(table_text)
    
    for row in rows:
        for metric, labels in IFRS_LABELS.items():
            if metric not in STATEMENT_SECTIONS["financial_position"]:
                continue
            if _match_label_in_row(row, labels):
                # Balance sheet has 2 columns (current, prior)
                values = _extract_table_values(row, expected_cols=2)
                
                if len(values) >= 2:
                    results[metric]["Jun_30_2026"] = values[0]
                    results[metric]["Dec_31_2025"] = values[1]
                break
    
    return results


def _parse_cash_flow_table(table_text: str) -> dict[str, dict[str, float | None]]:
    """Parse the cash flow statement table."""
    results = {metric: {} for metric in STATEMENT_SECTIONS["cash_flows"]}
    
    rows = _split_table_rows(table_text)
    
    for row in rows:
        for metric, labels in IFRS_LABELS.items():
            if metric not in STATEMENT_SECTIONS["cash_flows"]:
                continue
            if _match_label_in_row(row, labels):
                # Cash flow has 2 columns (H1, H1 prior)
                values = _extract_table_values(row, expected_cols=2)
                
                if len(values) >= 2:
                    results[metric]["H1_2026"] = values[0]
                    results[metric]["H1_2025"] = values[1]
                break
    
    return results


def _parse_changes_in_equity_table(table_text: str) -> dict[str, dict[str, float | None]]:
    """Parse the statement of changes in equity for share counts."""
    results = {metric: {} for metric in STATEMENT_SECTIONS["changes_in_equity"]}
    
    rows = _split_table_rows(table_text)
    
    for row in rows:
        for metric, labels in IFRS_LABELS.items():
            if metric not in STATEMENT_SECTIONS["changes_in_equity"]:
                continue
            if _match_label_in_row(row, labels):
                # Equity table varies, try to extract
                values = _extract_table_values(row, expected_cols=2)
                
                if values:
                    results[metric]["Jun_30_2026"] = values[0]
                    if len(values) > 1:
                        results[metric]["Jun_30_2025"] = values[1]
                break
    
    return results


def parse_sixk_financials(content: str, report_date: str | None = None) -> dict[str, Any]:
    """Parse financial data from a 6-K exhibit HTML content.
    
    Returns a structure compatible with the xbrl_parser output format.
    """
    # Find each statement table
    profit_loss_text = _find_financial_table(content, "profit_loss")
    financial_pos_text = _find_financial_table(content, "financial_position")
    cash_flow_text = _find_financial_table(content, "cash_flows")
    equity_text = _find_financial_table(content, "changes_in_equity")
    
    # Parse each table
    pl_data = _parse_profit_loss_table(profit_loss_text or "")
    fp_data = _parse_financial_position_table(financial_pos_text or "")
    cf_data = _parse_cash_flow_table(cash_flow_text or "")
    eq_data = _parse_changes_in_equity_table(equity_text or "")
    
    # Merge all data
    all_metrics = {}
    for d in [pl_data, fp_data, cf_data, eq_data]:
        for metric, periods in d.items():
            if metric not in all_metrics:
                all_metrics[metric] = {}
            all_metrics[metric].update(periods)
    
    # Determine fiscal period and year from content
    fiscal_period = "Q2"
    fiscal_year = "2026"
    
    if "three and six month period ended june 30, 2026" in content.lower():
        fiscal_period = "Q2"
        fiscal_year = "2026"
    elif "three month period ended march 31, 2026" in content.lower():
        fiscal_period = "Q1"
        fiscal_year = "2026"
    
    # Build result in xbrl_parser compatible format
    result = {
        "fiscal_period": fiscal_period,
        "fiscal_year": int(fiscal_year) if fiscal_year.isdigit() else None,
        "report_date": report_date,
        "metrics": {}
    }
    
    # Convert to the expected format with prior values
    for metric, periods in all_metrics.items():
        if not periods:
            continue
            
        # Determine current period value
        current_value = periods.get("Q2_2026") or periods.get("H1_2026") or periods.get("Jun_30_2026")
        prior_value = periods.get("Q2_2025") or periods.get("H1_2025") or periods.get("Dec_31_2025")
        prior_q_value = periods.get("Q1_2026")  # If available
        
        if current_value is not None:
            result["metrics"][metric] = {
                "value": current_value,
                "prior_value": prior_value,
                "prior_q_value": prior_q_value,
                "concept": metric,
                "context": "6K-HTML",
                "start": None,
                "end": report_date or "2026-06-30",
                "instant": metric in {"cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "consumer_receivables", "consumer_deposits"},
                "duration_days": 0 if metric in {"cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "consumer_receivables", "consumer_deposits"} else 91,
                "unit": "USD",
                "decimals": None,
                "dimensions": [],
                "taxonomy": "IFRS",
            }
    
    return result


if __name__ == "__main__":
    import sys
    with open("/tmp/klar_q2_2026_exhibit994.txt", "r") as f:
        content = f.read()
    
    result = parse_sixk_financials(content, "2026-06-30")
    import json
    print(json.dumps(result, indent=2, default=str))