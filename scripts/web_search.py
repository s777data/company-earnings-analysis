#!/usr/bin/env python3
"""Web-only earnings-call transcript discovery and validation."""
from __future__ import annotations

import os
import re
import hashlib
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.9",
           "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1"}
ALLOWED = ("stockanalysis.com", "seekingalpha.com", "fool.com", "marketbeat.com", "streetinsider.com", "investing.com")


def fetch_page_content(url: str) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code != 200: return None
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]): tag.decompose()
        text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
        if len(text) >= 5000: return text
    except requests.RequestException:
        pass
    try:
        response = requests.get(f"https://r.jina.ai/http://{url}", timeout=45)
        if response.status_code == 200 and len(response.text) >= 5000: return response.text
    except requests.RequestException:
        pass
    return None


def _validate(text: str, ticker: str, quarter: str, year: int) -> tuple[bool, list[str]]:
    lower = text.lower()
    failures = []
    if len(text) < 8000: failures.append("transcript is too short")
    if ticker.lower() not in lower: failures.append("ticker is absent")
    quarter_terms = {quarter.lower(), quarter.lower().replace("fy", "fiscal "), f"{year}"}
    if not any(term in lower for term in quarter_terms): failures.append("quarter/year is absent")
    prepared = any(term in lower for term in (
        "prepared remarks", "opening remarks", "initial remarks", "business update",
        "chief executive officer", "chief financial officer", "chairman and ceo",
        "ceo", "cfo", "co-founder and ceo", "founder and ceo",
    ))
    qa = any(term in lower for term in ("question-and-answer", "question and answer", "q&a", "q and a", "our first question", "analyst"))
    if not prepared: failures.append("prepared remarks were not detected")
    if not qa: failures.append("analyst Q&A was not detected")
    return not failures, failures


def _stockanalysis(ticker: str, quarter_number: int, year: int) -> list[str]:
    base = f"https://stockanalysis.com/stocks/{ticker.lower()}/transcripts/"
    try:
        html = requests.get(base, headers=HEADERS, timeout=25).text
    except requests.RequestException:
        return []
    pattern = rf'href=["\'](/stocks/{re.escape(ticker.lower())}/transcripts/\d+-q{quarter_number}-{year}/)["\']'
    return [f"https://stockanalysis.com{path}" for path in dict.fromkeys(re.findall(pattern, html, re.I))]


def _duckduckgo(query: str, limit: int = 8) -> list[str]:
    try:
        response = requests.get("https://html.duckduckgo.com/html/", params={"q": query}, headers=HEADERS, timeout=25)
        soup = BeautifulSoup(response.text, "html.parser")
        urls = []
        for link in soup.select("a.result__a"):
            url = link.get("href", "")
            if any(domain in url for domain in ALLOWED): urls.append(url)
        return list(dict.fromkeys(urls))[:limit]
    except requests.RequestException:
        return []


def find_transcript(ticker: str, fiscal_period: str, fiscal_year: int) -> dict[str, Any]:
    match = re.search(r"Q([1-4])", fiscal_period.upper())
    if not match: raise RuntimeError(f"A quarterly fiscal period is required, received {fiscal_period!r}")
    quarter_number = int(match.group(1))
    candidates = _stockanalysis(ticker, quarter_number, fiscal_year)
    for domain in ALLOWED:
        candidates.extend(_duckduckgo(f"site:{domain} {ticker} Q{quarter_number} {fiscal_year} earnings call transcript"))
    attempts = []
    for url in dict.fromkeys(candidates):
        content = fetch_page_content(url)
        if not content:
            attempts.append({"url": url, "status": "fetch_failed"}); continue
        valid, failures = _validate(content, ticker, f"Q{quarter_number}", fiscal_year)
        attempts.append({"url": url, "status": "accepted" if valid else "rejected", "reasons": failures})
        if valid:
            call_date = None
            call_heading_date = re.search(
                rf"Earnings\s+Call\s*:\s*Q{quarter_number}\s+{fiscal_year}\s+"
                r"([A-Z][a-z]{2,8})\s+([0-3]?\d),\s+(20\d{2})",
                content[:5000], re.I,
            )
            if call_heading_date:
                date_text = f"{call_heading_date.group(1)} {call_heading_date.group(2)}, {call_heading_date.group(3)}"
                for date_format in ("%B %d, %Y", "%b %d, %Y"):
                    try:
                        call_date = datetime.strptime(date_text, date_format).date().isoformat()
                        break
                    except ValueError:
                        pass
            return {"content": content, "url": url, "source": next((d for d in ALLOWED if d in url), "web"),
                    "fiscal_period": f"Q{quarter_number}", "fiscal_year": fiscal_year, "call_date": call_date,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "attempts": attempts}
    raise RuntimeError("EARNINGS_CALL_TRANSCRIPT_UNAVAILABLE: no complete correct-quarter transcript with prepared remarks and analyst Q&A was verified")

# Backward-compatible alias used by older callers.
def web_search(query: str, max_results: int = 10, source_filter=None):
    return [{"url": url} for url in _duckduckgo(query, max_results)]


def fetch_forward_pe_ntm(ticker: str) -> tuple[float | None, str | None]:
    """
    Fetch Forward P/E (NTM) from StockAnalysis.com which uses S&P Global Market Intelligence.
    Returns (forward_pe, source_url) or (None, None) if not available.
    """
    url = f"https://stockanalysis.com/stocks/{ticker.lower()}/statistics/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=25)
        if response.status_code != 200:
            return None, None
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        
        # Look for Forward P/E pattern - StockAnalysis format: "forward PE ratio is 113.27"
        patterns = [
            r"forward\s+pe\s+ratio\s+is\s+([\d,]+\.?\d*)",
            r"forward\s+p/e\s+ratio\s+is\s+([\d,]+\.?\d*)",
            r"forward\s+pe\s*[:\-]?\s*([\d,]+\.?\d*)\s*x",
            r"forward\s+p/e\s*[:\-]?\s*([\d,]+\.?\d*)\s*x",
            r"forward\s+p/e\s*ratio\s*[:\-]?\s*([\d,]+\.?\d*)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1).replace(",", ""))
                    return value, url
                except ValueError:
                    continue
        return None, None
    except requests.RequestException:
        return None, None
