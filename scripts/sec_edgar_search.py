#!/usr/bin/env python3
"""SEC submissions search with fiscal-period-safe metadata and enforced filters."""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import requests

SEC_DATA = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
USER_AGENT = os.getenv("SEC_USER_AGENT", "Hermes earnings research contact@example.com")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def get_cik(ticker: str) -> str | None:
    response = requests.get(f"{SEC_WWW}/files/company_tickers.json", headers=HEADERS, timeout=20)
    response.raise_for_status()
    wanted = ticker.upper()
    for row in response.json().values():
        if row.get("ticker", "").upper() == wanted:
            return str(row["cik_str"]).zfill(10)
    return None


def _rows(recent: dict[str, list[Any]]) -> list[dict[str, Any]]:
    count = len(recent.get("accessionNumber", []))
    rows = []
    for index in range(count):
        rows.append({key: values[index] if index < len(values) else None for key, values in recent.items()})
    return rows


def _matches_query(row: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    query_words = {word for word in query.lower().replace("-", " ").split() if word not in {"press", "release"}}
    searchable = " ".join(str(row.get(key) or "") for key in ("form", "items", "primaryDocDescription", "primaryDocument")).lower()
    if "earnings" in query_words:
        return "2.02" in searchable or any(term in searchable for term in ("earning", "results", "financial condition"))
    return all(word in searchable for word in query_words)


def search_filings(ticker: str, form_types: list[str] | None = None, start_date: str | None = None,
                   end_date: str | None = None, limit: int = 10, query: str | None = None) -> list[dict[str, Any]]:
    cik = get_cik(ticker)
    if not cik:
        return []
    response = requests.get(f"{SEC_DATA}/submissions/CIK{cik}.json", headers=HEADERS, timeout=30)
    response.raise_for_status()
    submission = response.json()
    results = []
    for row in _rows(submission.get("filings", {}).get("recent", {})):
        if form_types and row.get("form") not in form_types:
            continue
        filing_date = row.get("filingDate")
        if not filing_date or (start_date and filing_date < start_date) or (end_date and filing_date > end_date):
            continue
        if not _matches_query(row, query):
            continue
        accession_dashed = row["accessionNumber"]
        accession = accession_dashed.replace("-", "")
        primary = row.get("primaryDocument")
        results.append({
            "ticker": ticker.upper(), "cik": cik, "company_name": submission.get("name"),
            "accession_number": accession, "accession_number_dashed": accession_dashed,
            "form_type": row.get("form"), "filing_date": filing_date,
            "report_date": row.get("reportDate") or None, "acceptance_datetime": row.get("acceptanceDateTime"),
            "items": row.get("items") or "", "primary_document": primary,
            "primary_doc_description": row.get("primaryDocDescription") or "",
            "fiscal_year_end": submission.get("fiscalYearEnd"),
            "sector": submission.get("sicDescription") or "Unclassified",
            "url": f"{SEC_WWW}/Archives/edgar/data/{int(cik)}/{accession}/{primary}" if primary else None,
        })
        if len(results) >= limit:
            break
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--forms", nargs="+", default=["10-Q"])
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(search_filings(args.ticker, args.forms, limit=args.limit, query=args.query), indent=2))
