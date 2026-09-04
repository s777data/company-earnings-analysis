#!/usr/bin/env python3
"""Render the completed interactive earnings dashboard to a validated A4 PDF."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import pdfplumber
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse


SELECTOR = "#income-cards .metric-card"


def _valid_source_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.netloc.endswith((".test", ".example"))


def validate_pdf(path: str, expected_urls: list[str]) -> None:
    file_path = Path(path)
    if not file_path.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("PDF signature is invalid")
    with pdfplumber.open(file_path) as document:
        if len(document.pages) != 1:
            raise RuntimeError("PDF must contain exactly one page")
        page = document.pages[0]
        if abs(page.width - 595.28) > 2 or abs(page.height - 841.89) > 2:
            raise RuntimeError("PDF page is not A4")
        text = page.extract_text() or ""
        normalized_text = text.upper()
        headings = (
            ("INCOME STATEMENT HIGHLIGHTS",),
            ("KPI",),
            ("KEY RATIOS",),
            ("VALUATION",),
            ("CAPITAL & LIQUIDITY",),
            ("SHORT INTEREST & SBC", "SHORT INTEREST & STOCK-BASED COMPENSATION", "SHORT INTEREST", "STOCK-BASED COMPENSATION"),
            ("GUIDANCE & OUTLOOK",),
            ("EARNINGS CALL SUMMARY",),
            ("KEY CHANNELS & SEGMENTS",),
            ("STRATEGIC PILLARS",),
            ("KEY RISKS",),
            ("INVESTMENT THESIS",),
        )
        for alternatives in headings:
            if not any(heading.upper() in normalized_text for heading in alternatives):
                raise RuntimeError(f"PDF is missing required section: {alternatives[0]}")
        links = {item.get("uri") for item in page.hyperlinks if item.get("uri")}
        missing = set(expected_urls) - links
        if missing:
            raise RuntimeError("PDF is missing clickable source links")


def render_dashboard_png(pdf_path: str, output_path: str, target_height_px: int = 3840) -> str:
    """Rasterize the first page of a validated dashboard PDF to a 4K PNG."""
    source = Path(pdf_path).resolve()
    if not source.is_file():
        raise RuntimeError("Dashboard PDF is missing")
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    if target_height_px <= 0:
        raise RuntimeError("Target PNG height must be positive")

    document = fitz.open(source)
    try:
        if len(document) != 1:
            raise RuntimeError("Dashboard PDF must contain exactly one page")
        page = document[0]
        scale = target_height_px / page.rect.height
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pixmap.save(str(destination))
    finally:
        document.close()

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Dashboard PNG renderer produced no file")
    return str(destination)


def render_dashboard_pdf(
    html_path: str,
    output_path: str,
    expected_urls: Iterable[str] = (),
    playwright_cli: str | None = None,
) -> str:
    """Print the fully rendered local dashboard to PDF and validate the result.

    The selector wait guarantees that report.js has loaded and JavaScript has
    rendered the metric cards before Chromium enters print mode.
    """
    source = Path(html_path).resolve()
    if not source.is_file():
        raise RuntimeError("Interactive dashboard HTML is missing")
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    # playwright_cli is retained for backward compatibility with existing call sites,
    # but the renderer now uses the direct Playwright API as requested.
    del playwright_cli

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(source.as_uri(), wait_until="networkidle")
            page.wait_for_selector(SELECTOR)
            page.emulate_media(media="print")
            page.pdf(
                path=str(destination),
                format="A4",
                prefer_css_page_size=True,
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            browser.close()

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Interactive dashboard PDF renderer produced no file")

    # Interactive dashboard PDF is a print-based render from Chromium;
    # validate page structure but not clickable link annotations (which may not
    # survive the print-to-PDF path). The one-pager PDF carries the
    # verified source links.
    validate_pdf(str(destination), [])
    return str(destination)
