#!/usr/bin/env python3
"""Evidence-gated company earnings analysis pipeline."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from create_interactive_dashboard import create_interactive_dashboard
from render_interactive_dashboard_pdf import render_dashboard_pdf
from robinhood_mcp_get_quote import get_quote
from nasdaq_short_interest import fetch_short_interest
from valuation_metrics import build_valuation_sections
from sec_edgar_fetch import fetch_filing
from sec_edgar_search import search_filings
from telegram_notify import deliver_reports, generate_call_message, generate_dashboard_message
from web_search import find_transcript, fetch_forward_pe_ntm
from xbrl_parser import parse_xbrl_financials
from analysis_enrichment import (
    build_capital_liquidity,
    classify_financial_signal,
    classify_valuation_signal,
    extract_risks,
    extract_transcript_sections,
)


def _signal(item: dict[str, Any]) -> str:
    return item.get("signal") or item.get("tier") or "neutral"

LABELS = {"revenue": "Revenue", "gross_profit": "Gross Profit", "operating_income": "Operating Income",
          "net_income": "Net Income", "eps_diluted": "Diluted EPS", "operating_cash_flow": "Operating Cash Flow",
          "capex": "Capital Expenditures", "stock_based_compensation": "Stock-Based Compensation",
          "depreciation_amortization": "Depreciation & Amortization", "backlog": "Backlog",
          "cash": "Cash", "total_assets": "Total Assets",
          "total_liabilities": "Total Liabilities", "total_equity": "Total Equity", "long_term_debt": "Long-term Debt",
          "shares_diluted": "Diluted Shares"}

SCENARIO_WEIGHTS = {"base_case": 0.50, "bull_case": 0.30, "bear_case": 0.20}
HURDLE_RATE = 0.12


def _now() -> datetime: return datetime.now(timezone.utc)

def _validate_transcript_call_date(call_date: str | None, report_date: str) -> tuple[str | None, str | None]:
    if not call_date: return None, None
    try:
        call_day = datetime.fromisoformat(call_date).date(); report_day = datetime.fromisoformat(report_date).date()
    except ValueError:
        return None, "Transcript provider call date was invalid; displayed as N/A"
    if call_day < report_day or call_day > report_day + timedelta(days=120):
        return None, f"Transcript provider call date {call_date} failed report-date consistency validation; displayed as N/A"
    return call_date, None

def _days_old(value: str) -> int: return (_now().date() - datetime.fromisoformat(value).date()).days

def _display(value: float, metric: str) -> str:
    if "eps" in metric: return f"${value:.2f}"
    if "shares" in metric:
        return f"{value / 1e9:.2f}B" if abs(value) >= 1e9 else f"{value / 1e6:.1f}M"
    sign = "-" if value < 0 else ""; absolute = abs(value)
    if absolute >= 1e9: return f"{sign}${absolute / 1e9:.2f}B"
    if absolute >= 1e6: return f"{sign}${absolute / 1e6:.1f}M"
    return f"{sign}${absolute:,.0f}"

def _change(current: float, prior: float | None) -> float | None:
    return None if prior in (None, 0) else (current - prior) / abs(prior)


def _change_qoq(current: float, prior_q: float | None) -> float | None:
    """Calculate quarter-over-quarter change."""
    return None if prior_q in (None, 0) else (current - prior_q) / abs(prior_q)


def _tier(change: float | None, inverse: bool = False) -> str:
    if change is None: return "medium"
    adjusted = -change if inverse else change
    return "best" if adjusted >= 0.10 else "worst" if adjusted < 0 else "medium"


# Grade mapping for 75th percentile calculation
GRADE_SCALE = {
    "A+": 13, "A": 12, "A-": 11,
    "B+": 10, "B": 9, "B-": 8,
    "C+": 7, "C": 6, "C-": 5,
    "D+": 4, "D": 3, "D-": 2,
    "F": 1,
}
GRADE_SCALE_REV = {v: k for k, v in GRADE_SCALE.items()}


def _letter_to_score(letter: str) -> int:
    """Convert letter grade to numeric score for percentile calculation."""
    return GRADE_SCALE.get(letter, 0)


def _score_to_letter(score: int) -> str:
    """Convert numeric score back to letter grade."""
    return GRADE_SCALE_REV.get(score, "F")


def _percentile_75(values: list[int]) -> int:
    """Calculate 75th percentile of a list of numeric values."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    # 75th percentile index (0-indexed)
    idx = min(n - 1, int((n - 1) * 0.75))
    return sorted_vals[idx]


def _grade_financial_metrics(data: dict[str, Any]) -> tuple[str, str]:
    """Grade financial metrics: revenue growth, profitability, cash flow, margins."""
    financials = data.get("financials", {})
    rows = financials.get("rows", [])
    changes = {row["key"]: _change(row["value"], row.get("prior_value")) for row in rows}
    
    # Count positive/negative changes in core metrics
    core_keys = ("revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "eps_diluted")
    positive = sum(1 for k in core_keys if changes.get(k) is not None and changes[k] > 0.10)
    negative = sum(1 for k in core_keys if changes.get(k) is not None and changes[k] < 0)
    neutral = sum(1 for k in core_keys if changes.get(k) is not None and 0 <= changes[k] <= 0.10)
    
    # Key ratios: margins
    margins = financials.get("key_ratios", [])
    margin_improving = sum(1 for m in margins if m.get("key") in ("gross_margin", "operating_margin", "net_margin") and m.get("value", 0) > 0.15)
    
    if positive >= 4 and negative == 0 and margin_improving >= 2:
        return "A+", "Exceptional growth across revenue, profit, and cash flow with expanding margins"
    if positive >= 3 and negative == 0:
        return "A", "Strong growth in most core metrics with healthy profitability"
    if positive >= 2 and negative <= 1:
        return "A-", "Solid growth in key metrics, minor softness in one area"
    if positive >= 2 and negative == 0:
        return "B+", "Good growth in multiple metrics, margins stable"
    if positive >= 1 and negative <= 1:
        return "B", "Mixed but net positive financial performance"
    if positive >= 1 and negative >= 2:
        return "B-", "Growth offset by notable weakness in some metrics"
    if positive == 0 and negative <= 1:
        return "C+", "Flat performance with stable margins"
    if positive == 0 and negative == 2:
        return "C", "Stagnant growth with some declining metrics"
    if negative >= 3:
        return "C-", "Multiple metrics declining"
    if negative >= 4:
        return "D", "Broad-based deterioration in financial metrics"
    return "D-", "Severe financial weakness across the board"


def _grade_valuation(data: dict[str, Any]) -> tuple[str, str]:
    """Grade valuation: P/E, EV/EBITDA, FCF yield vs. growth and quality."""
    valuation = data.get("valuation", {})
    regime = valuation.get("regime", "")
    rows = valuation.get("rows", [])
    
    # Find key valuation metrics
    pe_row = next((r for r in rows if "P/E" in r.get("label", "") or "pe_ttm" in r.get("key", "")), None)
    fcf_row = next((r for r in rows if "FCF" in r.get("label", "")), None)
    ev_ebitda_row = next((r for r in rows if "EBITDA" in r.get("label", "")), None)
    ps_row = next((r for r in rows if "P/S" in r.get("label", "")), None)
    
    pe_signal = _signal(pe_row) if pe_row else "neutral"
    fcf_signal = _signal(fcf_row) if fcf_row else "neutral"
    ev_signal = _signal(ev_ebitda_row) if ev_ebitda_row else "neutral"
    ps_signal = _signal(ps_row) if ps_row else "neutral"
    
    positive_signals = sum(1 for s in (pe_signal, fcf_signal, ev_signal, ps_signal) if s in ("best", "strong_positive", "positive"))
    negative_signals = sum(1 for s in (pe_signal, fcf_signal, ev_signal, ps_signal) if s in ("negative", "worst"))
    
    if regime == "positive_earnings_and_fcf":
        if positive_signals >= 3:
            return "A+", "Attractive valuation across P/E, FCF yield, and EV/EBITDA for quality growth"
        if positive_signals >= 2:
            return "A", "Reasonable valuation with strong cash generation"
        if positive_signals >= 1 and negative_signals == 0:
            return "A-", "Fair valuation, one metric slightly rich"
        if positive_signals == 1 and negative_signals <= 1:
            return "B+", "Moderate valuation, mixed signals"
        if positive_signals == 0 and negative_signals <= 1:
            return "B", "Full valuation but supported by profitability"
        if negative_signals >= 2:
            return "B-", "Rich valuation on multiple metrics"
        if negative_signals >= 3:
            return "C", "Expensive across P/E, EV/EBITDA, and FCF yield"
        return "C-", "Very expensive for the growth profile"
    else:
        # Negative earnings/FCF regime
        if negative_signals <= 1:
            return "B", "Speculative valuation but not extreme"
        if negative_signals == 2:
            return "B-", "Elevated price/sales for pre-profit company"
        if negative_signals == 3:
            return "C", "High multiples without earnings support"
        return "C-", "Very high speculative valuation"


def _grade_earnings_call(data: dict[str, Any]) -> tuple[str, str]:
    """Grade earnings call: prepared remarks quality, Q&A substance, guidance clarity."""
    insights = data.get("transcript_insights", [])
    if not insights:
        return "C", "No transcript insights available"
    
    # Count positive/negative insights from management (not analysts)
    mgmt_insights = [i for i in insights if i.get("section") in ("Prepared Remarks", "Analyst Q&A")]
    positive = sum(1 for i in mgmt_insights if _signal(i) in ("best", "strong_positive", "positive"))
    negative = sum(1 for i in mgmt_insights if _signal(i) in ("negative", "worst"))
    neutral = sum(1 for i in mgmt_insights if _signal(i) in ("neutral", "medium"))
    
    # Check for guidance
    guidance = data.get("guidance", {}).get("rows", [])
    has_guidance = len(guidance) > 0
    
    # Check management tone
    tone_insight = next((i for i in insights if i.get("topic") == "Management Tone"), None)
    tone_positive = tone_insight and _signal(tone_insight) in ("best", "strong_positive", "positive")
    
    if positive >= 4 and negative == 0 and tone_positive and has_guidance:
        return "A+", "Highly confident tone, clear guidance, substantive positive Q&A"
    if positive >= 3 and negative <= 1 and tone_positive:
        return "A", "Confident management, good guidance, mostly positive discussion"
    if positive >= 2 and negative <= 1 and has_guidance:
        return "A-", "Solid call with guidance, minor caution in Q&A"
    if positive >= 2 and negative <= 2:
        return "B+", "Balanced call with adequate guidance"
    if positive >= 1 and negative <= 2:
        return "B", "Mixed tone, guidance present but not compelling"
    if positive == 0 and negative <= 1:
        return "B-", "Neutral call, limited forward-looking commentary"
    if positive == 0 and negative >= 2:
        return "C+", "Cautious tone, guidance vague or absent"
    if negative >= 3:
        return "C", "Negative tone, weak or no guidance"
    return "C-", "Evasive or concerning management commentary"


def _grade_management_execution(data: dict[str, Any]) -> tuple[str, str]:
    """Grade confidence in management execution: capital allocation, buybacks, margin trends, guidance track record."""
    financials = data.get("financials", {})
    rows = financials.get("rows", [])
    by_key = {row["key"]: row for row in rows}
    
    # Share count trend (buybacks)
    shares = by_key.get("shares_diluted", {})
    shares_change = _change(shares.get("value"), shares.get("prior_value"))
    buyback_positive = shares_change is not None and shares_change < -0.01
    
    # Operating cash flow vs net income (earnings quality)
    ocf = by_key.get("operating_cash_flow", {})
    ni = by_key.get("net_income", {})
    ocf_vs_ni = None
    if ocf.get("value") and ni.get("value") and ni["value"] != 0:
        ocf_vs_ni = ocf["value"] / ni["value"]
    high_quality = ocf_vs_ni is not None and ocf_vs_ni > 1.1
    
    # Margin trends
    margins = financials.get("key_ratios", [])
    margin_improving = sum(1 for m in margins if m.get("key") in ("gross_margin", "operating_margin", "net_margin") and m.get("value", 0) > 0)
    
    # Debt management
    debt = by_key.get("long_term_debt", {})
    debt_change = _change(debt.get("value"), debt.get("prior_value"))
    debt_decreasing = debt_change is not None and debt_change < -0.05
    
    # Capital allocation signals from call
    cap_alloc_insight = next((i for i in data.get("transcript_insights", []) if i.get("topic") == "Capital Allocation"), None)
    cap_alloc_positive = bool(cap_alloc_insight and _signal(cap_alloc_insight) in ("best", "strong_positive", "positive"))
    
    positives = sum([buyback_positive, high_quality, margin_improving >= 2, debt_decreasing, cap_alloc_positive])
    
    if positives >= 4:
        return "A+", "Buybacks, high earnings quality, expanding margins, debt reduction, disciplined capital allocation"
    if positives >= 3:
        return "A", "Strong execution on multiple fronts: buybacks, quality earnings, margin improvement"
    if positives >= 2:
        return "A-", "Good execution with buybacks or quality earnings, minor gap in one area"
    if positives == 2:
        return "B+", "Solid execution: quality earnings and stable margins"
    if positives == 1:
        return "B", "Adequate execution, one clear positive signal"
    if positives == 0:
        return "B-", "Neutral execution, no strong signals either way"
    if not buyback_positive and not high_quality:
        return "C+", "No buybacks, earnings quality concerns, flat margins"
    if not buyback_positive and not high_quality and not debt_decreasing:
        return "C", "Share dilution, low earnings quality, rising debt"
    return "C-", "Poor capital allocation, deteriorating quality, leverage increasing"


def _grade_future_growth(data: dict[str, Any]) -> tuple[str, str]:
    """Grade future growth: backlog, guidance, pipeline, market opportunity, secular trends."""
    financials = data.get("financials", {})
    rows = financials.get("rows", [])
    by_key = {row["key"]: row for row in rows}
    
    # Backlog growth
    backlog = by_key.get("backlog", {})
    backlog_change = _change(backlog.get("value"), backlog.get("prior_value"))
    backlog_growing = backlog_change is not None and backlog_change > 0.10
    
    # Revenue growth rate
    revenue = by_key.get("revenue", {})
    rev_change = _change(revenue.get("value"), revenue.get("prior_value"))
    high_growth = rev_change is not None and rev_change > 0.20
    mid_growth = rev_change is not None and rev_change > 0.10
    
    # Guidance from call
    guidance = data.get("guidance", {}).get("rows", [])
    guidance_positive = len(guidance) > 0
    
    # Revenue & Demand insight
    demand_insight = next((i for i in data.get("transcript_insights", []) if i.get("topic") == "Revenue & Demand"), None)
    demand_positive = bool(demand_insight and _signal(demand_insight) in ("best", "strong_positive", "positive"))
    
    # Products & Innovation
    product_insight = next((i for i in data.get("transcript_insights", []) if i.get("topic") == "Products & Innovation"), None)
    product_positive = bool(product_insight and _signal(product_insight) in ("best", "strong_positive", "positive"))
    
    # Strategic pillars (durable themes)
    pillars = data.get("strategic_pillars", [])
    strong_pillars = len(pillars) >= 3
    
    positives = sum([backlog_growing, high_growth, mid_growth, guidance_positive, demand_positive, product_positive, strong_pillars])
    
    if positives >= 5:
        return "A+", "Explosive growth trajectory: backlog expanding, >20% revenue growth, strong pipeline, clear secular tailwinds"
    if positives >= 4:
        return "A", "Strong growth outlook: high revenue growth, backlog building, positive guidance"
    if positives >= 3:
        return "A-", "Solid growth prospects: double-digit growth, visible pipeline, good guidance"
    if positives >= 2:
        return "B+", "Moderate growth with clear catalysts"
    if positives >= 1:
        return "B", "Steady growth, some visibility"
    if positives == 0:
        return "B-", "Low growth, limited visibility"
    if not high_growth and not backlog_growing and not demand_positive:
        return "C+", "Growth decelerating, no clear catalysts"
    if not mid_growth and not demand_positive and not product_positive:
        return "C", "Stagnant growth, weak pipeline"
    return "C-", "Structural growth challenges, declining demand signals"


def _citation(source: str, url: str, start: int | None = None, end: int | None = None, **extra) -> dict:
    return {"source": source, "url": url, "start": start, "end": end, **extra}


def _snippet(text: str, pattern: str, radius: int = 180) -> tuple[str, int, int] | None:
    match = re.search(pattern, text, re.I)
    if not match: return None
    start, end = max(0, match.start() - radius), min(len(text), match.end() + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip(), start, end


class EarningsAnalyzer:
    def __init__(self, ticker: str, max_filing_age_days: int = 120, output_format: str = "both",
                 expected_account: str | None = None, allow_stale_quote_for_test: bool = False):
        self.ticker = ticker.upper(); self.max_age = max_filing_age_days; self.output_format = output_format
        self.expected_account = expected_account; self.allow_stale_quote_for_test = allow_stale_quote_for_test
        self.data: dict[str, Any] = {"ticker": self.ticker, "warnings": [], "test_run": allow_stale_quote_for_test}
        self.filing: dict[str, Any] = {}; self.release: dict[str, Any] | None = None; self.transcript: dict[str, Any] = {}
        self.release_candidates: list[dict[str, Any]] = []

    def identify(self):
        filings = search_filings(self.ticker, ["10-Q", "10-Q/A"], limit=20)
        if not filings: raise RuntimeError("NO_FILINGS: no quarterly SEC filing was found")
        filings = [row for row in filings if row.get("report_date") and row["report_date"] <= _now().date().isoformat()]
        if not filings: raise RuntimeError("NO_FILINGS: no completed non-future quarterly filing was found")
        self.filing = max(filings, key=lambda row: (row["report_date"], row["filing_date"], row["form_type"].endswith("/A")))
        earnings_8k = search_filings(self.ticker, ["8-K"], query="earnings", limit=8)
        self.release_candidates = earnings_8k
        nearest = min(earnings_8k, key=lambda row: abs((datetime.fromisoformat(row["filing_date"]) - datetime.fromisoformat(self.filing["filing_date"])).days), default=None)
        freshest = min(_days_old(self.filing["filing_date"]), _days_old(nearest["filing_date"]) if nearest else 10**6)
        if freshest > self.max_age: raise RuntimeError(f"STALE_DATA: newest verified earnings evidence is {freshest} days old")

    def retrieve(self):
        filing_doc = fetch_filing(self.filing["accession_number"], self.filing["cik"], self.filing["primary_document"], include_exhibits=False)
        if not filing_doc.get("xbrl_content"): raise RuntimeError("XBRL_UNAVAILABLE: quarterly structured financial data was not found")
        xbrl = parse_xbrl_financials(filing_doc["xbrl_content"], self.filing.get("report_date"))
        period = (xbrl.get("fiscal_period") or "").upper(); year_text = xbrl.get("fiscal_year")
        if period not in {"Q1", "Q2", "Q3"}: raise RuntimeError(f"FISCAL_PERIOD_UNVERIFIED: SEC XBRL reported {period or 'no period'}")
        if not year_text: raise RuntimeError("FISCAL_YEAR_UNVERIFIED: SEC XBRL did not provide DocumentFiscalYearFocus")
        report_date = xbrl.get("report_date") or self.filing.get("report_date")
        if not report_date: raise RuntimeError("REPORT_DATE_UNVERIFIED")
        self.transcript = find_transcript(self.ticker, period, int(year_text))
        transcript_call_date, call_date_warning = _validate_transcript_call_date(self.transcript.get("call_date"), report_date)
        if call_date_warning:
            self.data["warnings"].append(call_date_warning)
        release_doc = None; scored_releases = []
        for candidate in self.release_candidates:
            if abs((datetime.fromisoformat(candidate["filing_date"]) - datetime.fromisoformat(self.filing["filing_date"])).days) > 60: continue
            candidate_doc = fetch_filing(candidate["accession_number"], candidate["cik"], candidate["primary_document"], include_exhibits=True)
            release_text = "\n".join(candidate_doc.get("exhibit_content", {}).values())
            normalized = release_text.lower()
            period_evidence = report_date in normalized or (period.lower() in normalized and str(year_text) in normalized)
            if not release_text or not period_evidence: continue
            score = (3 if "2.02" in candidate.get("items", "") else 0) + (2 if report_date in normalized else 0) + 1
            scored_releases.append((score, candidate["filing_date"], candidate, candidate_doc, release_text))
        if scored_releases:
            scored_releases.sort(key=lambda item: (item[0], item[1]), reverse=True)
            if len(scored_releases) > 1 and scored_releases[0][:2] == scored_releases[1][:2]:
                self.data["warnings"].append("Multiple equally strong earnings 8-K candidates; release omitted as ambiguous")
            else:
                _, _, self.release, release_doc, release_text = scored_releases[0]
        if not release_doc: self.data["warnings"].append("No quarter-matched earnings 8-K exhibit was verified")
        self.data.update({"fiscal_period": period, "fiscal_year": int(year_text), "report_date": report_date,
                          "filing_date": self.filing["filing_date"], "accession_number": self.filing["accession_number"],
                          "sources": {"filing_url": filing_doc["filing_url"], "xbrl_url": filing_doc["xbrl_url"],
                                      "earnings_release_url": release_doc["filing_url"] if release_doc else None,
                                      "transcript_url": self.transcript["url"], "transcript_provider": self.transcript["source"],
                                      "transcript_call_date": transcript_call_date,
                                      "transcript_retrieved_at": self.transcript["retrieved_at"],
                                      "transcript_content_sha256": self.transcript["content_sha256"]},
                          "_xbrl": xbrl, "_filing_text": filing_doc["content"],
                          "_release_text": release_text if release_doc else ""})

    def financials(self):
        rows = []; metrics = self.data["_xbrl"]["metrics"]
        tier1_metrics = {"revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "capex", "stock_based_compensation", "depreciation_amortization", "eps_diluted", "backlog", "cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "shares_diluted"}
        for name, fact in metrics.items():
            value, prior = fact["value"], fact.get("prior_value"); change = _change(value, prior)
            prior_q = fact.get("prior_q_value")
            change_qoq = _change_qoq(value, prior_q)
            comparison_parts = []
            if change is not None:
                comparison_parts.append(f"{change:+.1%} YoY")
            if change_qoq is not None:
                comparison_parts.append(f"{change_qoq:+.1%} QoQ")
            comparison = ", ".join(comparison_parts) if comparison_parts else "prior-year comparison unavailable"
            signal = classify_financial_signal(name, change)
            row_data = {"key": name, "label": LABELS.get(name, name), "value": value, "display": _display(value, name),
                         "prior_value": prior, "comparison": comparison, "signal": signal, "tier": signal,
                         "citation": _citation("SEC XBRL", self.data["sources"]["xbrl_url"], concept=fact["concept"],
                                               taxonomy=fact.get("taxonomy"), context=fact["context"], dimensions=fact.get("dimensions", []),
                                               unit=fact.get("unit"), decimals=fact.get("decimals"),
                                               period_start=fact["start"], period_end=fact["end"])}
            if prior_q is not None:
                row_data["prior_q_value"] = prior_q
                row_data["change_qoq"] = change_qoq
            rows.append(row_data)
        if not any(row["key"] == "revenue" for row in rows): raise RuntimeError("FINANCIAL_DATA_INCOMPLETE: revenue was not extracted")
        by_key = {row["key"]: row for row in rows}
        key_ratios = []
        revenue_value = by_key["revenue"]["value"]
        for key, label in (("gross_profit", "Gross Margin"), ("operating_income", "Operating Margin"), ("net_income", "Net Margin")):
            numerator = by_key.get(key, {}).get("value")
            if revenue_value and numerator is not None:
                margin = numerator / revenue_value
                signal = classify_financial_signal(label, margin)
                key_ratios.append({"key": label.lower().replace(" ", "_"), "label": label, "value": margin,
                                   "display": f"{margin:.1%}", "comparison": "current quarter", "signal": signal,
                                   "tier": signal, "citation": [by_key[key]["citation"], by_key["revenue"]["citation"]]})
        for key in ("revenue", "operating_income", "net_income", "operating_cash_flow", "eps_diluted"):
            row = by_key.get(key)
            if row and "unavailable" not in row["comparison"]:
                key_ratios.append({"key": f"{key}_growth", "label": f"{row['label']} Growth", "value": None,
                                   "display": row["comparison"].replace(" YoY", ""), "comparison": "year over year",
                                   "signal": row["signal"], "tier": row["signal"], "citation": row["citation"]})

        # Add SBC/Revenue as a Tier 1 ratio metric (from FINANCIAL_DASHBOARD_METRICS_REFERENCE.txt)
        sbc_row = by_key.get("stock_based_compensation")
        revenue_row = by_key.get("revenue")
        if sbc_row and revenue_row and revenue_row["value"]:
            sbc_revenue_value = sbc_row["value"] / revenue_row["value"]
            sbc_prior = None
            if sbc_row.get("prior_value") is not None and revenue_row.get("prior_value") is not None and revenue_row["prior_value"]:
                sbc_prior = sbc_row["prior_value"] / revenue_row["prior_value"]
            sbc_change = _change(sbc_revenue_value, sbc_prior)
            signal = classify_financial_signal("sbc_revenue", sbc_change)
            key_ratios.append({"key": "sbc_revenue", "label": "SBC / Revenue", "value": sbc_revenue_value,
                               "display": f"{sbc_revenue_value:.1%}", "comparison": "current quarter", "signal": signal,
                               "tier": signal, "citation": [sbc_row["citation"], revenue_row["citation"]]})

        # Add Free Cash Flow as a derived metric (OCF - CapEx) (from FINANCIAL_DASHBOARD_METRICS_REFERENCE.txt)
        ocf_row = by_key.get("operating_cash_flow")
        capex_row = by_key.get("capex")
        if ocf_row and capex_row:
            fcf_value = ocf_row["value"] - abs(capex_row["value"])
            fcf_prior = None
            if ocf_row.get("prior_value") is not None and capex_row.get("prior_value") is not None:
                fcf_prior = ocf_row["prior_value"] - abs(capex_row["prior_value"])
            fcf_change = _change(fcf_value, fcf_prior)
            
            # Get QoQ if available
            fcf_prior_q = None
            if ocf_row.get("prior_q_value") is not None and capex_row.get("prior_q_value") is not None:
                fcf_prior_q = ocf_row["prior_q_value"] - abs(capex_row["prior_q_value"])
            fcf_change_qoq = _change_qoq(fcf_value, fcf_prior_q)
            
            comparison_parts = []
            if fcf_change is not None:
                comparison_parts.append(f"{fcf_change:+.1%} YoY")
            if fcf_change_qoq is not None:
                comparison_parts.append(f"{fcf_change_qoq:+.1%} QoQ")
            comparison = ", ".join(comparison_parts) if comparison_parts else "prior-year comparison unavailable"
            
            signal = classify_financial_signal("free_cash_flow", fcf_change)
            fcf_row_data = {"key": "free_cash_flow", "label": "Free Cash Flow", "value": fcf_value,
                           "display": _display(fcf_value, "free_cash_flow"), "prior_value": fcf_prior,
                           "comparison": comparison, "signal": signal, "tier": signal,
                           "citation": _citation("SEC XBRL (derived)", self.data["sources"]["xbrl_url"],
                                                 concept="OperatingCashFlow minus CapitalExpenditures",
                                                 period_start=ocf_row.get("period_start"), period_end=ocf_row.get("period_end"))}
            if fcf_prior_q is not None:
                fcf_row_data["prior_q_value"] = fcf_prior_q
                fcf_row_data["change_qoq"] = fcf_change_qoq
            rows.append(fcf_row_data)
            by_key["free_cash_flow"] = fcf_row_data

        self.data["financials"] = {"rows": rows, "key_ratios": key_ratios}

    def quote_and_valuation(self):
        quote = get_quote(self.ticker, self.expected_account)
        timestamp = quote.get("updated_at")
        quote_age_seconds = None
        if timestamp:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            quote_age_seconds = max(0, (_now() - parsed.astimezone(timezone.utc)).total_seconds())
            if quote_age_seconds > 900:
                if not self.allow_stale_quote_for_test:
                    raise RuntimeError("STALE_QUOTE: Robinhood quote is older than 15 minutes")
                self.data["warnings"].append(
                    "TEST ONLY — stale Robinhood market data explicitly allowed; valuation and recommendation are not actionable"
                )
        else:
            self.data["warnings"].append("Robinhood MCP did not provide a quote timestamp")

        metrics = self.data["_xbrl"]["metrics"]

        def annualize(fact):
            if not fact or fact.get("value") is None:
                return None
            return fact["value"] * 365 / max(fact.get("duration_days") or 91, 1)

        revenue = metrics["revenue"]
        annual_revenue = annualize(revenue)
        annual_gross_profit = annualize(metrics.get("gross_profit"))
        annual_net_income = annualize(metrics.get("net_income"))
        annual_ebit = annualize(metrics.get("operating_income"))
        annual_da = annualize(metrics.get("depreciation_amortization"))
        annual_ebitda = (annual_ebit + annual_da
                         if annual_ebit is not None and annual_da is not None else None)
        annual_sbc = annualize(metrics.get("stock_based_compensation"))
        ocf, capex = metrics.get("operating_cash_flow"), metrics.get("capex")
        annual_fcf = None
        if ocf and capex and abs((ocf.get("duration_days") or 0) - (capex.get("duration_days") or 0)) <= 7:
            annual_fcf = (ocf["value"] - abs(capex["value"])) * 365 / max(ocf["duration_days"], 1)

        market_cap = quote.get("market_cap") or (
            quote["price"] * quote.get("shares_outstanding") if quote.get("shares_outstanding") else None
        )
        cash = metrics.get("cash", {}).get("value")
        debt = metrics.get("long_term_debt", {}).get("value") or 0
        enterprise_value = quote.get("enterprise_value")
        if enterprise_value is None and market_cap is not None and cash is not None:
            enterprise_value = market_cap + debt - cash
        prior_revenue = revenue.get("prior_value")
        revenue_growth_pct = ((revenue["value"] - prior_revenue) / abs(prior_revenue) * 100
                              if prior_revenue not in (None, 0) else None)

        short_data = {}
        try:
            short_data = fetch_short_interest(self.ticker)
            self.data["sources"]["short_interest_url"] = short_data["source_url"]
        except Exception as exc:
            self.data["warnings"].append(f"Official Nasdaq short-interest data unavailable: {type(exc).__name__}")

        sections = build_valuation_sections(
            market_cap=market_cap, enterprise_value=enterprise_value,
            annual_revenue=annual_revenue, annual_gross_profit=annual_gross_profit,
            revenue_growth_pct=revenue_growth_pct,
            total_equity=metrics.get("total_equity", {}).get("value"),
            backlog=metrics.get("backlog", {}).get("value"),
            annual_net_income=annual_net_income, annual_fcf=annual_fcf,
            annual_ebit=annual_ebit, annual_ebitda=annual_ebitda,
            trailing_pe=quote.get("pe_ratio"), forward_pe=quote.get("forward_pe_ratio"),
            peg_ratio=quote.get("peg_ratio"),
            short_interest=short_data.get("short_interest"), public_float=quote.get("public_float"),
            days_to_cover=short_data.get("days_to_cover"),
            short_interest_date=short_data.get("settlement_date"),
            stock_compensation=annual_sbc, period_revenue=annual_revenue, period_fcf=annual_fcf,
            diluted_shares=metrics.get("shares_diluted", {}).get("value"),
            prior_diluted_shares=metrics.get("shares_diluted", {}).get("prior_value"),
            market_source=quote["source"], filing_source="SEC filing/XBRL",
            short_source=short_data.get("source", "Nasdaq official short-interest report"),
        )
        
        # Fallback: fetch Forward P/E from StockAnalysis.com if Robinhood doesn't provide it
        forward_pe = quote.get("forward_pe_ratio")
        if forward_pe is None:
            try:
                forward_pe_sa, sa_url = fetch_forward_pe_ntm(self.ticker)
                if forward_pe_sa:
                    forward_pe = forward_pe_sa
                    self.data["warnings"].append(
                        f"Forward P/E sourced from StockAnalysis.com (S&P Global Market Intelligence): {forward_pe}x"
                    )
            except Exception as exc:
                self.data["warnings"].append(f"Forward P/E fallback failed: {type(exc).__name__}")
        
        # Rebuild valuation with the (possibly updated) forward_pe
        if forward_pe is not None and forward_pe != quote.get("forward_pe_ratio"):
            sections = build_valuation_sections(
                market_cap=market_cap, enterprise_value=enterprise_value,
                annual_revenue=annual_revenue, annual_gross_profit=annual_gross_profit,
                revenue_growth_pct=revenue_growth_pct,
                total_equity=metrics.get("total_equity", {}).get("value"),
                backlog=metrics.get("backlog", {}).get("value"),
                annual_net_income=annual_net_income, annual_fcf=annual_fcf,
                annual_ebit=annual_ebit, annual_ebitda=annual_ebitda,
                trailing_pe=quote.get("pe_ratio"), forward_pe=forward_pe,
                peg_ratio=quote.get("peg_ratio"),
                short_interest=short_data.get("short_interest"), public_float=quote.get("public_float"),
                days_to_cover=short_data.get("days_to_cover"),
                short_interest_date=short_data.get("settlement_date"),
                stock_compensation=annual_sbc, period_revenue=annual_revenue, period_fcf=annual_fcf,
                diluted_shares=metrics.get("shares_diluted", {}).get("value"),
                prior_diluted_shares=metrics.get("shares_diluted", {}).get("prior_value"),
                market_source=quote["source"], filing_source="SEC filing/XBRL",
                short_source=short_data.get("source", "Nasdaq official short-interest report"),
            )
        valuation = {
            "current_price": quote["price"], "market_cap": market_cap,
            "shares_outstanding": quote.get("shares_outstanding"), "public_float": quote.get("public_float"),
            "pe_ttm": quote.get("pe_ratio"), "high_52": quote.get("high_52"), "low_52": quote.get("low_52"),
            "quote_timestamp": timestamp, "quote_source": quote["source"],
            "quote_age_seconds": quote_age_seconds,
            "quote_is_stale": bool(quote_age_seconds and quote_age_seconds > 900),
            "enterprise_value": enterprise_value, "annualized_revenue": annual_revenue,
            "annualized_gross_profit": annual_gross_profit, "annualized_fcf": annual_fcf,
            "ps_annualized": market_cap / annual_revenue if market_cap and annual_revenue and annual_revenue > 0 else None,
            "fcf_yield_annualized": annual_fcf / market_cap * 100 if market_cap and annual_fcf is not None else None,
            "regime": sections["regime"], "regime_label": sections["regime_label"],
            "rows": sections["rows"], "risk_rows": sections["risk_rows"],
            "short_interest": short_data,
        }
        self.data["valuation"] = valuation

    def qualitative(self):
        transcript = self.transcript["content"]
        url = self.transcript["url"]
        sections = extract_transcript_sections(transcript, url)
        self.data["transcript_insights"] = sections["insights"]
        self.data["earnings_call_summary"] = {
            "insights": sections["insights"],
            "validated_sentence_count": sections["sentence_count"],
        }
        self.data["guidance"] = {"rows": sections["guidance"]}
        self.data["channels"] = {"items": sections["channels"]}
        self.data["strategic_pillars"] = sections["strategic_pillars"]

        drivers = []
        for row in self.data["financials"]["rows"]:
            if row["key"] in {"revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow"}:
                drivers.append({"driver": f"{row['label']}: {row['display']} ({row['comparison']})",
                                "signal": row["signal"], "tier": row["signal"], "citation": row["citation"]})
        drivers.extend({"driver": f"{item['topic']}: {item['detail']}", "signal": item["signal"],
                        "tier": item["signal"], "citation": item["citation"]}
                       for item in sections["insights"][:4])
        self.data["growth_drivers"] = drivers

        combined = self.data["_filing_text"] + "\n\nTRANSCRIPT\n" + transcript
        self.data["risks"] = extract_risks(combined, self.data["sources"]["filing_url"], url)
        self.data["capital_liquidity"] = {
            "items": build_capital_liquidity(self.data["financials"]["rows"])
        }

    def grade_and_thesis(self):
        changes = {row["key"]: _change(row["value"], row.get("prior_value")) for row in self.data["financials"]["rows"]}
        score = 0
        for key in ("revenue", "operating_income", "net_income", "operating_cash_flow"):
            change = changes.get(key)
            score += 1 if change is not None and change > 0 else -1 if change is not None and change < 0 else 0
        transcript_score = sum(
            1 if item["tier"] in {"best", "strong_positive", "positive"}
            else -1 if item["tier"] in {"negative", "worst"} else 0
            for item in self.data["transcript_insights"]
        )
        score += max(-2, min(2, transcript_score))
        completeness = sum([bool(self.data["financials"]["rows"]), bool(self.data["sources"].get("earnings_release_url")),
                            bool(self.data["sources"].get("transcript_url")), bool(self.data["valuation"].get("market_cap")),
                            bool(self.data["transcript_insights"])]) / 5
        confidence = min(1.0, 0.55 + 0.4 * completeness)
        letter = "A" if score >= 4 else "B" if score >= 2 else "C" if score >= 0 else "D" if score >= -2 else "F"
        
        # NEW: Compute granular grades for 5 categories
        financial_grade, financial_reason = _grade_financial_metrics(self.data)
        valuation_grade, valuation_reason = _grade_valuation(self.data)
        earnings_call_grade, earnings_call_reason = _grade_earnings_call(self.data)
        management_grade, management_reason = _grade_management_execution(self.data)
        growth_grade, growth_reason = _grade_future_growth(self.data)
        
        # Calculate weighted final grade
        # Final Grade = (Financial Metrics × 0.30) + (Valuation × 0.30) + (Earnings Call × 0.10) + (Management Execution × 0.10) + (Future Growth × 0.20)
        grade_scores = {
            "financial_metrics": _letter_to_score(financial_grade),
            "valuation": _letter_to_score(valuation_grade),
            "earnings_call": _letter_to_score(earnings_call_grade),
            "management_execution": _letter_to_score(management_grade),
            "future_growth": _letter_to_score(growth_grade),
        }
        final_score = (
            grade_scores["financial_metrics"] * 0.30 +
            grade_scores["valuation"] * 0.30 +
            grade_scores["earnings_call"] * 0.10 +
            grade_scores["management_execution"] * 0.10 +
            grade_scores["future_growth"] * 0.20
        )
        final_letter = _score_to_letter(round(final_score))
        
        # Store granular grades and reasoning
        self.data["grade_breakdown"] = {
            "financial_metrics": {"grade": financial_grade, "reason": financial_reason, "weight": 0.30},
            "valuation": {"grade": valuation_grade, "reason": valuation_reason, "weight": 0.30},
            "earnings_call": {"grade": earnings_call_grade, "reason": earnings_call_reason, "weight": 0.10},
            "management_execution": {"grade": management_grade, "reason": management_reason, "weight": 0.10},
            "future_growth": {"grade": growth_grade, "reason": growth_reason, "weight": 0.20},
            "final_grade": final_letter,
            "final_score": round(final_score, 2),
            "all_scores": grade_scores,
        }
        
        self.data["grade"] = {"letter": final_letter, "confidence": confidence,
                              "score": score,
                              "justification": f"Evidence score {score}: reported growth, profitability/cash flow, transcript tone, and source completeness; no ticker-specific grading override."}
        valuation = self.data["valuation"]
        pe = valuation.get("pe_ttm")
        price = valuation["current_price"]
        revenue_growth = changes.get("revenue")
        eps = price / pe if pe and pe > 0 else None
        thesis = {"recommendation": "INSUFFICIENT DATA", "hurdle_rate": HURDLE_RATE,
                  "scenario_weights": SCENARIO_WEIGHTS,
                  "method": "Five-year EPS scenarios use broker-derived TTM EPS, bounded reported growth, and transparent scenario weights/multiples."}
        if eps and revenue_growth is not None:
            base_growth = max(-0.05, min(0.20, revenue_growth))
            base_multiple = max(10.0, min(30.0, pe))
            cases = {"base_case": (base_growth, base_multiple),
                     "bull_case": (min(0.30, base_growth + 0.08), min(35.0, base_multiple + 3)),
                     "bear_case": (max(-0.10, base_growth - 0.12), max(8.0, base_multiple - 5))}
            for name, (growth, multiple) in cases.items():
                exit_eps = eps * (1 + growth) ** 5
                exit_price = exit_eps * multiple
                irr = (exit_price / price) ** (1 / 5) - 1
                probability = SCENARIO_WEIGHTS[name]
                summary = (f"TTM EPS ${eps:.2f} -> ${exit_eps:.2f}; EPS CAGR {growth:.1%}; "
                           f"exit P/E {multiple:.1f}x = ${exit_price:.2f}; IRR {irr:.1%}")
                thesis[name] = {"eps_cagr": growth, "exit_multiple": multiple, "exit_eps": exit_eps,
                                "exit_price": exit_price, "irr": irr, "probability": probability,
                                "summary": summary, "detail": summary}
            base_irr = thesis["base_case"]["irr"]
            thesis["base_cagr"] = thesis["base_case"]["eps_cagr"]
            thesis["irr"] = base_irr
            thesis["recommendation"] = (
                "BUY" if base_irr >= HURDLE_RATE and score >= 2 and confidence >= 0.85
                else "SELL" if base_irr < 0 and score < 0 and confidence >= 0.85
                else "HOLD"
            )
        risk_names = [row["risk"] for row in self.data.get("risks", [])[:3]]
        thesis["key_risks_summary"] = ", ".join(risk_names) if risk_names else "No quantified risk estimate available"
        self.data["thesis"] = thesis

    def save(self, output_dir: str, deliver: bool = True, telegram_target: str = "telegram", dry_run: bool = False):
        safe_period = f"{self.data['fiscal_period']}_FY{self.data['fiscal_year']}"; directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
        public = {key: value for key, value in self.data.items() if not key.startswith("_")}
        paths = {}
        if self.output_format in {"json", "both"}:
            path = directory / f"{self.ticker}_{safe_period}_analysis.json"; path.write_text(json.dumps(public, indent=2)); paths["json"] = str(path)
        if self.output_format in {"markdown", "both"}:
            path = directory / f"{self.ticker}_{safe_period}_analysis.md"; path.write_text(self.markdown(public)); paths["markdown"] = str(path)
        dashboard_dir = directory / f"{self.ticker}_{safe_period}_Interactive_Dashboard"
        paths["html"] = create_interactive_dashboard(public, str(dashboard_dir))
        interactive_pdf = directory / f"{self.ticker}_{safe_period}_Interactive_Dashboard.pdf"
        source_urls = [public.get("sources", {}).get(key) for key in ("filing_url", "transcript_url")]
        paths["interactive_pdf"] = render_dashboard_pdf(paths["html"], str(interactive_pdf), source_urls)
        if deliver: paths["delivery"] = deliver_reports(public, paths["interactive_pdf"], telegram_target, dry_run)
        return paths

    def markdown(self, data: dict[str, Any]) -> str:
        evidence = ["", "---", "", "## Evidence Register",
                    f"- SEC filing: {data['sources']['filing_url']}",
                    f"- SEC XBRL: {data['sources'].get('xbrl_url', 'N/A')}",
                    f"- Earnings-call transcript: {data['sources']['transcript_url']}",
                    f"- Market data: {data['valuation'].get('quote_source', 'N/A')} at {data['valuation'].get('quote_timestamp') or 'timestamp unavailable'}"]
        warnings = ["", "## Warnings"] + [f"- {warning}" for warning in data.get("warnings", [])]
        return ("# Message 1 — Enhanced Dashboard\n\n" + generate_dashboard_message(data) +
                "\n\n---\n\n# Message 2 — Earnings Call Summary\n\n" + generate_call_message(data) +
                "\n" + "\n".join(evidence + warnings) + "\n")

    def run(self, output_dir: str, deliver: bool = True, telegram_target: str = "telegram", dry_run: bool = False):
        self.identify(); self.retrieve(); self.financials(); self.quote_and_valuation(); self.qualitative(); self.grade_and_thesis()
        return self.save(output_dir, deliver, telegram_target, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Verified company earnings analysis")
    parser.add_argument("--ticker", required=True); parser.add_argument("--max-filing-age-days", type=int, default=120)
    parser.add_argument("--output-format", choices=["json", "markdown", "both"], default="both")
    parser.add_argument("--output-dir", default=str(Path.home() / "outputs")); parser.add_argument("--no-deliver", action="store_true",
                        help="Generate artifacts without automatically delivering them")
    parser.add_argument("--telegram-target", default="telegram"); parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-allow-stale-quote", action="store_true",
                        help="TEST ONLY: allow stale Robinhood pricing and mark all outputs non-actionable")
    args = parser.parse_args()
    analyzer = EarningsAnalyzer(args.ticker, args.max_filing_age_days, args.output_format,
                                allow_stale_quote_for_test=args.test_allow_stale_quote)
    try:
        paths = analyzer.run(args.output_dir, not args.no_deliver, args.telegram_target, args.dry_run); print(json.dumps(paths, indent=2))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())