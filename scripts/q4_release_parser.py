#!/usr/bin/env python3
"""Parse standalone fiscal-Q4 financial tables from an official earnings release."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_MONTH_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"([0-3]?\d),\s+(20\d{2})",
    re.I,
)
_NUMBER = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$")


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _number(value: str) -> float:
    text = value.strip().replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    result = float(text)
    return -result if negative else result


def _section(text: str, start: str, end: str | None = None) -> str:
    # Releases often repeat statement titles in a table of contents. The last
    # occurrence is the actual financial statement, not the TOC entry.
    start_index = text.casefold().rfind(start.casefold())
    if start_index < 0:
        raise RuntimeError(f"Q4_RELEASE_TABLE_MISSING: {start}")
    result = text[start_index:]
    if end:
        end_index = result.casefold().find(end.casefold(), len(start))
        if end_index >= 0:
            result = result[:end_index]
    return result


def _row_values(
    section: str,
    aliases: tuple[str, ...],
    count: int = 4,
    *,
    prefer_last: bool = False,
) -> list[float]:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    normalized_aliases = {_normalized(alias) for alias in aliases}
    quarter_columns = bool(
        re.search(r"(?:first|second|third|fourth|[1-4]th)\s+qtr\.?", section, re.I)
    )
    balance_columns = bool(re.search(r"\bas\s+of\b", section, re.I))
    target_count = 5 if quarter_columns and count >= 4 else (3 if balance_columns and count == 2 else count)
    line_indices = range(len(lines) - 1, -1, -1) if prefer_last else range(len(lines))
    for index in line_indices:
        line = lines[index]
        norm_line = _normalized(line)
        # Check if line starts with any of the aliases (since values may follow on same line)
        matched = False
        for alias_norm in normalized_aliases:
            if norm_line.startswith(alias_norm):
                matched = True
                break
        if not matched:
            continue
        values: list[float] = []
        # Collect potential numeric tokens from the label line and subsequent lines
        # SEC releases often split "$" and "898,185" across lines
        tokens: list[str] = []
        # From label line (skip label)
        parts = line.split()
        tokens.extend(parts[1:])
        # From subsequent lines
        for candidate in lines[index + 1:index + 40]:
            if not candidate:
                continue
            # Don't stop at next label row
            cand_norm = _normalized(candidate)
            if any(cand_norm.startswith(a) for a in normalized_aliases) and cand_norm != norm_line:
                break
            tokens.extend(candidate.split())
        # Now parse tokens for numbers
        for token in tokens:
            compact = token.replace("$", "").replace(",", "").strip()
            if compact in {"—", "-", "$", "%", ""}:
                continue
            if re.fullmatch(r"\([1-9]\)", compact):
                continue
            if _NUMBER.fullmatch(compact):
                values.append(_number(compact))
                if len(values) == target_count:
                    if quarter_columns and count >= 4:
                        return [values[0], values[2], values[3], values[4]]
                    if balance_columns and count == 2:
                        return [values[0], values[2]]
                    return values
            elif values:
                break
        if len(values) == target_count:
            if quarter_columns and count >= 4:
                return [values[0], values[2], values[3], values[4]]
            if balance_columns and count == 2:
                return [values[0], values[2]]
            return values
        break
    raise RuntimeError(f"Q4_RELEASE_ROW_MISSING: {' / '.join(aliases)}")


def _iso_date(month: str, day: str, year: str) -> str:
    return datetime.strptime(f"{month} {day}, {year}", "%B %d, %Y").date().isoformat()


def _prior_year_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    try:
        return parsed.replace(year=parsed.year - 1).isoformat()
    except ValueError:
        return parsed.replace(year=parsed.year - 1, day=28).isoformat()


def extract_fiscal_year(content: str) -> int | None:
    """Extract an explicit fiscal year from common earnings-release wording.

    The release parser must remain evidence-gated: this helper only accepts
    year-bearing labels in the release text and never infers a fiscal year from
    the ticker or from an arbitrary calendar date.
    """
    if not content:
        return None
    patterns = (
        r"\bfiscal\s+year\s+(20\d{2})\b",
        r"\bfull\s+year\s+(20\d{2})\b",
        r"\bfy\s*[-/]?\s*(20\d{2})\b",
        r"\bq[1-4]\s+(?:fy\s*)?(20\d{2})\b",
        r"\b(?:first|second|third|fourth)\s+quarter\s+(?:of\s+)?(?:fiscal\s+)?(?:year\s+)?(20\d{2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, content, re.I)
        if match:
            return int(match.group(1))
    return None


_STATEMENT_TITLE_ALIASES = {
    "balance": (
        "condensed consolidated balance sheets",
        "consolidated balance sheets",
        "balance sheets",
        "consolidated statements of financial position",
        "statements of financial position",
    ),
    "operations": (
        "condensed consolidated statements of operations and comprehensive income (loss)",
        "consolidated statements of operations and comprehensive income (loss)",
        "condensed consolidated statements of operations",
        "consolidated statements of operations",
        "statements of operations and comprehensive income (loss)",
        "statements of operations",
    ),
    "cash_flows": (
        "condensed consolidated statements of cash flows",
        "consolidated statements of cash flows",
        "statements of cash flows",
    ),
}


def find_statement_titles(content: str) -> dict[str, tuple[int, str]]:
    """Locate one ordered statement sequence using issuer-neutral title aliases."""
    normalized = (content or "").casefold()
    candidates: dict[str, list[tuple[int, str]]] = {}
    for section, aliases in _STATEMENT_TITLE_ALIASES.items():
        positions: dict[int, str] = {}
        for alias in aliases:
            for match in re.finditer(re.escape(alias.casefold()), normalized):
                current = positions.get(match.start())
                if current is None or len(alias) > len(current):
                    positions[match.start()] = alias
        candidates[section] = sorted(
            positions.items(), key=lambda item: item[0]
        )

    return {
        section: items[-1]
        for section, items in candidates.items()
        if items
    }


def parse_q4_release_financials(
    content: str,
    *,
    ticker: str,
    fiscal_year: int | None,
    report_date: str,
    period_start: str,
    source_url: str,
    fiscal_period: str = "Q4",
) -> dict[str, Any]:
    """Return standalone three-month facts from an SEC/official release.

    Historically used for Q4 standalone earnings releases, but the parser is
    now generalized so it can also parse Q1/Q2/Q3 earnings releases when the
    filing source is an 8-K exhibit instead of a 10-Q/10-K.
    """
    if not content or len(content) < 100:
        raise RuntimeError("QUARTER_RELEASE_UNAVAILABLE: official release text is empty")

    period = fiscal_period.upper()
    quarter_terms = {
        "Q1": "first quarter",
        "Q2": "second quarter",
        "Q3": "third quarter",
        "Q4": "fourth quarter",
    }
    if period not in quarter_terms:
        raise RuntimeError(f"QUARTER_RELEASE_PERIOD_INVALID: {period}")

    lower = content.casefold()
    if period.casefold() not in lower and quarter_terms[period] not in lower:
        raise RuntimeError(f"QUARTER_RELEASE_PERIOD_MISMATCH: {period} identity is absent")

    inferred_year = fiscal_year if fiscal_year is not None else extract_fiscal_year(content)
    if inferred_year is None:
        raise RuntimeError("QUARTER_RELEASE_YEAR_MISMATCH: fiscal year identity is absent")
    if extract_fiscal_year(content) != inferred_year:
        raise RuntimeError("QUARTER_RELEASE_YEAR_MISMATCH: fiscal year identity is absent")

    date_matches = {_iso_date(*match.groups()) for match in _MONTH_DATE.finditer(content[:12000])}
    if report_date not in date_matches:
        raise RuntimeError(f"QUARTER_RELEASE_PERIOD_MISMATCH: release does not identify period end {report_date}")

    lower_content = content.casefold()
    titles = find_statement_titles(content)
    for section in ("balance", "operations", "cash_flows"):
        if section not in titles:
            canonical = _STATEMENT_TITLE_ALIASES[section][0]
            raise RuntimeError(f"Q4_RELEASE_TABLE_MISSING: {canonical}")

    title_positions = sorted(
        (title_data[0], section)
        for section, title_data in titles.items()
    )
    sections: dict[str, str] = {}
    for offset, (start_index, section) in enumerate(title_positions):
        end_index = title_positions[offset + 1][0] if offset + 1 < len(title_positions) else len(content)
        sections[section] = content[start_index:end_index]
    balance = sections["balance"]
    operations = sections["operations"]
    cash_flows = sections["cash_flows"]
    quarter_scope_pattern = re.compile(
        r"three\s+months?\s+ended|(?:first|second|third|fourth|[1-4]th)\s+qtr\.?|quarter\s+ended",
        re.I,
    )
    if not quarter_scope_pattern.search(operations[:1500]):
        raise RuntimeError("QUARTER_RELEASE_SCOPE_MISMATCH: explicit three-month tables are required")
    cash_flows_have_quarter_scope = bool(quarter_scope_pattern.search(cash_flows[:1500]))

    rows: dict[str, tuple[tuple[str, ...], str, float]] = {
        "revenue": (("Revenue",), "Revenue", 1000.0),
        "gross_profit": (("Gross profit", "Gross margin"), "GrossProfit", 1000.0),
        "operating_income": (("Operating income", "Loss from operations", "Income from operations", "Income (loss) from operations"), "OperatingIncomeLoss", 1000.0),
        "net_income": (("Net loss", "Net income", "Net income (loss)"), "NetIncomeLoss", 1000.0),
        "eps_diluted": (
            ("Net loss per share, basic and diluted", "Net income per share, basic and diluted", "Net income (loss) per share, basic and diluted", "Diluted"),
            "EarningsPerShareDiluted",
            1.0,
        ),
        "shares_diluted": (
            ("Weighted-average shares used in computing net loss per share, basic and diluted", "Weighted-average shares used in computing net income per share, basic and diluted", "Weighted-average shares used in computing net income (loss) per share, diluted", "Diluted"),
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            1000.0,
        ),
        "depreciation_amortization": (("Depreciation and amortization expense", "Depreciation and amortization"), "DepreciationDepletionAndAmortization", 1000.0),
        "stock_based_compensation": (("Stock-based compensation expense",), "ShareBasedCompensation", 1000.0),
    }
    cash_rows: dict[str, tuple[tuple[str, ...], str, float]] = {
        "operating_cash_flow": (("Net cash provided by operating activities",), "NetCashProvidedByUsedInOperatingActivities", 1000.0),
    }
    balance_rows: dict[str, tuple[tuple[str, ...], str, float]] = {
        "cash": (("Cash and cash equivalents", "Cash and equivalents"), "CashAndCashEquivalentsAtCarryingValue", 1000.0),
        "total_assets": (("Total assets",), "Assets", 1000.0),
        "total_liabilities": (("Total liabilities",), "Liabilities", 1000.0),
        "total_equity": (("Total stockholders’ equity", "Total stockholders' equity", "Total equity"), "StockholdersEquity", 1000.0),
        "long_term_debt": (("Long-term debt",), "LongTermDebtNoncurrent", 1000.0),
    }

    prior_end = _prior_year_date(report_date)
    metrics: dict[str, dict[str, Any]] = {}
    optional_metrics = {"depreciation_amortization", "stock_based_compensation", "long_term_debt"}
    for metric, (aliases, concept, scale) in rows.items():
        try:
            current, prior, _, _ = _row_values(
                operations,
                aliases,
                prefer_last=metric == "shares_diluted",
            )
        except RuntimeError:
            if metric in optional_metrics:
                continue
            raise
        metrics[metric] = {
            "value": current * scale,
            "prior_value": prior * scale,
            "prior_end": prior_end,
            "concept": concept,
            "context": "official_release_three_months",
            "start": period_start,
            "end": report_date,
            "instant": False,
            "duration_days": (date.fromisoformat(report_date) - date.fromisoformat(period_start)).days + 1,
            "unit": "USD/shares" if metric == "eps_diluted" else ("shares" if metric == "shares_diluted" else "USD"),
            "decimals": None,
            "dimensions": [],
            "taxonomy": "official-release",
            "period_scope": "quarter",
            "source": "SEC 8-K Exhibit 99.1",
            "url": source_url,
        }
    for metric, (aliases, concept, scale) in cash_rows.items():
        if not cash_flows_have_quarter_scope:
            continue
        current, prior, _, _ = _row_values(cash_flows, aliases)
        metrics[metric] = {
            "value": current * scale,
            "prior_value": prior * scale,
            "prior_end": prior_end,
            "concept": concept,
            "context": "official_release_three_months",
            "start": period_start,
            "end": report_date,
            "instant": False,
            "duration_days": (date.fromisoformat(report_date) - date.fromisoformat(period_start)).days + 1,
            "unit": "USD",
            "decimals": None,
            "dimensions": [],
            "taxonomy": "official-release",
            "period_scope": "quarter",
            "source": "SEC 8-K Exhibit 99.1",
            "url": source_url,
        }

    for metric, (aliases, concept, scale) in balance_rows.items():
        try:
            current, prior = _row_values(balance, aliases, count=2)
        except RuntimeError:
            if metric == "long_term_debt":
                continue
            raise
        metrics[metric] = {
            "value": current * scale,
            "prior_value": prior * scale,
            "prior_end": prior_end,
            "concept": concept,
            "context": "official_release_balance_sheet",
            "start": report_date,
            "end": report_date,
            "instant": True,
            "duration_days": 0,
            "unit": "USD",
            "decimals": None,
            "dimensions": [],
            "taxonomy": "official-release",
            "period_scope": "instant",
            "source": "SEC 8-K Exhibit 99.1",
            "url": source_url,
        }

    if cash_flows_have_quarter_scope:
        pp_e = _row_values(cash_flows, ("Purchases of property, equipment and other assets", "Purchases of property and equipment"))
        try:
            software = _row_values(cash_flows, ("Capitalized internal-use software", "Capitalized internal use software"))
        except RuntimeError:
            software = [0.0, 0.0, 0.0, 0.0]
        metrics["capex"] = {
            "value": (abs(pp_e[0]) + abs(software[0])) * 1000.0,
            "prior_value": (abs(pp_e[1]) + abs(software[1])) * 1000.0,
            "prior_end": prior_end,
            "concept": "PurchasesOfPropertyPlantAndEquipmentPlusCapitalizedInternalUseSoftware",
            "context": "official_release_three_months",
            "start": period_start,
            "end": report_date,
            "instant": False,
            "duration_days": (date.fromisoformat(report_date) - date.fromisoformat(period_start)).days + 1,
            "unit": "USD",
            "decimals": None,
            "dimensions": [],
            "taxonomy": "official-release-derived",
            "period_scope": "quarter",
            "source": "SEC 8-K Exhibit 99.1 (derived)",
            "url": source_url,
            "components": {
                "property_equipment": abs(pp_e[0]) * 1000.0,
                "capitalized_internal_use_software": abs(software[0]) * 1000.0,
            },
        }
    return {
        "fiscal_period": period,
        "fiscal_year": str(inferred_year),
        "report_date": report_date,
        "metrics": metrics,
        "source_url": source_url,
        "source_type": "official_standalone_quarter_release",
        "ticker": ticker.upper(),
    }
