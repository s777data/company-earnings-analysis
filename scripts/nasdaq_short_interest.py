#!/usr/bin/env python3
"""Read official Nasdaq-reported short-interest data without unofficial mirrors."""
from __future__ import annotations

from typing import Any

import requests

NASDAQ_BASE = "https://api.nasdaq.com/api/quote"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Hermes earnings research)",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def _number(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def fetch_short_interest(symbol: str) -> dict[str, Any]:
    """Return the newest official Nasdaq short-interest observation.

    Nasdaq reports settlement-date short interest and days to cover. Public float
    is intentionally not inferred here; callers must supply a separately verified
    float before calculating Short Interest % of Float.
    """
    ticker = symbol.upper()
    url = f"{NASDAQ_BASE}/{ticker}/short-interest?assetclass=stocks"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = (((payload.get("data") or {}).get("shortInterestTable") or {}).get("rows") or [])
    if not rows:
        raise RuntimeError("Nasdaq did not return short-interest observations")
    latest = rows[0]
    short_interest = _number(latest.get("interest"))
    days_to_cover = _number(latest.get("daysToCover"))
    average_volume = _number(latest.get("avgDailyShareVolume"))
    if short_interest is None or days_to_cover is None:
        raise RuntimeError("Nasdaq short-interest observation is incomplete")
    return {
        "short_interest": short_interest,
        "average_daily_volume": average_volume,
        "days_to_cover": days_to_cover,
        "settlement_date": latest.get("settlementDate"),
        "source": "Nasdaq official short-interest report",
        "source_url": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/short-interest",
    }
