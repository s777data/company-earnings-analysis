#!/usr/bin/env python3
"""Final Valuation Score Engine — P/S Relative Valuation + Regime-based composite score.

Implements the evidence-gated valuation methodology from valuation_grade_prompt.
All calculations are company-neutral; no ticker-specific branches.
"""

from __future__ import annotations

import math
from typing import Any, Optional


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


# ──────────────────────────────────────────────────────────────────────
# 1. P/S RELATIVE VALUATION ENGINE (from prompt sections 1-13)
# ──────────────────────────────────────────────────────────────────────

def calculate_ps_relative_valuation(
    *,
    company_ps: Optional[float],
    peer_median_ps: Optional[float],
    company_revenue_growth_yoy: Optional[float],  # decimal, e.g. 0.25 for 25%
    peer_revenue_growth: Optional[float],
    company_adjusted_ebitda_margin: Optional[float],  # decimal
    peer_adjusted_ebitda_margin: Optional[float],
    # metadata for logging
    peer_group_name: str = "Unknown",
    peer_group_level: str = "Unknown",
    peer_count: int = 0,
    peer_ps_source: str = "Unknown",
    peer_ps_date: str = "Unknown",
) -> dict[str, Any]:
    """
    Calculate P/S relative valuation ratio (VR) and continuous 0-100 score.

    Returns dict with:
    - base_ps_ratio
    - growth_adjustment
    - profitability_adjustment
    - relative_valuation_ratio (VR)
    - valuation_score (0-100)
    - classification (Very Attractive ... Very Expensive)
    - color (Dark Blue ... Dark Red)
    - inputs (echoed for audit trail)
    """
    if company_ps is None or peer_median_ps is None or peer_median_ps <= 0:
        return _empty_ps_result("Missing company P/S or peer median P/S")

    # 7. Base Relative P/S
    base_ps_ratio = company_ps / peer_median_ps

    # 8. Growth Adjustment (70% weight)
    if company_revenue_growth_yoy is not None and peer_revenue_growth is not None:
        growth_adjustment = (
            ((1 + peer_revenue_growth) / (1 + company_revenue_growth_yoy)) ** 0.70
        )
    else:
        growth_adjustment = 1.0

    # 9. Profitability Adjustment (30% weight)
    if (
        company_adjusted_ebitda_margin is not None
        and peer_adjusted_ebitda_margin is not None
        and company_adjusted_ebitda_margin > -0.90  # Guardrail: margin > -90%
        and peer_adjusted_ebitda_margin > -0.90
    ):
        profitability_adjustment = (
            ((1 + peer_adjusted_ebitda_margin) / (1 + company_adjusted_ebitda_margin))
            ** 0.30
        )
    else:
        # Guardrail: if margin <= -90%, formula invalid - use neutral adjustment
        profitability_adjustment = 1.0

    # 10. Relative Valuation Ratio
    relative_valuation_ratio = (
        base_ps_ratio * growth_adjustment * profitability_adjustment
    )

    # 13. Continuous 0-100 Color Score
    # valuation_score = 100 * VR / (1 + VR)
    valuation_score = 100 * relative_valuation_ratio / (1 + relative_valuation_ratio)

    # 12. Classification Spectrum
    classification, color = _classify_vr(relative_valuation_ratio)

    return {
        "base_ps_ratio": base_ps_ratio,
        "growth_adjustment": growth_adjustment,
        "profitability_adjustment": profitability_adjustment,
        "relative_valuation_ratio": relative_valuation_ratio,
        "valuation_score": round(valuation_score, 1),
        "classification": classification,
        "color": color,
        "inputs": {
            "company_ps": company_ps,
            "peer_median_ps": peer_median_ps,
            "company_revenue_growth_yoy": company_revenue_growth_yoy,
            "peer_revenue_growth": peer_revenue_growth,
            "company_adjusted_ebitda_margin": company_adjusted_ebitda_margin,
            "peer_adjusted_ebitda_margin": peer_adjusted_ebitda_margin,
            "peer_group_name": peer_group_name,
            "peer_group_level": peer_group_level,
            "peer_count": peer_count,
            "peer_ps_source": peer_ps_source,
            "peer_ps_date": peer_ps_date,
        },
    }


def _classify_vr(vr: float) -> tuple[str, str]:
    """Map VR to classification and color per prompt section 12."""
    if vr < 0.55:
        return "Very Attractive", "Dark Blue"
    if vr < 0.75:
        return "Attractive", "Blue"
    if vr < 0.90:
        return "Slightly Attractive", "Light Blue"
    if vr <= 1.10:
        return "Fair", "Neutral"
    if vr <= 1.30:
        return "Premium", "Yellow"
    if vr <= 1.60:
        return "Expensive", "Orange"
    return "Very Expensive", "Dark Red"


def _empty_ps_result(reason: str) -> dict[str, Any]:
    return {
        "base_ps_ratio": None,
        "growth_adjustment": None,
        "profitability_adjustment": None,
        "relative_valuation_ratio": None,
        "valuation_score": None,
        "classification": "Unavailable",
        "color": "Neutral",
        "error": reason,
        "inputs": {},
    }


# ──────────────────────────────────────────────────────────────────────
# 2. FINAL VALUATION SCORE ENGINE (from prompt sections 1-14)
# ──────────────────────────────────────────────────────────────────────

def determine_valuation_regime(
    forward_eps: Optional[float],
    ebitda: Optional[float],
    fcf: Optional[float],
) -> str:
    """Determine valuation regime: A (profitable+FCF), B (profitable-FCF), C (unprofitable)."""
    if forward_eps is not None and forward_eps > 0 and ebitda is not None and ebitda > 0 and fcf is not None and fcf > 0:
        return "A"
    if forward_eps is not None and forward_eps > 0 and ebitda is not None and ebitda > 0:
        return "B"
    return "C"


def calculate_pe_score(
    company_forward_pe: Optional[float],
    peer_forward_pe: Optional[float],
    company_expected_eps_growth: Optional[float],
    peer_expected_eps_growth: Optional[float],
) -> Optional[float]:
    """Forward P/E Score per prompt section 3."""
    if not all(v is not None for v in (company_forward_pe, peer_forward_pe, company_expected_eps_growth, peer_expected_eps_growth)):
        return None
    if company_forward_pe <= 0 or peer_forward_pe <= 0:
        return None

    pe_vr = (company_forward_pe / peer_forward_pe) * (
        (1 + peer_expected_eps_growth) / (1 + company_expected_eps_growth)
    )
    # PE_Score = CLAMP(75 - 35 * LN(PE_VR), 0, 100)
    score = 75 - 35 * math.log(pe_vr)
    return clamp(score, 0, 100)


def calculate_ps_score(
    company_ps: Optional[float],
    peer_ps: Optional[float],
    company_revenue_growth: Optional[float],
    peer_revenue_growth: Optional[float],
    company_profitability: Optional[float],  # adj EBITDA margin (profitable) or gross margin (unprofitable)
    peer_profitability: Optional[float],
) -> Optional[float]:
    """P/S Score per prompt section 4."""
    if not all(v is not None for v in (company_ps, peer_ps, company_revenue_growth, peer_revenue_growth)):
        return None
    if peer_ps <= 0:
        return None

    ps_vr = (company_ps / peer_ps) * (
        ((1 + peer_revenue_growth) / (1 + company_revenue_growth)) ** 0.70
    )
    if company_profitability is not None and peer_profitability is not None:
        if (1 + company_profitability) > 0 and (1 + peer_profitability) > 0:
            ps_vr *= ((1 + peer_profitability) / (1 + company_profitability)) ** 0.30

    score = 75 - 35 * math.log(ps_vr)
    return clamp(score, 0, 100)


def calculate_ev_ebitda_score(
    company_ev_ebitda: Optional[float],
    peer_ev_ebitda: Optional[float],
) -> Optional[float]:
    """EV/EBITDA Score per prompt section 5."""
    if company_ev_ebitda is None or peer_ev_ebitda is None or peer_ev_ebitda <= 0:
        return None
    vr = company_ev_ebitda / peer_ev_ebitda
    score = 75 - 35 * math.log(vr)
    return clamp(score, 0, 100)


def calculate_fcf_yield_score(
    company_fcf_yield: Optional[float],
    peer_fcf_yield: Optional[float],
) -> Optional[float]:
    """FCF Yield Score per prompt section 6. Higher yield = better."""
    if company_fcf_yield is None or peer_fcf_yield is None or company_fcf_yield <= 0:
        return None
    # FCF_VR = peer_fcf_yield / company_fcf_yield
    vr = peer_fcf_yield / company_fcf_yield
    score = 75 - 35 * math.log(vr)
    return clamp(score, 0, 100)


def calculate_ev_revenue_score(
    company_ev_revenue: Optional[float],
    peer_ev_revenue: Optional[float],
    company_revenue_growth: Optional[float],
    peer_revenue_growth: Optional[float],
    company_gross_margin: Optional[float],
    peer_gross_margin: Optional[float],
) -> Optional[float]:
    """EV/Revenue Score per prompt section 7."""
    if not all(v is not None for v in (company_ev_revenue, peer_ev_revenue, company_revenue_growth, peer_revenue_growth)):
        return None
    if peer_ev_revenue <= 0:
        return None

    vr = (company_ev_revenue / peer_ev_revenue) * (
        ((1 + peer_revenue_growth) / (1 + company_revenue_growth)) ** 0.70
    )
    if company_gross_margin is not None and peer_gross_margin is not None:
        if (1 + company_gross_margin) > 0 and (1 + peer_gross_margin) > 0:
            vr *= ((1 + peer_gross_margin) / (1 + company_gross_margin)) ** 0.30

    score = 75 - 35 * math.log(vr)
    return clamp(score, 0, 100)


def calculate_ev_gross_profit_score(
    company_ev_gross_profit: Optional[float],
    peer_ev_gross_profit: Optional[float],
    company_revenue_growth: Optional[float],
    peer_revenue_growth: Optional[float],
) -> Optional[float]:
    """EV/Gross Profit Score per prompt section 8."""
    if not all(v is not None for v in (company_ev_gross_profit, peer_ev_gross_profit, company_revenue_growth, peer_revenue_growth)):
        return None
    if peer_ev_gross_profit <= 0:
        return None

    vr = (company_ev_gross_profit / peer_ev_gross_profit) * (
        ((1 + peer_revenue_growth) / (1 + company_revenue_growth)) ** 0.50
    )
    score = 75 - 35 * math.log(vr)
    return clamp(score, 0, 100)


def calculate_capital_liquidity_adjustment(
    net_cash: Optional[float],  # Cash - Total Debt
    market_cap: Optional[float],
    net_debt_to_ebitda: Optional[float] = None,
) -> float:
    """Capital & Liquidity Adjustment per prompt section 9."""
    if net_cash is None or market_cap is None or market_cap <= 0:
        return 0.0

    net_cash_ratio = net_cash / market_cap

    # Strong net cash: +2 to +5
    if net_cash_ratio > 0.20:
        adj = 5
    elif net_cash_ratio > 0.10:
        adj = 4
    elif net_cash_ratio > 0.05:
        adj = 3
    elif net_cash_ratio > 0:
        adj = 2
    # Neutral
    elif net_cash_ratio == 0:
        adj = 0
    # Moderate leverage: -2 to -4
    elif net_debt_to_ebitda is not None and net_debt_to_ebitda > 3.0:
        adj = -5
    elif net_debt_to_ebitda is not None and net_debt_to_ebitda > 2.0:
        adj = -4
    elif net_debt_to_ebitda is not None and net_debt_to_ebitda > 1.0:
        adj = -3
    elif net_cash_ratio > -0.10:
        adj = -2
    elif net_cash_ratio > -0.20:
        adj = -4
    # High leverage: -5 to -8
    else:
        adj = -6

    return clamp(adj, -10, 10)


def calculate_dilution_adjustment(net_share_dilution_pct: Optional[float]) -> float:
    """Dilution / SBC Adjustment per prompt section 10."""
    if net_share_dilution_pct is None:
        return 0.0

    if net_share_dilution_pct < 0:  # buybacks
        return 2
    if net_share_dilution_pct <= 1:
        return 0
    if net_share_dilution_pct <= 3:
        return -2
    if net_share_dilution_pct <= 5:
        return -4
    if net_share_dilution_pct <= 8:
        return -6
    return -8


def calculate_roic_adjustment(roic_minus_wacc: Optional[float]) -> float:
    """ROIC Quality Adjustment per prompt section 11."""
    if roic_minus_wacc is None:
        return 0.0

    if roic_minus_wacc > 0.15:
        return 4
    if roic_minus_wacc > 0.08:
        return 2
    if roic_minus_wacc > 0.03:
        return 1
    if roic_minus_wacc >= -0.03:
        return 0
    if roic_minus_wacc > -0.10:
        return -3
    return -5


def calculate_final_valuation_score(
    *,
    # Regime A inputs
    pe_score: Optional[float] = None,
    ps_score: Optional[float] = None,
    ev_ebitda_score: Optional[float] = None,
    fcf_yield_score: Optional[float] = None,
    # Regime B inputs (same as A but no FCF)
    # Regime C inputs
    ev_revenue_score: Optional[float] = None,
    ev_gross_profit_score: Optional[float] = None,
    # Adjustments
    net_cash: Optional[float] = None,
    market_cap: Optional[float] = None,
    net_debt_to_ebitda: Optional[float] = None,
    net_share_dilution_pct: Optional[float] = None,
    roic_minus_wacc: Optional[float] = None,
    regime: str = "C",
) -> dict[str, Any]:
    """
    Calculate Final Valuation Score per prompt sections 1-14.

    Returns dict with:
    - regime
    - core_valuation_score
    - capital_liquidity_adjustment
    - dilution_adjustment
    - roic_adjustment
    - total_modifier (clamped -10 to +10)
    - final_valuation_score (0-100)
    - letter_grade (A+ through F)
    - classification (Exceptionally Attractive ... Extreme Valuation)
    - component_scores (for audit trail)
    """
    # 1. Determine weights based on regime
    if regime == "A":
        weights = {
            "pe": 0.35,
            "ps": 0.25,
            "ev_ebitda": 0.20,
            "fcf_yield": 0.20,
        }
        component_scores = {
            "pe": pe_score,
            "ps": ps_score,
            "ev_ebitda": ev_ebitda_score,
            "fcf_yield": fcf_yield_score,
        }
    elif regime == "B":
        weights = {
            "pe": 0.4375,
            "ps": 0.3125,
            "ev_ebitda": 0.25,
        }
        component_scores = {
            "pe": pe_score,
            "ps": ps_score,
            "ev_ebitda": ev_ebitda_score,
        }
    else:  # Regime C
        weights = {
            "ps": 0.40,
            "ev_revenue": 0.35,
            "ev_gross_profit": 0.25,
        }
        component_scores = {
            "ps": ps_score,
            "ev_revenue": ev_revenue_score,
            "ev_gross_profit": ev_gross_profit_score,
        }

    # 13. Missing Metric Rule - renormalize weights for available metrics
    valid_weights = {k: v for k, v in weights.items() if component_scores.get(k) is not None}
    if not valid_weights:
        return _empty_final_result("No valid valuation metrics available", regime)

    total_weight = sum(valid_weights.values())
    normalized_weights = {k: v / total_weight for k, v in valid_weights.items()}

    # Core Valuation Score
    core_score = sum(
        component_scores[k] * normalized_weights[k]
        for k in normalized_weights
    )

    # 9-11. Adjustments
    cap_liq_adj = calculate_capital_liquidity_adjustment(net_cash, market_cap, net_debt_to_ebitda)
    dilution_adj = calculate_dilution_adjustment(net_share_dilution_pct)
    roic_adj = calculate_roic_adjustment(roic_minus_wacc)

    # 12. Total Modifier Limit
    total_modifier = clamp(cap_liq_adj + dilution_adj + roic_adj, -10, 10)

    # Final Score
    final_score = clamp(core_score + total_modifier, 0, 100)

    # 14. Letter Grade
    letter_grade = _score_to_letter_grade(final_score)
    classification = _letter_grade_to_classification(letter_grade)

    return {
        "regime": regime,
        "core_valuation_score": round(core_score, 1),
        "capital_liquidity_adjustment": cap_liq_adj,
        "dilution_adjustment": dilution_adj,
        "roic_adjustment": roic_adj,
        "total_modifier": round(total_modifier, 1),
        "final_valuation_score": round(final_score, 1),
        "letter_grade": letter_grade,
        "classification": classification,
        "component_scores": {k: round(v, 1) if v is not None else None for k, v in component_scores.items()},
        "normalized_weights": {k: round(v, 4) for k, v in normalized_weights.items()},
        "valid_metrics": list(valid_weights.keys()),
    }


def _score_to_letter_grade(score: float) -> str:
    """Convert 0-100 score to letter grade per prompt section 14."""
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    if score >= 40:
        return "D"
    return "F"


def _letter_grade_to_classification(grade: str) -> str:
    """Map letter grade to classification label."""
    mapping = {
        "A+": "Exceptionally Attractive",
        "A": "Very Attractive",
        "A-": "Attractive",
        "B+": "Fair / Attractive",
        "B": "Fair",
        "B-": "Fair / Premium",
        "C+": "Moderate Premium",
        "C": "Expensive",
        "C-": "Expensive",
        "D": "Very Expensive",
        "F": "Extreme Valuation",
    }
    return mapping.get(grade, "Unknown")


def _empty_final_result(reason: str, regime: str) -> dict[str, Any]:
    return {
        "regime": regime,
        "core_valuation_score": None,
        "capital_liquidity_adjustment": 0,
        "dilution_adjustment": 0,
        "roic_adjustment": 0,
        "total_modifier": 0,
        "final_valuation_score": None,
        "letter_grade": "N/A",
        "classification": "Unavailable",
        "error": reason,
        "component_scores": {},
        "normalized_weights": {},
        "valid_metrics": [],
    }


# ──────────────────────────────────────────────────────────────────────
# 3. MASTER ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────

def build_valuation_analysis(
    *,
    # Company fundamentals
    market_cap: Optional[float],
    enterprise_value: Optional[float],
    annual_revenue: Optional[float],
    annual_gross_profit: Optional[float],
    annual_net_income: Optional[float],
    annual_ebit: Optional[float],
    annual_ebitda: Optional[float],
    annual_fcf: Optional[float],
    total_equity: Optional[float],
    cash: Optional[float],
    total_debt: Optional[float],
    # Growth & margins
    revenue_growth_yoy: Optional[float],  # decimal
    gross_margin: Optional[float],  # decimal
    adjusted_ebitda_margin: Optional[float],  # decimal
    # Market data
    current_price: Optional[float],
    trailing_pe: Optional[float],
    forward_pe: Optional[float],
    peg_ratio: Optional[float],
    # Peer data
    peer_median_ps: Optional[float] = None,
    peer_median_forward_pe: Optional[float] = None,
    peer_median_ev_ebitda: Optional[float] = None,
    peer_median_ev_revenue: Optional[float] = None,
    peer_median_ev_gross_profit: Optional[float] = None,
    peer_median_fcf_yield: Optional[float] = None,
    peer_revenue_growth: Optional[float] = None,
    peer_gross_margin: Optional[float] = None,
    peer_adjusted_ebitda_margin: Optional[float] = None,
    peer_expected_eps_growth: Optional[float] = None,
    # Peer metadata
    peer_group_name: str = "Unknown",
    peer_group_level: str = "Unknown",
    peer_count: int = 0,
    peer_ps_source: str = "Unknown",
    peer_ps_date: str = "Unknown",
    # Dilution & quality
    net_share_dilution_pct: Optional[float] = None,
    roic_minus_wacc: Optional[float] = None,
) -> dict[str, Any]:
    """
    Master function to compute both P/S Relative Valuation and Final Valuation Score.

    This is the main entry point that run_analysis.py should call.
    """
    # Company P/S
    company_ps = _safe_div(market_cap, annual_revenue)

    # 1. P/S Relative Valuation
    ps_relative = calculate_ps_relative_valuation(
        company_ps=company_ps,
        peer_median_ps=peer_median_ps,
        company_revenue_growth_yoy=revenue_growth_yoy,
        peer_revenue_growth=peer_revenue_growth,
        company_adjusted_ebitda_margin=adjusted_ebitda_margin,
        peer_adjusted_ebitda_margin=peer_adjusted_ebitda_margin,
        peer_group_name=peer_group_name,
        peer_group_level=peer_group_level,
        peer_count=peer_count,
        peer_ps_source=peer_ps_source,
        peer_ps_date=peer_ps_date,
    )

    # Determine regime
    regime = determine_valuation_regime(forward_pe, annual_ebitda, annual_fcf)

    # Calculate individual metric scores
    pe_score = calculate_pe_score(
        forward_pe, peer_median_forward_pe, None, peer_expected_eps_growth
    ) if forward_pe and peer_median_forward_pe and peer_expected_eps_growth is not None else None

    ps_score = calculate_ps_score(
        company_ps, peer_median_ps, revenue_growth_yoy, peer_revenue_growth,
        adjusted_ebitda_margin, peer_adjusted_ebitda_margin
    ) if all(v is not None for v in [company_ps, peer_median_ps, revenue_growth_yoy, peer_revenue_growth]) else None

    ev_ebitda_score = calculate_ev_ebitda_score(
        _safe_div(enterprise_value, annual_ebitda), peer_median_ev_ebitda
    ) if enterprise_value and annual_ebitda and peer_median_ev_ebitda else None

    fcf_yield_score = calculate_fcf_yield_score(
        _safe_div(annual_fcf, market_cap) * 100 if market_cap and annual_fcf else None,
        peer_median_fcf_yield
    ) if annual_fcf and market_cap and peer_median_fcf_yield else None

    ev_revenue_score = calculate_ev_revenue_score(
        _safe_div(enterprise_value, annual_revenue), peer_median_ev_revenue,
        revenue_growth_yoy, peer_revenue_growth,
        gross_margin, peer_gross_margin
    ) if enterprise_value and annual_revenue and peer_median_ev_revenue else None

    ev_gross_profit_score = calculate_ev_gross_profit_score(
        _safe_div(enterprise_value, annual_gross_profit), peer_median_ev_gross_profit,
        revenue_growth_yoy, peer_revenue_growth
    ) if enterprise_value and annual_gross_profit and peer_median_ev_gross_profit else None

    # Net cash for adjustment
    net_cash = (cash or 0) - (total_debt or 0)

    # 2. Final Valuation Score
    final_score = calculate_final_valuation_score(
        pe_score=pe_score,
        ps_score=ps_score,
        ev_ebitda_score=ev_ebitda_score,
        fcf_yield_score=fcf_yield_score,
        ev_revenue_score=ev_revenue_score,
        ev_gross_profit_score=ev_gross_profit_score,
        net_cash=net_cash,
        market_cap=market_cap,
        net_debt_to_ebitda=_safe_div(total_debt - (cash or 0), annual_ebitda) if annual_ebitda else None,
        net_share_dilution_pct=net_share_dilution_pct,
        roic_minus_wacc=roic_minus_wacc,
        regime=regime,
    )

    return {
        "ps_relative_valuation": ps_relative,
        "final_valuation_score": final_score,
        "regime": regime,
        "company_ps": company_ps,
    }