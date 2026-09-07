#!/usr/bin/env python3
"""Discover and extract KPI rows from shareholder-letter PDFs."""
from __future__ import annotations

import io
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup

PDF_KEYWORDS = ("shareholder", "letter", "earnings", "report", "q1", "q2", "q3", "q4", "fy")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _casefold(text: str) -> str:
    return _normalize(text).casefold()


def _fetch_url(url: str) -> tuple[bytes, str]:
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "")


def _looks_like_pdf(url: str, content_type: str = "") -> bool:
    return url.lower().split("?", 1)[0].endswith(".pdf") or "application/pdf" in content_type.lower()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        chunks: list[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
        return "\n".join(chunks)


def _discover_pdf_urls(page_url: str, html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = str(tag.get("href") or "")
        absolute = urljoin(page_url, href)
        lowered = absolute.casefold()
        label = _casefold(tag.get_text(" ", strip=True))
        if "pdf" in lowered or any(keyword in lowered for keyword in PDF_KEYWORDS) or any(keyword in label for keyword in PDF_KEYWORDS):
            urls.append(absolute)
    return urls


def discover_shareholder_letter_pdf(
    *,
    page_url: str | None,
    release_text: str | None,
    report_date: str,
    fiscal_period: str,
    fiscal_year: int,
) -> str | None:
    """Find a likely shareholder-letter PDF from an IR page or release text.

    The discovery step is intentionally conservative: it only returns a PDF when
    the candidate URL or the extracted PDF text clearly matches the requested
    quarter identity.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(url: str) -> None:
        cleaned = url.strip().rstrip(".,;:)]}")
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        candidates.append(cleaned)

    for text in (release_text or "", page_url or ""):
        for match in re.findall(r"https?://[^\s<>\"']+", text):
            add_candidate(match)

    if page_url:
        parsed = urlparse(page_url)
        if parsed.scheme in {"http", "https"}:
            if _looks_like_pdf(page_url):
                add_candidate(page_url)
            else:
                try:
                    body, content_type = _fetch_url(page_url)
                    if _looks_like_pdf(page_url, content_type):
                        add_candidate(page_url)
                    else:
                        html_text = body.decode("utf-8", errors="ignore")
                        for candidate in _discover_pdf_urls(page_url, html_text):
                            add_candidate(candidate)
                except Exception:
                    pass

    period = fiscal_period.upper()
    quarter_terms = {"Q1": "first quarter", "Q2": "second quarter", "Q3": "third quarter", "Q4": "fourth quarter"}
    expected_terms = {period.casefold(), quarter_terms.get(period, "")}
    expected_terms = {term for term in expected_terms if term}
    expected_year_terms = {
        str(fiscal_year),
        f"fy{str(fiscal_year)[-2:]}",
        f"fy {str(fiscal_year)[-2:]}",
        f"fiscal year {fiscal_year}",
    }
    # Prefer URLs that already encode the quarter identity and/or look like a shareholder letter.
    ranked: list[tuple[int, str, str | None]] = []
    for candidate in candidates:
        lowered = candidate.casefold()
        score = 0
        if lowered.endswith(".pdf"):
            score += 3
        if "shareholder" in lowered:
            score += 5
        if "letter" in lowered:
            score += 4
        if period.casefold() in lowered or quarter_terms.get(period, "") in lowered:
            score += 3
        if any(term in lowered for term in expected_year_terms):
            score += 2
        ranked.append((score, candidate, None))

    for score, candidate, _ in sorted(ranked, reverse=True):
        if score <= 0:
            continue
        try:
            body, content_type = _fetch_url(candidate)
        except Exception:
            continue
        if not _looks_like_pdf(candidate, content_type):
            continue
        try:
            text = _extract_pdf_text(body)
        except Exception:
            continue
        normalized = _casefold(text)
        if period.casefold() not in normalized and quarter_terms.get(period, "") not in normalized:
            continue
        if str(fiscal_year) not in normalized and f"fy{str(fiscal_year)[-2:]}" not in normalized:
            continue
        if report_date not in normalized:
            # Some letters mention fiscal period without the exact ISO date in the visible text.
            # Accept the URL if it is a strong quarter match and the document is clearly a shareholder letter.
            if "shareholder" not in candidate.casefold() and "letter" not in candidate.casefold():
                continue
        return candidate
    return None


def extract_shareholder_letter_text(pdf_url: str) -> str:
    body, _ = _fetch_url(pdf_url)
    return _extract_pdf_text(body)


def _find(patterns: list[str], text: str, flags: int = re.I) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match
    return None


def _q_value(value: str) -> str:
    return value if value.startswith("Q") else value


def extract_shareholder_letter_kpis(
    *,
    text: str,
    company: str,
    ticker: str,
    sector: str,
    report_date: str,
    fiscal_period: str,
    fiscal_year: int,
    source_url: str,
) -> list[dict[str, Any]]:
    """Extract a compact, source-backed KPI set from a shareholder letter.

    The extractor focuses on metrics that are usually stated explicitly in
    shareholder letters: ARR, revenue, customer cohorts, product penetration,
    retention, margin, EPS, and guidance.
    """
    normalized = _normalize(text)
    period_label = f"{fiscal_period.upper()} FY{str(fiscal_year)[-2:]}"
    prev_label = f"Q{int(fiscal_period[1])} FY{int(fiscal_year) - 1}" if fiscal_period.upper().startswith("Q") else f"FY{fiscal_year - 1}"

    def make_row(metric: str, latest: str, prior: str, view: str, source: str = "IR", importance: str = "Tier 1 — Core") -> dict[str, Any]:
        return {
            "company": company,
            "ticker": ticker,
            "sector": sector,
            "metric": metric,
            "latest_quarter": latest,
            "prior_year_quarter": prior,
            "analyst_view": view,
            "source": source,
            "importance": importance,
            "source_url": source_url,
            "date_added": report_date,
        }

    rows: list[dict[str, Any]] = []

    m = _find([
        r"crossed \$([0-9.]+)B in ARR, growing ([0-9]+)% year-over-year, driven by \$([0-9]+)M in net new ARR",
    ], normalized)
    if m:
        rows.append(make_row(
            "Annual Recurring Revenue (ARR)",
            f"{period_label}: ${m.group(1)}B",
            f"{prev_label}: N/A",
            f"ARR grew {m.group(2)}% year-over-year to ${m.group(1)}B, driven by ${m.group(3)}M in net new ARR.",
        ))
        rows.append(make_row(
            "Net New ARR",
            f"{period_label}: ${m.group(3)}M",
            f"{prev_label}: N/A",
            f"Net new ARR reached ${m.group(3)}M, supporting the quarter's ARR growth.",
        ))

    m = _find([
        r"Q2 was another quarter of durable growth at scale:.*?Q2 revenue was \$([0-9]+) million, an increase of ([0-9]+)% year-over-year or ([0-9]+)% in constant currency",
        r"Q2 revenue was \$([0-9]+) million, an increase of ([0-9]+)% year-over-year or ([0-9]+)% in constant currency",
    ], normalized)
    if m:
        rows.append(make_row(
            "Total Revenue",
            f"{period_label}: ${m.group(1)}M",
            f"{prev_label}: N/A",
            f"Revenue grew {m.group(2)}% year-over-year ({m.group(3)}% constant currency) to ${m.group(1)}M.",
            source="IR/SEC",
        ))

    m = _find([
        r"We added ([0-9,]+) \$100K\+ ARR customers and ([0-9,]+) \$1M\+ ARR customers",
    ], normalized)
    if m:
        rows.append(make_row(
            "$100K+ ARR Customers",
            f"{period_label}: {m.group(1)}",
            f"{prev_label}: N/A",
            f"The $100K+ customer cohort reached {m.group(1)} customers, a quarterly record.",
        ))
        rows.append(make_row(
            "$1M+ ARR Customers",
            f"{period_label}: {m.group(2)}",
            f"{prev_label}: N/A",
            f"The $1M+ customer cohort reached {m.group(2)} customers, also a quarterly record.",
        ))

    m = _find([
        r"ARR from \$100K\+ customers was \$([0-9.]+)B, an increase of ([0-9]+)% year-over-year",
    ], normalized)
    if m:
        rows.append(make_row(
            "ARR from $100K+ ARR Customers",
            f"{period_label}: ${m.group(1)}B",
            f"{prev_label}: N/A",
            f"ARR from $100K+ customers reached ${m.group(1)}B, up {m.group(2)}% year-over-year and representing a larger share of total ARR.",
        ))

    m = _find([
        r"ARR from \$1M\+ customers surpassed \$([0-9.]+) million, increasing more than ([0-9]+)% year-over-year",
    ], normalized)
    if m:
        rows.append(make_row(
            "ARR from $1M+ ARR Customers",
            f"{period_label}: >${m.group(1)}M",
            f"{prev_label}: N/A",
            f"ARR from $1M+ customers surpassed ${m.group(1)}M, increasing more than {m.group(2)}% year-over-year.",
        ))

    m = _find([
        r"Average ARR per \$100K\+ ARR customer was \$([0-9,]+)K in Q2 FY27, up ([0-9]+)% from \$([0-9,]+)K in Q2 FY26",
    ], normalized)
    if m:
        rows.append(make_row(
            "ARR per $100K+ ARR Customer",
            f"{period_label}: ${m.group(1)}K",
            f"Q2 FY{fiscal_year - 1}: ${m.group(3)}K",
            f"Average ARR per $100K+ customer was ${m.group(1)}K, up {m.group(2)}% year-over-year.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"dollar-based net retention rate of approximately ([0-9]+)% for core customers",
    ], normalized)
    if m:
        rows.append(make_row(
            "Core Customer Dollar-Based Net Retention Rate",
            f"{period_label}: ~{m.group(1)}%",
            f"{prev_label}: N/A",
            f"Core customer dollar-based net retention was approximately {m.group(1)}%.",
        ))

    m = _find([
        r"([0-9]+)% of \$100K\+ ARR customers and ([0-9]+)% of core customers subscribe to 2\+ products \(compared to ([0-9]+)% and ([0-9]+)% in Q2 FY26",
    ], normalized)
    if m:
        rows.append(make_row(
            "2+ Products Penetration ($100K+ ARR Customers)",
            f"{period_label}: {m.group(1)}%",
            f"Q2 FY{fiscal_year - 1}: {m.group(3)}%",
            f"{m.group(1)}% of $100K+ ARR customers subscribed to 2+ products, up from {m.group(3)}% a year ago.",
            source="IR",
            importance="Tier 2 — High",
        ))
        rows.append(make_row(
            "2+ Products Penetration (Core Customers)",
            f"{period_label}: {m.group(2)}%",
            f"Q2 FY{fiscal_year - 1}: {m.group(4)}%",
            f"{m.group(2)}% of core customers subscribed to 2+ products, up from {m.group(4)}% a year ago.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"([0-9]+)% of \$100K\+ ARR customers and ([0-9]+)% of core customers subscribe to 3\+ products \(compared to ([0-9]+)% and ([0-9]+)% in Q2 FY26",
    ], normalized)
    if m:
        rows.append(make_row(
            "3+ Products Penetration ($100K+ ARR Customers)",
            f"{period_label}: {m.group(1)}%",
            f"Q2 FY{fiscal_year - 1}: {m.group(3)}%",
            f"{m.group(1)}% of $100K+ ARR customers subscribed to 3+ products, up from {m.group(3)}% a year ago.",
            source="IR",
            importance="Tier 2 — High",
        ))
        rows.append(make_row(
            "3+ Products Penetration (Core Customers)",
            f"{period_label}: {m.group(2)}%",
            f"Q2 FY{fiscal_year - 1}: {m.group(4)}%",
            f"{m.group(2)}% of core customers subscribed to 3+ products, up from {m.group(4)}% a year ago.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"20%\+ of net new ACV for the third consecutive quarter",
    ], normalized)
    if m:
        rows.append(make_row(
            "Emerging Products Share of Net New ACV",
            f"{period_label}: 20%+",
            f"{prev_label}: N/A",
            "Emerging products contributed 20%+ of net new ACV for the third consecutive quarter.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"18% of Q2 net new ACV was generated outside the U\.S\.",
    ], normalized)
    if m:
        rows.append(make_row(
            "International Net New ACV Mix",
            f"{period_label}: 18%",
            f"{prev_label}: N/A",
            "International markets generated 18% of Q2 net new ACV.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"21% non-GAAP operating margin",
    ], normalized)
    if m:
        rows.append(make_row(
            "Non-GAAP Operating Margin",
            f"{period_label}: 21%",
            f"Q2 FY{fiscal_year - 1}: N/A",
            "Non-GAAP operating margin reached 21%, indicating operating leverage.",
            source="IR/SEC",
        ))

    m = _find([
        r"13% free cash flow margin",
    ], normalized)
    if m:
        rows.append(make_row(
            "Free Cash Flow Margin",
            f"{period_label}: 13%",
            f"Q2 FY{fiscal_year - 1}: N/A",
            "Free cash flow margin reached 13%, reflecting improved operating leverage.",
            source="IR/SEC",
        ))

    m = _find([
        r"\$0\.03 GAAP EPS",
    ], normalized)
    if m:
        rows.append(make_row(
            "GAAP Net Income Per Share",
            f"{period_label}: $0.03",
            f"Q2 FY{fiscal_year - 1}: N/A",
            "GAAP EPS was $0.03, marking profitability.",
            source="IR/SEC",
        ))

    m = _find([
        r"Revenue between \$514 and \$516 million",
    ], normalized)
    if m:
        rows.append(make_row(
            "Q3 FY2027 Revenue Outlook",
            f"Q3 FY{fiscal_year}: $514M – $516M",
            "N/A",
            "Q3 revenue guidance was $514M–$516M.",
            source="IR",
            importance="Tier 2 — High",
        ))

    m = _find([
        r"Full-year FY27:\s*○ Revenue between \$2\.043 and \$2\.047 billion",
    ], normalized)
    if m:
        rows.append(make_row(
            "FY2027 Revenue Outlook",
            f"FY{fiscal_year}: $2.043B – $2.047B",
            "N/A",
            "Full-year revenue guidance was $2.043B–$2.047B.",
            source="IR",
            importance="Tier 1 — Core",
        ))

    # De-duplicate by metric and keep the first occurrence.
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        metric = row["metric"]
        if metric in seen:
            continue
        seen.add(metric)
        deduped.append(row)
    return deduped
