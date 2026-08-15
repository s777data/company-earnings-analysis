#!/usr/bin/env python3
"""Evidence-gated valuation and ownership-risk metrics.

Metric definitions, tiers, directionality, and ranges mirror
references/VALUATION_METRICS_REFERENCE_MAIN_METRICS_REVIEW.txt. Calculations are
company-neutral and omit metrics whose denominator or source inputs are not
verified and economically meaningful.
"""
from __future__ import annotations

from typing import Any


CATALOG: dict[str, dict[str, Any]] = {
    "ps_annualized": {
        "name": "P/S (Annualized)", "group": "main", "tier": 1,
        "definition": "Market capitalization / annualized revenue.",
        "impact": "Shows how much equity investors are paying for each dollar of annualized sales. Useful when earnings are negative or too small for P/E to be meaningful.",
        "formula": "Market cap ÷ annualized revenue", "direction": "Lower is better",
        "scale": [(2, "Attractive", "positive"), (5, "Moderate", "neutral"), (10, "Expensive", "caution"), (None, "Very Expensive", "worst")],
    },
    "ev_revenue": {
        "name": "EV / Revenue", "group": "main", "tier": 1,
        "definition": "Enterprise value / total annualized revenue.",
        "impact": "Tells you how much you are paying for one dollar of total sales, adjusting for debt and cash.",
        "formula": "Enterprise value ÷ annualized revenue", "direction": "Lower is better",
        "scale": [(2, "Deep Value", "positive"), (5, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "ev_gross_profit": {
        "name": "EV / Gross Profit", "group": "main", "tier": 2,
        "definition": "Enterprise value / annualized gross profit.",
        "impact": "Shows whether the core product is profitable to make before corporate overhead and management costs.",
        "formula": "Enterprise value ÷ annualized gross profit", "direction": "Lower is better", "scale": [],
    },
    "ev_revenue_growth": {
        "name": "EV / Revenue / Growth", "group": "main", "tier": 2,
        "definition": "(EV / Revenue) / YoY Revenue Growth Rate (%).",
        "impact": "Factors sales growth into the revenue multiple, functioning like a PEG ratio for top-line sales.",
        "formula": "EV/Revenue ÷ YoY revenue growth %", "direction": "Lower is better", "scale": [],
    },
    "price_to_book": {
        "name": "Price to Book (P/B)", "group": "main", "tier": 2,
        "definition": "Market cap / total equity (or tangible book value).",
        "impact": "Shows the price paid relative to the accounting value of assets after liabilities.",
        "formula": "Market cap ÷ total equity", "direction": "Lower is better",
        "scale": [(1, "Below Book", "positive"), (3, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "forward_pe": {
        "name": "Forward P/E (NTM)", "group": "profitability", "tier": 1,
        "definition": "Current share price / consensus next-twelve-month diluted EPS.",
        "impact": "Shows the price paid today for expected next-twelve-month earnings.",
        "formula": "Share price ÷ consensus NTM diluted EPS", "direction": "Lower is better",
        "scale": [(15, "Attractive", "positive"), (25, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "trailing_pe": {
        "name": "Trailing P/E", "group": "profitability", "tier": 1,
        "definition": "Market cap / trailing net income, or share price / trailing diluted EPS.",
        "impact": "Shows the price paid for profits generated over the trailing twelve months.",
        "formula": "Market cap ÷ trailing net income", "direction": "Lower is better",
        "scale": [(15, "Attractive", "positive"), (25, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "ev_ebitda": {
        "name": "EV / EBITDA", "group": "profitability", "tier": 1,
        "definition": "Enterprise value / EBITDA.",
        "impact": "Compares the total business value with operating earning power before interest, taxes, depreciation, and amortization.",
        "formula": "Enterprise value ÷ EBITDA", "direction": "Lower is better",
        "scale": [(8, "Attractive", "positive"), (15, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "levered_fcf_yield": {
        "name": "Levered FCF Yield", "group": "profitability", "tier": 1,
        "definition": "FCF available to common equity / market cap.",
        "impact": "Shows the cash return generated for common shareholders relative to the stock's market value.",
        "formula": "Levered FCF ÷ market cap", "direction": "Higher is better",
        "scale": [(5, "Expensive", "negative"), (10, "Typical", "neutral"), (None, "Attractive", "positive")],
    },
    "peg_ratio": {
        "name": "PEG Ratio", "group": "profitability", "tier": 1,
        "definition": "P/E ratio / expected EPS growth rate (as a whole number).",
        "impact": "Tests whether an earnings multiple is justified by expected EPS growth.",
        "formula": "P/E ÷ expected EPS growth rate", "direction": "Lower is better",
        "scale": [(1, "Attractive", "positive"), (2, "Typical", "neutral"), (None, "Expensive", "negative")],
    },
    "ev_ebit": {
        "name": "EV / EBIT", "group": "profitability", "tier": 2,
        "definition": "Enterprise value / operating income.",
        "impact": "Compares total business value with core operating profit after depreciation and amortization.",
        "formula": "Enterprise value ÷ operating income", "direction": "Lower is better", "scale": [],
    },
    "ev_fcff": {
        "name": "EV / FCFF (Unlevered FCF)", "group": "profitability", "tier": 2,
        "definition": "Enterprise value / free cash flow to the firm.",
        "impact": "Shows total business value relative to cash generated for debt and equity providers.",
        "formula": "Enterprise value ÷ FCFF", "direction": "Lower is better",
        "scale": [(15, "Attractive", "positive"), (25, "Typical", "neutral"), (30, "Elevated", "caution"), (None, "Expensive", "negative")],
    },
    "normalized_multiple": {
        "name": "Normalized Multi-Year Multiple", "group": "profitability", "tier": 2,
        "definition": "3-to-5 year averaged earnings or FCF / Valuation.",
        "impact": "Smooths unusually strong and weak years to show a longer-term valuation trend.",
        "formula": "Valuation ÷ 3–5 year normalized earnings or FCF", "direction": "Lower is better", "scale": [],
    },
    "fcf_conversion": {
        "name": "FCF Conversion", "group": "profitability", "tier": 3,
        "definition": "FCF available to equity / net income.",
        "impact": "Tests whether reported accounting profits are supported by cash generation.",
        "formula": "Levered FCF ÷ net income", "direction": "Higher is better",
        "scale": [(100, "Monitor", "caution"), (None, "Excellent", "positive")],
    },
    "shareholder_yield": {
        "name": "Total Shareholder Yield", "group": "profitability", "tier": 3,
        "definition": "(Cash dividends + share repurchases - share issuance) / market cap.",
        "impact": "Measures dividends and net buybacks returned to shareholders relative to market value.",
        "formula": "(Dividends + repurchases − issuance) ÷ market cap", "direction": "Higher is better",
        "scale": [(2, "Low", "caution"), (5, "Typical", "neutral"), (None, "High", "positive")],
    },
    "ev_backlog": {
        "name": "EV / Backlog", "group": "negative", "tier": 1,
        "definition": "Enterprise value / total order backlog.",
        "impact": "Compares enterprise value with contracted future work for project-based companies.",
        "formula": "Enterprise value ÷ reported backlog", "direction": "Lower is better", "scale": [],
    },
    "short_interest_float": {
        "name": "Short Interest % of Float", "group": "risk", "tier": 1,
        "definition": "Shares sold short / public float.",
        "impact": "Shows bearish positioning and potential short-squeeze pressure.",
        "formula": "Shares sold short ÷ public float", "direction": "Lower is generally safer",
        "scale": [(5, "Low", "positive"), (10, "Moderate", "neutral"), (20, "High", "caution"), (None, "Very High", "worst")],
    },
    "days_to_cover": {
        "name": "Short Ratio / Days to Cover", "group": "risk", "tier": 1,
        "definition": "Shares sold short / average daily trading volume.",
        "impact": "Estimates how many normal trading days shorts would need to cover their positions.",
        "formula": "Shares sold short ÷ average daily volume", "direction": "Lower is generally safer",
        "scale": [(2, "Low", "positive"), (5, "Moderate", "neutral"), (10, "High", "caution"), (None, "Very High", "worst")],
    },
    "sbc_revenue": {
        "name": "SBC / Revenue", "group": "risk", "tier": 1,
        "definition": "Stock-based compensation expense / revenue.",
        "impact": "Shows how much revenue is consumed by recurring equity compensation.",
        "formula": "Stock-based compensation ÷ revenue", "direction": "Lower is better",
        "scale": [(5, "Low", "positive"), (10, "Moderate", "neutral"), (20, "High", "caution"), (None, "Very High", "worst")],
    },
    "sbc_fcf": {
        "name": "SBC / Free Cash Flow", "group": "risk", "tier": 2,
        "definition": "Stock-based compensation / reported free cash flow.",
        "impact": "Shows how dependent reported FCF is on adding back stock compensation.",
        "formula": "Stock-based compensation ÷ reported FCF", "direction": "Lower is better",
        "scale": [(20, "Strong", "positive"), (40, "Moderate", "neutral"), (75, "High", "caution"), (100, "Very High", "negative"), (None, "Exceeds FCF", "worst")],
    },
    "sbc_adjusted_fcf_yield": {
        "name": "SBC-Adjusted FCF Yield", "group": "risk", "tier": 1,
        "definition": "(Levered FCF - stock-based compensation) / market capitalization.",
        "impact": "Measures shareholder cash yield after treating SBC as an economic cost.",
        "formula": "(Levered FCF − SBC) ÷ market cap", "direction": "Higher is better",
        "scale": [(2, "Very Expensive", "worst"), (4, "Expensive", "negative"), (8, "Reasonable", "neutral"), (None, "Attractive", "positive")],
    },
    "net_share_dilution": {
        "name": "Net Share Dilution", "group": "risk", "tier": 1,
        "definition": "Percentage change in diluted shares outstanding over the period.",
        "impact": "Shows whether issuance and SBC dilute existing shareholders after buybacks.",
        "formula": "Change in diluted weighted-average shares", "direction": "Lower is better",
        "scale": [(0, "Shrinking", "positive"), (1, "Minimal", "positive"), (3, "Moderate", "neutral"), (5, "High", "caution"), (None, "Very High", "worst")],
    },
}

MAIN_ORDER = ("ps_annualized", "ev_revenue", "ev_gross_profit", "ev_revenue_growth", "price_to_book")
PROFIT_ORDER = tuple(key for tier in (1, 2, 3) for key, meta in CATALOG.items()
                     if meta["group"] == "profitability" and meta["tier"] == tier)
NEGATIVE_ORDER = ("ev_revenue", "ev_gross_profit", "ev_backlog", "ev_revenue_growth", "price_to_book")
RISK_ORDER = ("short_interest_float", "days_to_cover", "sbc_revenue", "sbc_fcf", "sbc_adjusted_fcf_yield", "net_share_dilution")


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _classification(meta: dict[str, Any], value: float | None) -> tuple[str, str]:
    if value is None:
        return "neutral", "Unavailable"
    for maximum, label, signal in meta.get("scale", []):
        if maximum is None or value < maximum:
            return signal, label
    return "neutral", "Context Only"


def _display(key: str, value: float | None) -> str:
    if value is None:
        return "N/A"
    if key in {"levered_fcf_yield", "fcf_conversion", "shareholder_yield", "short_interest_float",
               "sbc_revenue", "sbc_fcf", "sbc_adjusted_fcf_yield", "net_share_dilution"}:
        return f"{value:.1f}%"
    if key == "days_to_cover":
        return f"{value:.1f}d"
    return f"{value:.1f}x"


def _row(key: str, value: float | None, source: str, source_date: str | None = None) -> dict[str, Any]:
    meta = CATALOG[key]
    signal, assessment = _classification(meta, value)
    return {
        "key": key, "label": meta["name"], "value": value, "display": _display(key, value),
        "signal": signal, "tier": meta["tier"], "assessment": assessment,
        "definition": meta["definition"], "impact": meta["impact"], "formula": meta["formula"],
        "directionality": meta["direction"],
        "scale": [{"max": maximum, "label": label, "signal": step_signal}
                  for maximum, label, step_signal in meta.get("scale", [])],
        "source_note": source, "source_date": source_date,
    }


def build_valuation_sections(*, market_cap: float | None, enterprise_value: float | None,
                             annual_revenue: float | None, annual_gross_profit: float | None,
                             revenue_growth_pct: float | None, total_equity: float | None,
                             backlog: float | None, annual_net_income: float | None,
                             annual_fcf: float | None, annual_ebit: float | None,
                             annual_ebitda: float | None, trailing_pe: float | None,
                             forward_pe: float | None = None, peg_ratio: float | None = None,
                             fcff: float | None = None, normalized_multiple: float | None = None,
                             shareholder_distributions: float | None = None,
                             short_interest: float | None = None, public_float: float | None = None,
                             days_to_cover: float | None = None, short_interest_date: str | None = None,
                             stock_compensation: float | None = None, period_revenue: float | None = None,
                             period_fcf: float | None = None, diluted_shares: float | None = None,
                             prior_diluted_shares: float | None = None,
                             market_source: str = "Verified market data",
                             filing_source: str = "SEC filing/XBRL",
                             short_source: str = "Nasdaq official short-interest report") -> dict[str, Any]:
    """Return unique, applicable cards in guide order for the active earnings regime."""
    ev_revenue = _safe_div(enterprise_value, annual_revenue)
    values = {
        "ps_annualized": _safe_div(market_cap, annual_revenue),
        "ev_revenue": ev_revenue,
        "ev_gross_profit": _safe_div(enterprise_value, annual_gross_profit),
        "ev_revenue_growth": _safe_div(ev_revenue, revenue_growth_pct),
        "price_to_book": _safe_div(market_cap, total_equity),
        "forward_pe": forward_pe if forward_pe and forward_pe > 0 else None,
        "trailing_pe": trailing_pe if trailing_pe and trailing_pe > 0 else None,
        "ev_ebitda": _safe_div(enterprise_value, annual_ebitda),
        "levered_fcf_yield": (annual_fcf / market_cap * 100 if market_cap and annual_fcf and annual_fcf > 0 else None),
        "peg_ratio": peg_ratio if peg_ratio and peg_ratio > 0 else None,
        "ev_ebit": _safe_div(enterprise_value, annual_ebit),
        "ev_fcff": _safe_div(enterprise_value, fcff),
        "normalized_multiple": normalized_multiple if normalized_multiple and normalized_multiple > 0 else None,
        "fcf_conversion": _safe_div(annual_fcf, annual_net_income) * 100 if _safe_div(annual_fcf, annual_net_income) is not None else None,
        "shareholder_yield": (shareholder_distributions / market_cap * 100
                              if market_cap and shareholder_distributions is not None else None),
        "ev_backlog": _safe_div(enterprise_value, backlog),
        "short_interest_float": (_safe_div(short_interest, public_float) * 100
                                 if _safe_div(short_interest, public_float) is not None else None),
        "days_to_cover": days_to_cover,
        "sbc_revenue": (_safe_div(stock_compensation, period_revenue) * 100
                        if _safe_div(stock_compensation, period_revenue) is not None else None),
        "sbc_fcf": (_safe_div(stock_compensation, period_fcf) * 100
                    if _safe_div(stock_compensation, period_fcf) is not None else None),
        "sbc_adjusted_fcf_yield": ((annual_fcf - stock_compensation) / market_cap * 100
                                   if market_cap and annual_fcf is not None and stock_compensation is not None else None),
        "net_share_dilution": ((_safe_div(diluted_shares, prior_diluted_shares) - 1) * 100
                               if _safe_div(diluted_shares, prior_diluted_shares) is not None else None),
    }
    positive_regime = bool(annual_net_income and annual_net_income > 0 and annual_fcf and annual_fcf > 0)
    active_order = PROFIT_ORDER if positive_regime else NEGATIVE_ORDER
    ordered = list(MAIN_ORDER)
    ordered.extend(key for key in active_order if key not in ordered)
    market_and_filing = f"{market_source}; {filing_source}"
    valuation_rows = [_row(key, values[key], market_and_filing) for key in ordered if values.get(key) is not None]
    risk_rows = []
    for key in RISK_ORDER:
        if values.get(key) is None:
            continue
        source = short_source if key in {"short_interest_float", "days_to_cover"} else filing_source
        risk_rows.append(_row(key, values[key], source, short_interest_date if key in {"short_interest_float", "days_to_cover"} else None))
    return {
        "regime": "positive_earnings_and_fcf" if positive_regime else "negative_earnings_or_fcf",
        "regime_label": "Positive Earnings / FCF" if positive_regime else "Negative Earnings / FCF",
        "rows": valuation_rows,
        "risk_rows": risk_rows,
    }
