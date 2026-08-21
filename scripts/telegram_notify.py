#!/usr/bin/env python3
"""Verified Hermes gateway delivery for earnings reports."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import zipfile

SIGNAL_EMOJIS = {
    "best": "🟦", "strong_positive": "🔷", "positive": "🔵", "neutral": "🟡",
    "medium": "🟡", "caution": "🟠", "negative": "🔴", "worst": "🟥",
}
SIGNAL_HEADINGS = {
    "best": "Exceptional (Paradigm shifts & structural moats)",
    "strong_positive": "Strong Positive (High-conviction execution)",
    "positive": "Positive (Healthy execution & foundational strength)",
    "neutral": "Neutral (Balanced or insufficient directional evidence)",
    "medium": "Neutral (Balanced or insufficient directional evidence)",
    "caution": "Caution (Monitoring required)",
    "negative": "Negative (Clear headwinds & execution issues)",
    "worst": "Severe Negative (Thesis-level risk)",
}


def _signal(item: dict[str, Any]) -> str:
    return item.get("signal") or item.get("tier") or "neutral"


def _clip(text: str, maximum: int = 190) -> str:
    text = " ".join(str(text).split())
    if len(text) <= maximum:
        return text
    shortened = text[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:-\-")
    return shortened + "…"


def _format_metric(metric: dict[str, Any], show_qoq: bool = True) -> str:
    """Format a single metric line with YoY and QoQ."""
    emoji = SIGNAL_EMOJIS.get(_signal(metric), "🟡")
    label = metric.get("label", "")
    display = metric.get("display", "")
    comparison = metric.get("comparison", "")
    # Add QoQ if available and not already in comparison
    qoq_part = ""
    if show_qoq:
        change_qoq = metric.get("change_qoq")
        if change_qoq is not None and "QoQ" not in comparison:
            qoq_part = f" ({change_qoq:+.1%} QoQ)"
    return f"{emoji} {label}: **{display}** ({comparison}{qoq_part})"


def _format_business_kpi(row: dict[str, Any]) -> str:
    """Format one compact source-backed KPI observation for Telegram."""
    emoji = SIGNAL_EMOJIS.get(row.get("signal", "neutral"), "🟡")
    importance = str(row.get("importance", "Tier unavailable")).replace("Tier ", "T")
    latest_period = row.get("latest_period", "Latest")
    prior_period = row.get("prior_period", "Prior-year")
    analyst_view = _clip(row.get("analyst_view", "No comparison available."), 105)
    return (
        f"{emoji} **{row.get('metric', 'KPI')}** [{row.get('source', 'SEC')} · {importance}]\n"
        f"   {latest_period}: **{row.get('latest_quarter', 'N/A')}** | "
        f"{prior_period}: **{row.get('prior_year_quarter', 'N/A')}** — {analyst_view}"
    )


def _complete_insight_selection(rows: list[dict[str, Any]], maximum: int = 8,
                                character_budget: int = 2500) -> list[dict[str, Any]]:
    """Select complete observations that fit Telegram without truncating evidence."""
    qa = next((row for row in rows if row.get("section") == "Analyst Q&A"), None)
    selected: list[dict[str, Any]] = []
    used = 0
    for row in rows:
        detail = " ".join(str(row.get("detail", "")).split())
        if not detail or len(selected) >= maximum:
            continue
        reserve = len(qa.get("detail", "")) if qa and qa not in selected and row is not qa else 0
        if used + len(detail) + reserve > character_budget:
            continue
        selected.append(row)
        used += len(detail)
    if qa and qa not in selected:
        while selected and used + len(qa.get("detail", "")) > character_budget:
            removed = selected.pop()
            used -= len(removed.get("detail", ""))
        if len(selected) < maximum:
            selected.append(qa)
    return selected


def _warning_prefix(data: dict[str, Any]) -> list[str]:
    return ["**TEST ONLY — STALE MARKET DATA — NOT ACTIONABLE**", ""] if data.get("test_run") else []


def _generate_grade_reasoning(data: dict[str, Any]) -> str:
    """Generate the GRADE REASONING section for Telegram and dashboard."""
    grade_breakdown = data.get("grade_breakdown", {})
    if not grade_breakdown:
        return ""
    
    lines = ["", "📋 **GRADE REASONING**", ""]
    
    # Order: Financial Metrics, Valuation, Earnings Call, Management Execution, Future Growth
    categories = [
        ("financial_metrics", "📊 Financial Metrics"),
        ("valuation", "💰 Valuation"),
        ("earnings_call", "📞 Earnings Call"),
        ("management_execution", "👔 Management Execution"),
        ("future_growth", "🚀 Future Growth"),
    ]
    
    for key, label in categories:
        cat = grade_breakdown.get(key, {})
        grade = cat.get("grade", "N/A")
        reason = cat.get("reason", "No reasoning available")
        weight = cat.get("weight", 0)
        
        # Emoji for grade
        grade_emoji = {
            "A+": "🟦", "A": "🟦", "A-": "🔷",
            "B+": "🔷", "B": "🔵", "B-": "🔵",
            "C+": "🟡", "C": "🟡", "C-": "🟠",
            "D+": "🟠", "D": "🔴", "D-": "🔴", "F": "🟥",
        }.get(grade, "🟡")
        
        lines.append(f"{grade_emoji} **{label} ({weight:.0%}): {grade}** — {reason}")
    
    # Final grade
    final_grade = grade_breakdown.get("final_grade", "N/A")
    final_score = grade_breakdown.get("final_score", 0)
    final_emoji = {
        "A+": "🟦", "A": "🟦", "A-": "🔷",
        "B+": "🔷", "B": "🔵", "B-": "🔵",
        "C+": "🟡", "C": "🟡", "C-": "🟠",
        "D+": "🟠", "D": "🔴", "D-": "🔴", "F": "🟥",
    }.get(final_grade, "🟡")
    
    lines.extend(["", f"🏁 **Final Grade (weighted): {final_emoji} {final_grade}** (score: {final_score:.2f})"])
    
    return "\n".join(lines)


def generate_dashboard_message(data: dict[str, Any]) -> str:
    grade = data.get("grade", {})
    thesis = data.get("thesis", {})
    financials = data.get("financials", {}).get("rows", [])
    valuation = data.get("valuation", {})
    key_ratios = data.get("financials", {}).get("key_ratios", [])

    # Section emojis
    lines = _warning_prefix(data) + [
        f"📊 **{data['ticker']} — {data['fiscal_period']} FY{data['fiscal_year']} Earnings**",
        f"Grade: **{grade.get('letter', 'N/A')}** | Confidence: **{grade.get('confidence', 0):.0%}**",
        "",
    ]

    # FINANCIAL HIGHLIGHTS (YoY + QoQ) - All Tier 1 Income Statement metrics from reference
    lines.append("📈 **Financial Highlights (YoY + QoQ)**")
    tier1_income_keys = ["revenue", "gross_profit", "operating_income", "net_income", 
                         "operating_cash_flow", "free_cash_flow", "capex", "eps_diluted"]
    for key in tier1_income_keys:
        metric = next((m for m in financials if m.get("key") == key), None)
        if metric:
            lines.append(_format_metric(metric))

    # KPI — company-specific operating measures from verified IR and SEC evidence.
    lines.extend(["", "🎯 **KPI**"])
    business_kpis = data.get("business_kpis", {})
    kpi_rows = business_kpis.get("rows", [])[:12]
    if kpi_rows:
        lines.extend(_format_business_kpi(row) for row in kpi_rows)
    else:
        lines.append("🟡 No current-period source-derived KPI reference rows were available.")

    # KEY RATIOS - Only Tier 1 from reference (Gross Margin, Operating Margin, Net Margin, SBC/Revenue)
    # Growth metrics are NOT Tier 1 Key Ratios per reference file
    lines.extend(["", "📊 **Key Ratios**"])
    tier1_ratio_keys = ["gross_margin", "operating_margin", "net_margin", "sbc_revenue"]
    for key in tier1_ratio_keys:
        metric = next((m for m in key_ratios if m.get("key") == key), None)
        if metric:
            lines.append(_format_metric(metric, show_qoq=False))
    
    # If no Tier 1 ratios available (e.g., missing gross_profit), add a note
    if not any(next((m for m in key_ratios if m.get("key") == key), None) for key in tier1_ratio_keys):
        lines.append("🟡 No Tier 1 Key Ratios available (requires gross_profit for margins)")

    # CAPITAL & LIQUIDITY - All Tier 1 from reference
    lines.extend(["", "💼 **Capital & Liquidity**"])
    tier1_capital_keys = ["cash", "total_assets", "total_liabilities", "total_equity", 
                          "long_term_debt", "backlog"]
    for key in tier1_capital_keys:
        metric = next((m for m in financials if m.get("key") == key), None)
        if metric:
            lines.append(_format_metric(metric))

    # VALUATION - Regime-appropriate metrics from reference
    lines.extend(["", "💰 **Valuation**"])
    regime = valuation.get("regime", "negative_earnings_or_fcf")
    if regime == "positive_earnings_and_fcf":
        lines.append("🟢 **Profitability-Based Valuation Metrics (Positive Earnings/FCF)**")
        # Check for missing Tier 1 profitability metrics
        valuation_rows = valuation.get("rows", [])
        tier1_profit_keys = ["forward_pe", "trailing_pe", "ev_ebitda", "levered_fcf_yield"]
        missing_profit = [k for k in tier1_profit_keys if not any(r.get("key") == k for r in valuation_rows)]
        if missing_profit:
            lines.append(f"🟡 Missing Tier 1: {', '.join(missing_profit)}")
    else:
        lines.append("🔴 **Valuation Metrics (Negative Earnings/FCF)**")
    for row in valuation.get("rows", []):
        emoji = SIGNAL_EMOJIS.get(_signal(row), "🟡")
        lines.append(f"{emoji} {row['label']}: **{row['display']}** — {row.get('assessment', 'Unclassified')}")

    # SHORT INTEREST & STOCK-BASED COMPENSATION - All Tier 1 from reference
    lines.extend(["", "📉 **Short Interest & Stock-Based Compensation**"])
    risk_rows = valuation.get("risk_rows", [])
    tier1_risk_keys = ["short_interest_float", "days_to_cover", "sbc_revenue", 
                       "sbc_adjusted_fcf_yield", "net_share_dilution"]
    for key in tier1_risk_keys:
        row = next((r for r in risk_rows if r.get("key") == key), None)
        if row:
            emoji = SIGNAL_EMOJIS.get(_signal(row), "🟠")
            lines.append(f"{emoji} {row['label']}: **{row['display']}** — {row.get('assessment', 'Unclassified')}")

    lines.extend(["", "⚠️ **Key Risk Matrix**"])
    risks = data.get("risks", [])[:6]
    if not risks:
        lines.append("🟡 No coherent risk excerpt was verified.")
    for risk in risks:
        emoji = SIGNAL_EMOJIS.get(_signal(risk), "🟠")
        if isinstance(risk.get("probability"), (int, float)) and isinstance(risk.get("eps_impact"), (int, float)):
            quantification = f"{risk['probability']:.0%} probability / {risk['eps_impact']:.0%} EPS impact"
        else:
            quantification = "Probability and EPS impact not quantified by the company"
        lines.append(f"{emoji} {risk['risk']}: {quantification} — {_clip(risk.get('evidence', ''), 110)}")

    lines.extend(["", "🎯 **Key Drivers**"])
    for driver in data.get("growth_drivers", [])[:7]:
        emoji = SIGNAL_EMOJIS.get(_signal(driver), "🟡")
        lines.append(f"{emoji} {_clip(driver['driver'], 170)}")

    base = thesis.get("base_case")
    bull = thesis.get("bull_case")
    bear = thesis.get("bear_case")
    lines.extend(["", f"🧠 **Thesis: {thesis.get('recommendation', 'INSUFFICIENT DATA')}** | ",
                  f"Base EPS CAGR: {thesis.get('base_cagr', 0):.0%} | ",
                  f"IRR: {thesis.get('irr', 0):.0%} | Hurdle: {thesis.get('hurdle_rate', 0):.0%}"])
    for label, case, emoji in (("Base", base, SIGNAL_EMOJIS["best"]),
                               ("Bull", bull, SIGNAL_EMOJIS["strong_positive"]),
                               ("Bear", bear, SIGNAL_EMOJIS["negative"])):
        if case:
            lines.append(f"{emoji} {label} ({case.get('probability', 0):.0%}): {_clip(case.get('detail') or case.get('summary', ''), 230)}")
    lines.append(f"{SIGNAL_EMOJIS['caution']} Key Risks: {_clip(thesis.get('key_risks_summary', 'Not quantified'), 220)}")

    # GRADE REASONING section
    lines.append(_generate_grade_reasoning(data))

    # METRICS NOTE - Summary of missing Tier 1 metrics
    missing_notes = []
    # Financial Highlights
    financials = data.get("financials", {}).get("rows", [])
    tier1_income_keys = ["revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "free_cash_flow", "capex", "eps_diluted"]
    missing_income = [k for k in tier1_income_keys if not any(m.get("key") == k for m in financials)]
    if missing_income:
        missing_notes.append(f"Financial Highlights: missing {', '.join(missing_income)}")
    
    # Key Ratios
    key_ratios = data.get("financials", {}).get("key_ratios", [])
    tier1_ratio_keys = ["gross_margin", "operating_margin", "net_margin", "sbc_revenue"]
    missing_ratios = [k for k in tier1_ratio_keys if not any(m.get("key") == k for m in key_ratios)]
    if missing_ratios:
        missing_notes.append(f"Key Ratios: missing {', '.join(missing_ratios)}")
    
    # Capital & Liquidity
    tier1_capital_keys = ["cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "backlog"]
    missing_capital = [k for k in tier1_capital_keys if not any(m.get("key") == k for m in financials)]
    if missing_capital:
        missing_notes.append(f"Capital & Liquidity: missing {', '.join(missing_capital)}")
    
    # Short Interest & SBC
    risk_rows = valuation.get("risk_rows", [])
    tier1_risk_keys = ["short_interest_float", "days_to_cover", "sbc_revenue", "sbc_adjusted_fcf_yield", "net_share_dilution"]
    missing_risk = [k for k in tier1_risk_keys if not any(r.get("key") == k for r in risk_rows)]
    if missing_risk:
        missing_notes.append(f"Short Interest & SBC: missing {', '.join(missing_risk)}")
    
    if missing_notes:
        lines.extend(["", "📝 **Metrics Note:**"] + [f"• {note}" for note in missing_notes])
    else:
        lines.append("\n📝 **Metrics Note:** All Tier 1 metrics displayed.")

    lines.extend(["", "📎 HTML Dashboard: Interactive dashboard attached as ZIP",
                  f"🔗 SEC: {data['sources']['filing_url']}"])
    if data["sources"].get("investor_relations_url"):
        lines.append(f"🔗 IR: {data['sources']['investor_relations_url']}")
    if data["sources"].get("earnings_release_url"):
        lines.append(f"🔗 IR/SEC release: {data['sources']['earnings_release_url']}")
    lines.append(f"🔗 Transcript: {data['sources']['transcript_url']}")
    return "\n".join(lines)


def generate_call_message(data: dict[str, Any]) -> str:
    lines = _warning_prefix(data) + [f"📞 **{data['ticker']} — {data['fiscal_period']} FY{data['fiscal_year']} Earnings Call Summary**", ""]
    all_insights = data.get("transcript_insights", [])
    insights = _complete_insight_selection(all_insights)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for insight in insights:
        grouped.setdefault(_signal(insight), []).append(insight)
    for signal in ("best", "strong_positive", "positive", "neutral", "medium", "caution", "negative", "worst"):
        rows = grouped.get(signal, [])
        if not rows:
            continue
        emoji = SIGNAL_EMOJIS[signal]
        lines.append(f"{emoji} **{SIGNAL_HEADINGS[signal]}**")
        lines.append("")
        for insight in rows:
            confidence = ""
            if insight.get("topic") == "Management Tone":
                category = insight.get("confidence_category")
                subcategory = insight.get("confidence_subcategory")
                if category and subcategory:
                    confidence = f"{category} -> {subcategory}, "
            lines.append(f"{emoji} **{insight['topic']}**: {confidence}{' '.join(insight['detail'].split())}")
            lines.append(f"   Reasoning: {_clip(insight.get('reasoning', 'Classification follows the cited transcript evidence.'), 150)}")
            lines.append(f"   Evidence: {insight.get('section', 'Transcript')} chars {insight.get('citation', {}).get('start', 'N/A')}–{insight.get('citation', {}).get('end', 'N/A')}")
            lines.append("")
    lines.extend([f"Source: Earnings call transcript (prepared remarks + analyst Q&A) — {data['sources']['transcript_url']}",
                  "📎 HTML Dashboard: Interactive dashboard attached as ZIP"])
    return "\n".join(lines)


def _create_html_zip(html_dir: str) -> str:
    """Create a zip file from the interactive dashboard HTML directory."""
    html_path = Path(html_dir).resolve()
    if not html_path.is_dir():
        raise RuntimeError(f"Interactive dashboard HTML directory not found: {html_dir}")
    
    zip_path = html_path.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in html_path.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(html_path.parent)
                zipf.write(file_path, arcname)
    
    return str(zip_path)


def _send(message: str, html_dir: str, target: str) -> dict[str, Any]:
    zip_path = _create_html_zip(html_dir)
    path = Path(zip_path).resolve()
    if not path.is_file() or path.stat().st_size == 0: 
        raise RuntimeError("HTML zip file is missing or empty")
    
    body = f"{message}\n\nMEDIA:{path}"
    result = subprocess.run(["hermes", "send", "--to", target, "--json", body], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Telegram delivery failed: {(result.stderr or result.stdout).strip()}")
    try: response = json.loads(result.stdout)
    except json.JSONDecodeError as exc: raise RuntimeError("Telegram delivery returned malformed JSON") from exc
    if not isinstance(response, dict) or response.get("success") is False or response.get("error"):
        raise RuntimeError("Telegram backend did not confirm successful delivery")
    backend_id = response.get("message_id") or response.get("id") or response.get("delivery_id")
    if not backend_id and not response.get("success"):
        raise RuntimeError("Telegram delivery returned no success receipt or message identifier")
    return {"success": True, "target": target.split(":", 1)[0], "backend_id": backend_id,
            "timestamp": datetime.now(timezone.utc).isoformat(), "return_code": result.returncode}


def deliver_reports(data: dict[str, Any], html_dir: str, target: str = "telegram", dry_run: bool = False) -> list[dict[str, Any]]:
    messages = [generate_dashboard_message(data), generate_call_message(data)]
    if dry_run:
        zip_path = _create_html_zip(html_dir)
        return [{"success": False, "dry_run": True, "message": message, "media_path": str(Path(zip_path).resolve())} for message in messages]
    return [_send(message, html_dir, target) for message in messages]