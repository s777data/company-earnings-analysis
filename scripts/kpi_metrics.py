#!/usr/bin/env python3
"""Evidence-gated selection of company-specific operating KPIs.

The seed catalogue is derived from references/BUSINESS_KPI_METRICS_REFERENCE.md.
It intentionally excludes generic income-statement, valuation, cash-flow, and SBC
measures already rendered elsewhere in the report.
"""
from __future__ import annotations

import re
from typing import Any

ALLOWED_SOURCES = {"IR", "SEC", "IR/SEC"}
MIN_KPIS = 12
MAX_KPIS = 12

# The first catalogue implements the restaurant operating-KPI framework supplied
# with the feature request. The selector activates it only for restaurant filings.
RESTAURANT_KPIS: tuple[dict[str, Any], ...] = (
    {"key": "same_restaurant_sales_growth", "metric": "Same Restaurant Sales Growth", "tier": 1,
     "aliases": (r"same[- ]restaurant sales(?: growth)?", r"same[- ]store sales(?: growth)?", r"comparable restaurant sales"),
     "direction": "higher", "importance": "Tier 1 — Core", "impact": "Measures demand growth from established restaurants."},
    {"key": "guest_traffic_growth", "metric": "Guest Traffic Growth", "tier": 1,
     "aliases": (r"guest traffic(?: growth)?", r"traffic(?: growth)?"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Separates customer demand from price and product mix."},
    {"key": "average_unit_volume", "metric": "Average Unit Volume (AUV)", "tier": 1,
     "aliases": (r"average unit volume", r"\bAUV\b"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Measures mature-location sales productivity."},
    {"key": "restaurant_level_profit_margin", "metric": "Restaurant-Level Profit Margin", "tier": 1,
     "aliases": (r"restaurant[- ]level profit margin", r"restaurant level margin"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Measures underlying restaurant unit economics."},
    {"key": "net_new_restaurant_openings", "metric": "Net New Restaurant Openings", "tier": 1,
     "aliases": (r"net new (?:[A-Z]{2,8} )?restaurant openings", r"net new openings"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Measures physical footprint expansion during the period."},
    {"key": "total_restaurants", "metric": "Total Restaurant Count", "tier": 1,
     "aliases": (r"total (?:[A-Z]{2,8} )?restaurants", r"restaurant count", r"ending restaurant count"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Shows the scale of the operating footprint."},
    {"key": "restaurant_revenue", "metric": "Restaurant Revenue", "tier": 1,
     "aliases": (r"\b[A-Z]{2,8} revenue\b", r"restaurant revenue"), "direction": "higher",
     "importance": "Tier 1 — Core", "impact": "Connects unit growth and same-store performance to operating scale."},
    {"key": "price_product_mix", "metric": "Menu Price + Product Mix", "tier": 2,
     "aliases": (r"menu price (?:and|\+) product mix", r"price (?:and|\+) product mix", r"price/product mix"),
     "direction": "context", "importance": "Tier 2 — High", "impact": "Explains the non-traffic component of comparable sales."},
    {"key": "digital_revenue_mix", "metric": "Digital Revenue Mix", "tier": 2,
     "aliases": (r"digital revenue mix", r"digital sales mix"), "direction": "context",
     "importance": "Tier 2 — High", "impact": "Measures digital-channel adoption and its operating mix."},
    {"key": "food_packaging_pct", "metric": "Food, Beverage & Packaging % of Revenue", "tier": 2,
     "aliases": (r"food,? beverage and packaging.*?percentage of", r"food,? beverage (?:and|&) packaging.*?%", r"food,? beverage and packaging"),
     "direction": "lower", "importance": "Tier 2 — High", "impact": "Tracks the largest restaurant input-cost bucket."},
    {"key": "labor_pct", "metric": "Labor % of Revenue", "tier": 2,
     "aliases": (r"labor.*?percentage of (?:[A-Z]{2,8} )?revenue", r"labor.*?% of (?:[A-Z]{2,8} )?revenue"), "direction": "lower",
     "importance": "Tier 2 — High", "impact": "Measures restaurant labor efficiency and wage pressure."},
    {"key": "restaurant_footprint_growth", "metric": "Restaurant Footprint Growth", "tier": 2,
     "aliases": (r"restaurant (?:footprint|count) (?:increased|growth)", r"increase in (?:the )?(?:[A-Z]{2,8} )?restaurant count"),
     "direction": "higher", "importance": "Tier 2 — High", "impact": "Normalizes expansion relative to the existing footprint."},
    {"key": "restaurant_operating_weeks", "metric": "Restaurant Operating Weeks", "tier": 2,
     "aliases": (r"restaurant operating weeks",), "direction": "higher", "importance": "Tier 2 — High",
     "impact": "Measures restaurant capacity available to generate revenue during the period."},
    {"key": "restaurant_level_profit", "metric": "Restaurant-Level Profit", "tier": 2,
     "aliases": (r"restaurant[- ]level profit(?! margin)",), "direction": "higher", "importance": "Tier 2 — High",
     "impact": "Measures restaurant profitability in dollars before corporate expenses."},
    {"key": "occupancy_pct", "metric": "Occupancy % of Revenue", "tier": 3,
     "aliases": (r"occupancy.*?percentage of (?:[A-Z]{2,8} )?revenue", r"occupancy.*?% of (?:[A-Z]{2,8} )?revenue"), "direction": "lower",
     "importance": "Tier 3 — Supporting", "impact": "Shows fixed-cost leverage from restaurant occupancy expense."},
    {"key": "other_restaurant_opex_pct", "metric": "Other Restaurant Operating Expenses %", "tier": 3,
     "aliases": (r"other restaurant operating expenses.*?percentage of", r"other restaurant operating expenses.*?%"),
     "direction": "lower", "importance": "Tier 3 — Supporting", "impact": "Tracks delivery and other controllable restaurant operating costs."},
)

_VALUE = re.compile(r"(?<![A-Za-z0-9])(?:\$\s*)?[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:%|bps|million|billion|thousand|M|B|K)?", re.I)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")


def _clean_value(raw: str) -> str:
    return re.sub(r"\s+", "", raw).replace("million", "M").replace("billion", "B").replace("thousand", "K")


def _value_number(value: str | None) -> float | None:
    if not value or value == "N/A":
        return None
    raw = value.replace("$", "").replace(",", "").replace("%", "").replace("+", "").strip()
    multiplier = 1.0
    if raw.lower().endswith("bps"):
        raw = raw[:-3]; multiplier = .01
    elif raw[-1:].upper() in {"K", "M", "B"}:
        suffix = raw[-1:].upper(); raw = raw[:-1]
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9}[suffix]
    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def _extract_values(text: str, aliases: tuple[str, ...]) -> tuple[str | None, str | None, str | None]:
    for alias in aliases:
        match = re.search(alias, text, re.I | re.S)
        if not match:
            continue
        # Tables are flattened to lines. Keep the window tight enough to avoid the
        # next metric while permitting split labels and headers.
        window = text[match.end():match.end() + 260]
        values: list[str] = []
        previous_end: int | None = None
        for token_match in _VALUE.finditer(window):
            cleaned = _clean_value(token_match.group(0))
            if _YEAR.match(cleaned):
                continue
            if previous_end is not None:
                between = window[previous_end:token_match.start()]
                # A new metric label between values means the second token is
                # not a valid prior-year comparison for the current metric.
                if re.search(r"[A-Za-z]{3,}", between):
                    break
            values.append(cleaned)
            previous_end = token_match.end()
            if len(values) == 2:
                break
        if values:
            return values[0], values[1] if len(values) > 1 else None, re.sub(r"\s+", " ", text[max(0, match.start() - 40):match.end() + 260]).strip()
    return None, None, None


def _signal(latest: str | None, prior: str | None, direction: str) -> tuple[str, str]:
    current_number, prior_number = _value_number(latest), _value_number(prior)
    if current_number is None:
        return "neutral", "Current-quarter value was not available in the verified source text."
    if prior_number is None:
        return "neutral", "Current-quarter value was reported; prior-year comparison was not disclosed."
    delta = current_number - prior_number
    if delta == 0 or direction == "context":
        return "neutral", "Stable or context-dependent versus the prior-year quarter."
    favorable = delta > 0 if direction == "higher" else delta < 0
    if favorable:
        return "positive", "Improved versus the prior-year quarter on this operating measure."
    return "negative", "Deteriorated versus the prior-year quarter; monitor the operating driver."


def _restaurant_context(filing_text: str, release_text: str) -> bool:
    text = f"{filing_text}\n{release_text}".lower()
    return text.count("restaurant") >= 8 and any(term in text for term in ("same restaurant", "same-store", "restaurant-level"))


def build_business_kpis(*, filing_text: str, release_text: str, filing_url: str,
                        release_url: str | None, fiscal_period: str, fiscal_year: int) -> dict[str, Any]:
    """Select 12–15 source-backed, company-specific operating KPIs.

    All applicable Tier 1 rows are retained. Lower tiers fill the report in tier
    order. If a restaurant source identifies fewer than 12 populated rows, Tier 1
    and the highest-priority Tier 2 rows remain visible with explicit N/A values.
    """
    if not _restaurant_context(filing_text, release_text):
        return {
            "rows": [], "selection_status": "NO_APPLICABLE_REFERENCE_CATALOGUE",
            "minimum": MIN_KPIS, "maximum": MAX_KPIS,
            "note": "No company-specific KPI catalogue matched the verified source text.",
        }

    rows = []
    for definition in RESTAURANT_KPIS:
        sec_latest, sec_prior, sec_excerpt = _extract_values(filing_text, definition["aliases"])
        ir_latest, ir_prior, ir_excerpt = _extract_values(release_text, definition["aliases"])
        found_sec, found_ir = sec_latest is not None, ir_latest is not None
        if found_ir and found_sec and (ir_latest, ir_prior) == (sec_latest, sec_prior):
            source = "IR/SEC"
        elif found_ir:
            source = "IR"
        else:
            source = "SEC"
        latest = ir_latest if found_ir else sec_latest
        prior = ir_prior if found_ir and ir_prior is not None else sec_prior
        excerpt = ir_excerpt if found_ir else sec_excerpt
        signal, analyst_view = _signal(latest, prior, definition["direction"])
        rows.append({
            "key": definition["key"], "metric": definition["metric"],
            "latest_quarter": latest or "N/A", "latest_period": f"{fiscal_period} {fiscal_year}",
            "prior_year_quarter": prior or "N/A", "prior_period": f"{fiscal_period} {fiscal_year - 1}",
            "analyst_view": analyst_view, "source": source if source in ALLOWED_SOURCES else "SEC",
            "importance": definition["importance"], "tier": definition["tier"], "signal": signal,
            "impact": definition["impact"], "directionality": definition["direction"],
            "citation": {
                "source": source if source in ALLOWED_SOURCES else "SEC",
                "url": release_url if found_ir and release_url else filing_url,
                "filing_url": filing_url if found_sec else None,
                "ir_url": release_url if found_ir else None,
                "excerpt": excerpt,
            },
            "available": latest is not None,
        })

    tier_one = [row for row in rows if row["tier"] == 1]
    lower_available = [row for row in rows if row["tier"] > 1 and row["available"]]
    lower_missing = [row for row in rows if row["tier"] > 1 and not row["available"]]
    selected = tier_one + lower_available
    if len(selected) < MIN_KPIS:
        selected.extend(lower_missing[:MIN_KPIS - len(selected)])
    # The supplied reporting recommendation permits 12–15 rows. Select 12 so
    # every complete result remains legible inside the validated A4 layout.
    report_limit = min(MAX_KPIS, max(MIN_KPIS, len(tier_one)))
    selected = selected[:report_limit]
    return {
        "rows": selected,
        "selection_status": "COMPLETE" if len(selected) >= MIN_KPIS else "INCOMPLETE",
        "minimum": MIN_KPIS, "maximum": MAX_KPIS,
        "source_policy": ["IR", "SEC", "IR/SEC"],
        "note": "All Tier 1 metrics are retained; lower tiers are selected by importance and source availability.",
    }
