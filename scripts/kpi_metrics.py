#!/usr/bin/env python3
"""Source-derived company KPI registry and dashboard selection.

The registry is intentionally company-neutral: analysts derive metrics from the
current company's official IR materials and SEC earnings filing, then upsert the
observations here. Runtime code selects the twelve highest-importance rows for
the requested company and period; it contains no industry catalogue.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ALLOWED_SOURCES = {"IR", "SEC", "IR/SEC"}
DASHBOARD_KPI_LIMIT = 12
REFERENCE_HEADER = (
    "COMPANY|TICKER|SECTOR|metric|latest quarter value( eg,Q2 2026)|"
    "last year quarter value ( eg,Q2 2025)|Analyst_view|source|importance|date_added"
)
REFERENCE_FIELDS = (
    "company", "ticker", "sector", "metric", "latest_quarter", "prior_year_quarter",
    "analyst_view", "source", "importance", "date_added",
)
DEFAULT_REFERENCE_PATH = Path(__file__).resolve().parents[1] / "references" / "KPI_derived_reference.txt"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("|", "/").split()).strip()


def _identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(_clean(row.get(field)).casefold() for field in ("company", "ticker", "sector", "metric"))


def _importance_rank(value: str) -> tuple[int, str]:
    text = _clean(value).casefold()
    match = re.search(r"(?:tier|t)\s*([1-4])", text)
    if match:
        return int(match.group(1)), text
    if "core" in text:
        return 1, text
    if "high" in text:
        return 2, text
    if "support" in text:
        return 3, text
    return 4, text


def _period_value(cell: str, fallback_period: str) -> tuple[str, str]:
    text = _clean(cell) or "N/A"
    match = re.match(r"^(Q[1-4]\s+(?:FY)?\d{4})\s*:\s*(.+)$", text, re.I)
    if not match:
        return fallback_period, text
    period = match.group(1).upper().replace(" FY", " ")
    return period, match.group(2).strip() or "N/A"


def _signal(analyst_view: str) -> str:
    text = analyst_view.casefold()
    adverse = ("declin", "contract", "deterior", "pressure", "weaker", "unfavorable", "risk", "lower mix")
    favorable = ("grow", "improv", "expand", "strength", "accelerat", "gain", "record", "higher", "leadership")
    has_adverse = any(term in text for term in adverse)
    has_favorable = any(term in text for term in favorable)
    if has_adverse and not has_favorable:
        return "negative"
    if has_favorable and not has_adverse:
        return "positive"
    return "neutral"


def read_derived_kpis(path: str | Path = DEFAULT_REFERENCE_PATH) -> list[dict[str, str]]:
    """Read and validate the pipe-delimited official KPI reference."""
    reference = Path(path)
    if not reference.exists():
        return []
    lines = reference.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    if lines[0].strip() != REFERENCE_HEADER:
        raise RuntimeError(f"KPI_REFERENCE_INVALID_HEADER: {reference}")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for line_number, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        values = line.split("|")
        if len(values) != len(REFERENCE_FIELDS):
            raise RuntimeError(f"KPI_REFERENCE_INVALID_ROW: {reference}:{line_number}")
        row = dict(zip(REFERENCE_FIELDS, map(_clean, values)))
        if row["source"] not in ALLOWED_SOURCES:
            raise RuntimeError(f"KPI_REFERENCE_INVALID_SOURCE: {reference}:{line_number}")
        identity = _identity(row)
        if identity in seen:
            raise RuntimeError(f"KPI_REFERENCE_DUPLICATE: {reference}:{line_number}")
        seen.add(identity)
        rows.append(row)
    return rows


def upsert_derived_kpis(rows: Iterable[dict[str, Any]], path: str | Path = DEFAULT_REFERENCE_PATH,
                         added_on: str | None = None) -> list[dict[str, str]]:
    """Atomically upsert rows, deduped by COMPANY|TICKER|SECTOR|metric."""
    reference = Path(path)
    existing = read_derived_kpis(reference)
    by_identity = {_identity(row): row for row in existing}
    today = added_on or date.today().isoformat()
    for incoming in rows:
        row = {field: _clean(incoming.get(field)) for field in REFERENCE_FIELDS}
        missing = [field for field in ("company", "ticker", "sector", "metric", "analyst_view", "source", "importance")
                   if not row[field]]
        if missing:
            raise ValueError(f"KPI row missing required fields: {', '.join(missing)}")
        if row["source"] not in ALLOWED_SOURCES:
            raise ValueError(f"KPI source must be one of {sorted(ALLOWED_SOURCES)}")
        row["ticker"] = row["ticker"].upper()
        row["latest_quarter"] = row["latest_quarter"] or "N/A"
        row["prior_year_quarter"] = row["prior_year_quarter"] or "N/A"
        identity = _identity(row)
        previous = by_identity.get(identity)
        row["date_added"] = (previous or {}).get("date_added") or row["date_added"] or today
        by_identity[identity] = row
    ordered = sorted(by_identity.values(), key=lambda row: (
        row["company"].casefold(), row["ticker"].casefold(), _importance_rank(row["importance"]),
        row["metric"].casefold(),
    ))
    reference.parent.mkdir(parents=True, exist_ok=True)
    payload = [REFERENCE_HEADER]
    payload.extend("|".join(_clean(row[field]) for field in REFERENCE_FIELDS) for row in ordered)
    temporary = reference.with_suffix(reference.suffix + ".tmp")
    temporary.write_text("\n".join(payload) + "\n", encoding="utf-8")
    temporary.replace(reference)
    return ordered


def build_business_kpis(*, company: str, ticker: str, sector: str, filing_url: str,
                        release_url: str | None, fiscal_period: str, fiscal_year: int,
                        ir_url: str | None = None,
                        reference_path: str | Path = DEFAULT_REFERENCE_PATH, **_: Any) -> dict[str, Any]:
    """Load the top twelve source-derived KPIs for one company and fiscal period."""
    current_period = f"{fiscal_period.upper()} {fiscal_year}"
    prior_period = f"{fiscal_period.upper()} {fiscal_year - 1}"
    candidates = [row for row in read_derived_kpis(reference_path)
                  if row["ticker"].casefold() == ticker.casefold()]
    selected: list[dict[str, Any]] = []
    stale_period_rows = 0
    for row in sorted(candidates, key=lambda item: (_importance_rank(item["importance"]), item["metric"].casefold())):
        latest_period, latest_value = _period_value(row["latest_quarter"], current_period)
        prior_row_period, prior_value = _period_value(row["prior_year_quarter"], prior_period)
        if latest_period != current_period:
            stale_period_rows += 1
            continue
        source = row["source"]
        primary_url = filing_url if source == "SEC" else (ir_url or release_url or filing_url)
        selected.append({
            "key": re.sub(r"[^a-z0-9]+", "_", row["metric"].casefold()).strip("_"),
            "metric": row["metric"], "latest_quarter": latest_value, "latest_period": latest_period,
            "prior_year_quarter": prior_value, "prior_period": prior_row_period,
            "analyst_view": row["analyst_view"], "source": source,
            "importance": row["importance"], "tier": _importance_rank(row["importance"])[0],
            "signal": _signal(row["analyst_view"]), "available": latest_value != "N/A",
            "citation": {"source": source, "url": primary_url,
                         "filing_url": filing_url if source in {"SEC", "IR/SEC"} else None,
                         "ir_url": ir_url if source in {"IR", "IR/SEC"} else None},
            "company": company, "ticker": ticker.upper(), "sector": sector,
            "date_added": row["date_added"],
        })
        if len(selected) == DASHBOARD_KPI_LIMIT:
            break
    status = "COMPLETE" if len(selected) == DASHBOARD_KPI_LIMIT else "INCOMPLETE"
    if not candidates:
        status = "DERIVED_REFERENCE_REQUIRED"
    return {
        "rows": selected, "selection_status": status,
        "display_limit": DASHBOARD_KPI_LIMIT, "available_reference_rows": len(candidates),
        "stale_period_rows": stale_period_rows,
        "reference_path": str(Path(reference_path)),
        "source_policy": sorted(ALLOWED_SOURCES),
        "note": ("Top source-derived metrics selected by importance from KPI_derived_reference.txt."
                 if selected else "No current-period source-derived KPI rows exist for this ticker."),
    }
