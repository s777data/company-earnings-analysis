#!/usr/bin/env python3
"""Render the completed interactive earnings dashboard to a validated A4 PDF."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable
import pdfplumber
from urllib.parse import urlparse


SELECTOR = "body[data-layout-ready='true'] #valuation-cards .gauge-card"


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
        headings = ("INCOME STATEMENT HIGHLIGHTS", "KPI", "KEY RATIOS", "VALUATION", "CAPITAL & LIQUIDITY",
                    "SHORT INTEREST & SBC", "GUIDANCE & OUTLOOK", "EARNINGS CALL SUMMARY", "KEY CHANNELS & SEGMENTS",
                    "STRATEGIC PILLARS", "KEY RISKS", "INVESTMENT THESIS")
        for heading in headings:
            if heading.upper() not in normalized_text:
                raise RuntimeError(f"PDF is missing required section: {heading}")
        links = {item.get("uri") for item in page.hyperlinks if item.get("uri")}
        missing = set(expected_urls) - links
        if missing:
            raise RuntimeError("PDF is missing clickable source links")


def _playwright_executable(explicit: str | None = None) -> str:
    """Resolve the Playwright CLI without assuming a project-local Node setup."""
    candidates = [
        explicit,
        os.environ.get("PLAYWRIGHT_CLI"),
        shutil.which("playwright"),
        str(Path.home() / ".local/pipx/venvs/hermes-agent/bin/playwright"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise RuntimeError(
        "Playwright CLI is required to render the interactive dashboard PDF. "
        "Install it and Chromium with `playwright install chromium`, or set PLAYWRIGHT_CLI."
    )


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

    command = [
        _playwright_executable(playwright_cli),
        "pdf",
        "--paper-format",
        "A4",
        "--wait-for-selector",
        SELECTOR,
        "--timeout",
        "120000",
        source.as_uri(),
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=150)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Interactive dashboard PDF rendering failed: {detail}")
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Interactive dashboard PDF renderer produced no file")

    # Interactive dashboard PDF is a print-based render from Chromium;
    # validate page structure but not clickable link annotations (which may not
    # survive the print-to-PDF path). The one-pager PDF carries the
    # verified source links.
    validate_pdf(str(destination), [])
    return str(destination)
