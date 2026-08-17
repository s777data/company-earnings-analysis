#!/usr/bin/env python3
"""Source-derived company KPI registry and dashboard selection.

The registry is intentionally company-neutral: analysts derive metrics from the
current company's official IR materials and SEC earnings filing, then upsert the
observations here. Runtime code selects the twelve highest-importance rows for
the requested company and period; it contains no industry catalogue.

The registry is stored as JSON with this structure:
[
  {
    "COMPANY": "Applied Materials, Inc.",
    "TICKER": "AMAT",
    "SECTOR": "Semiconductor Equipment",
    "metric": "Semiconductor Systems Revenue",
    "details_map": {
      "2026-08-16": {
        "latest_quarter_value": "Q2 2026: $5.965B",
        "last_year_quarter_value": "Q2 2025: $5.401B",
        "analyst_view": "Core equipment revenue grew 10.4% YoY...",
        "source": "IR/SEC",
        "importance": "Tier 1 — Core"
      }
    }
  }
]
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ALLOWED_SOURCES = {"IR", "SEC", "IR/SEC"}
DASHBOARD_KPI_LIMIT = 12

# Default JSON reference path
DEFAULT_REFERENCE_PATH = Path(__file__).resolve().parents[1] / "references" / "KPI_derived_reference.json"

# Legacy text path for backwards compatibility (if JSON doesn't exist)
LEGACY_REFERENCE_PATH = Path(__file__).resolve().parents[1] / "references" / "KPI_derived_reference.txt"

REFERENCE_FIELDS = (
    "company", "ticker", "sector", "metric", "latest_quarter", "prior_year_quarter",
    "analyst_view", "source", "importance", "date_added",
)


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


def _load_json_references(path: str | Path) -> list[dict[str, Any]]:
    """Load KPI references from JSON format."""
    reference = Path(path)
    if not reference.exists():
        return []
    try:
        data = json.loads(reference.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise RuntimeError(f"KPI_REFERENCE_INVALID_JSON: {reference}: expected array")
        return data
    except json.JSONDecodeError as e:
        raise RuntimeError(f"KPI_REFERENCE_JSON_DECODE_ERROR: {reference}: {e}")


def _convert_json_to_flat_rows(json_data: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert JSON format with details_map to flat rows for processing."""
    rows = []
    for metric_obj in json_data:
        company = metric_obj.get("COMPANY", "")
        ticker = metric_obj.get("TICKER", "")
        sector = metric_obj.get("SECTOR", "")
        metric = metric_obj.get("metric", "")
        details_map = metric_obj.get("details_map", {})
        
        # Use the most recent date_added entry
        if details_map:
            latest_date = max(details_map.keys())
            details = details_map[latest_date]
            row = {
                "company": company,
                "ticker": ticker,
                "sector": sector,
                "metric": metric,
                "latest_quarter": details.get("latest_quarter_value", "N/A"),
                "prior_year_quarter": details.get("last_year_quarter_value", "N/A"),
                "analyst_view": details.get("analyst_view", ""),
                "source": details.get("source", ""),
                "importance": details.get("importance", ""),
                "date_added": latest_date,
            }
            rows.append(row)
    return rows


def read_derived_kpis(path: str | Path = DEFAULT_REFERENCE_PATH) -> list[dict[str, str]]:
    """Read and validate the KPI reference from JSON format.
    
    Falls back to legacy pipe-delimited text format if JSON doesn't exist.
    """
    reference = Path(path)
    
    # Try JSON format first
    if reference.suffix == ".json" and reference.exists():
        json_data = _load_json_references(reference)
        return _convert_json_to_flat_rows(json_data)
    
    # Try legacy text format
    if reference.suffix == ".txt" and reference.exists():
        # For backward compatibility, we still support reading the old format
        return _read_legacy_text_format(reference)
    
    # If the default path doesn't exist, check if we should fall back
    if path == DEFAULT_REFERENCE_PATH and LEGACY_REFERENCE_PATH.exists():
        return _read_legacy_text_format(LEGACY_REFERENCE_PATH)
    
    return []


def _read_legacy_text_format(reference: Path) -> list[dict[str, str]]:
    """Read legacy pipe-delimited text format."""
    lines = reference.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    
    # Check if it's the old header format
    legacy_header = (
        "COMPANY|TICKER|SECTOR|metric|latest quarter value( eg,Q2 2026)|"
        "last year quarter value ( eg,Q2 2025)|Analyst_view|source|importance|date_added"
    )
    
    # If no header or doesn't match, try to parse as-is
    if lines[0].strip() != legacy_header:
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
    """Atomically upsert rows, deduped by COMPANY|TICKER|SECTOR|metric.
    
    Writes to JSON format. If path is .txt, writes legacy format for backward compatibility.
    """
    reference = Path(path)
    
    # Load existing data (from JSON or legacy)
    existing_flat = read_derived_kpis(reference)
    by_identity = {_identity(row): row for row in existing_flat}
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
        # For legacy format (.txt), preserve original date_added to maintain single-date behavior
        # For JSON format, the new date is added as a separate entry in details_map
        if reference.suffix == ".json":
            row["date_added"] = today
        else:
            row["date_added"] = (previous or {}).get("date_added") or row["date_added"] or today
        by_identity[identity] = row
    
    ordered = sorted(by_identity.values(), key=lambda row: (
        row["company"].casefold(), row["ticker"].casefold(), _importance_rank(row["importance"]),
        row["metric"].casefold(),
    ))
    
    reference.parent.mkdir(parents=True, exist_ok=True)
    
    # Write in the appropriate format based on file extension
    if reference.suffix == ".json":
        _write_json_format(reference, ordered)
    else:
        _write_legacy_format(reference, ordered)
    
    return ordered


def _write_json_format(reference: Path, ordered_rows: list[dict[str, str]]) -> None:
    """Write KPI references in JSON format with details_map."""
    # Load existing JSON to preserve historical details_map entries
    existing_json = _load_json_references(reference)
    existing_by_key = {}
    for obj in existing_json:
        key = (obj.get("COMPANY", ""), obj.get("TICKER", ""), obj.get("SECTOR", ""), obj.get("metric", ""))
        existing_by_key[key] = obj
    
    # Build new JSON structure
    result = []
    for row in ordered_rows:
        key = (row["company"], row["ticker"], row["sector"], row["metric"])
        existing = existing_by_key.get(key)
        
        if existing:
            # Update existing metric with new date entry
            details_map = existing.get("details_map", {})
            date_key = row["date_added"]
            details_map[date_key] = {
                "latest_quarter_value": row["latest_quarter"],
                "last_year_quarter_value": row["prior_year_quarter"],
                "analyst_view": row["analyst_view"],
                "source": row["source"],
                "importance": row["importance"],
            }
            result.append({
                "COMPANY": row["company"],
                "TICKER": row["ticker"],
                "SECTOR": row["sector"],
                "metric": row["metric"],
                "details_map": details_map,
            })
        else:
            # New metric
            details_map = {
                row["date_added"]: {
                    "latest_quarter_value": row["latest_quarter"],
                    "last_year_quarter_value": row["prior_year_quarter"],
                    "analyst_view": row["analyst_view"],
                    "source": row["source"],
                    "importance": row["importance"],
                }
            }
            result.append({
                "COMPANY": row["company"],
                "TICKER": row["ticker"],
                "SECTOR": row["sector"],
                "metric": row["metric"],
                "details_map": details_map,
            })
    
    temporary = reference.with_suffix(reference.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(reference)


def _write_legacy_format(reference: Path, ordered_rows: list[dict[str, str]]) -> None:
    """Write KPI references in legacy pipe-delimited text format."""
    legacy_header = (
        "COMPANY|TICKER|SECTOR|metric|latest quarter value( eg,Q2 2026)|"
        "last year quarter value ( eg,Q2 2025)|Analyst_view|source|importance|date_added"
    )
    payload = [legacy_header]
    payload.extend("|".join(_clean(row[field]) for field in REFERENCE_FIELDS) for row in ordered_rows)
    temporary = reference.with_suffix(reference.suffix + ".tmp")
    temporary.write_text("\n".join(payload) + "\n", encoding="utf-8")
    temporary.replace(reference)


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
