#!/usr/bin/env python3
"""Dimension-aware parser for SEC XBRL instance documents."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree as ET

TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenueFromContractWithCustomer", "Revenues", "SalesRevenueNet"),
    "gross_profit": ("GrossProfit",), "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"), "eps_diluted": ("EarningsPerShareDiluted",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpendituresIncurredButNotYetPaid"),
    "stock_based_compensation": ("AllocatedShareBasedCompensationExpense", "ShareBasedCompensation"),
    "depreciation_amortization": ("DepreciationDepletionAndAmortization", "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment"),
    "backlog": ("RevenueRemainingPerformanceObligation",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "total_assets": ("Assets",), "total_liabilities": ("Liabilities",),
    "total_equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "long_term_debt": ("LongTermDebtCurrent", "LongTermDebtNoncurrent", "LongTermDebt"),
    "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}

@dataclass
class Context:
    start: str | None
    end: str
    instant: bool
    dimensions: tuple[str, ...]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(root: ET.Element, name: str):
    return [item for item in root.iter() if _local(item.tag) == name]


def _contexts(root: ET.Element) -> dict[str, Context]:
    result = {}
    for node in _children(root, "context"):
        context_id = node.get("id")
        start = end = None
        instant = False
        dimensions = tuple((child.get("dimension") or "typed-dimension") for child in node.iter()
                           if _local(child.tag) in {"explicitMember", "typedMember"})
        for child in node.iter():
            local = _local(child.tag)
            if local == "startDate": start = child.text
            elif local == "endDate": end = child.text
            elif local == "instant": end, instant = child.text, True
        if context_id and end:
            result[context_id] = Context(start, end, instant, dimensions)
    return result


def _duration(context: Context) -> int:
    return 0 if context.instant or not context.start else (date.fromisoformat(context.end) - date.fromisoformat(context.start)).days + 1


def parse_xbrl_financials(content: str, report_date: str | None = None) -> dict:
    root = ET.fromstring(content)
    contexts = _contexts(root)
    facts: dict[str, list[dict]] = {key: [] for key in TAGS}
    period_focus = fiscal_year_focus = None
    reverse = {tag: metric for metric, tags in TAGS.items() for tag in tags}
    for node in root.iter():
        local = _local(node.tag)
        if local == "DocumentFiscalPeriodFocus": period_focus = (node.text or "").strip()
        if local == "DocumentFiscalYearFocus": fiscal_year_focus = (node.text or "").strip()
        metric = reverse.get(local)
        context = contexts.get(node.get("contextRef", ""))
        if not metric or not context or not node.text or context.dimensions:
            continue
        try: value = float(node.text.replace(",", ""))
        except ValueError: continue
        facts[metric].append({"value": value, "concept": local, "context": node.get("contextRef"),
                              "start": context.start, "end": context.end, "instant": context.instant,
                              "duration_days": _duration(context), "unit": node.get("unitRef"),
                              "decimals": node.get("decimals"), "dimensions": list(context.dimensions),
                              "taxonomy": node.tag.split("}")[0].lstrip("{") if "}" in node.tag else None})
    target = report_date or max((ctx.end for ctx in contexts.values()), default=None)
    result = {"fiscal_period": period_focus, "fiscal_year": fiscal_year_focus, "report_date": target, "metrics": {}}
    for metric, entries in facts.items():
        if not entries: continue
        instant_metric = metric in {"cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "backlog"}
        eligible = [entry for entry in entries if entry["end"] == target and entry["instant"] == instant_metric]
        if not eligible:
            eligible = [entry for entry in entries if entry["instant"] == instant_metric]
        if not eligible: continue
        if instant_metric:
            eligible.sort(key=lambda entry: entry["end"], reverse=True)
        else:
            # Prefer a true quarter; if unavailable retain YTD and label its duration.
            eligible.sort(key=lambda entry: (0 if 70 <= entry["duration_days"] <= 110 else 1,
                                             abs(entry["duration_days"] - 91), entry["concept"]))
        chosen = eligible[0]
        prior_candidates = [entry for entry in entries if entry["instant"] == instant_metric and entry["end"] < chosen["end"]]
        if not instant_metric:
            prior_candidates = [entry for entry in prior_candidates if abs(entry["duration_days"] - chosen["duration_days"]) <= 7]
        prior_value = None
        prior_end = None
        if prior_candidates:
            target_prior_days = 365
            prior_candidates.sort(key=lambda entry: abs((date.fromisoformat(chosen["end"]) - date.fromisoformat(entry["end"])).days - target_prior_days))
            prior = prior_candidates[0]
            if abs((date.fromisoformat(chosen["end"]) - date.fromisoformat(prior["end"])).days - target_prior_days) <= 45:
                prior_value = prior["value"]
                prior_end = prior["end"]
        
        # Find prior quarter (approximately 90 days before)
        prior_q_value = None
        prior_q_candidates = [entry for entry in entries if entry["instant"] == instant_metric and entry["end"] < chosen["end"]]
        if not instant_metric:
            prior_q_candidates = [entry for entry in prior_q_candidates if abs(entry["duration_days"] - chosen["duration_days"]) <= 7]
        if prior_q_candidates:
            target_prior_q_days = 91  # ~1 quarter
            prior_q_candidates.sort(key=lambda entry: abs((date.fromisoformat(chosen["end"]) - date.fromisoformat(entry["end"])).days - target_prior_q_days))
            prior_q = prior_q_candidates[0]
            if abs((date.fromisoformat(chosen["end"]) - date.fromisoformat(prior_q["end"])).days - target_prior_q_days) <= 45:
                prior_q_value = prior_q["value"]
        
        result["metrics"][metric] = {**chosen, "prior_value": prior_value, "prior_end": prior_end, "prior_q_value": prior_q_value}
    return result
