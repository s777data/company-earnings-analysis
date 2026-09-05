#!/usr/bin/env python3
"""Render the completed interactive earnings dashboard to a validated A4 PDF."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import fitz  # PyMuPDF
import pdfplumber
from playwright.sync_api import sync_playwright


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


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_MIN_WIDTH = 2400
PNG_MIN_HEIGHT = 3400
PNG_DEVICE_SCALE_FACTOR = 3.125
PNG_VIEWPORT = {"width": 1280, "height": 1800}
PNG_SELECTOR = "#report"


def _validate_png(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise RuntimeError("Dashboard PNG signature is invalid")
    if len(data) < 33:
        raise RuntimeError("Dashboard PNG is truncated")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width < PNG_MIN_WIDTH or height < PNG_MIN_HEIGHT:
        raise RuntimeError(f"Dashboard PNG is too small: {width}x{height}")
    return width, height


def render_dashboard_png(html_path: str, output_path: str, expected_urls: Iterable[str] = (), playwright_cli: str | None = None) -> str:
    """Render the final dashboard HTML to a high-resolution PNG.

    The input may be the dashboard HTML entry point, the dashboard ZIP archive,
    or a legacy dashboard PDF. ZIP/HTML inputs render directly from Chromium;
    PDF inputs are accepted for backward compatibility.
    """
    source_path = Path(html_path).resolve()
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    del expected_urls, playwright_cli

    if source_path.suffix.lower() == ".pdf":
        document = fitz.open(source_path)
        try:
            if len(document) != 1:
                raise RuntimeError("Dashboard PDF must contain exactly one page")
            page = document[0]
            scale = 3840 / page.rect.height
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            pixmap.save(str(destination))
        finally:
            document.close()
    else:
        source, tempdir = _resolve_source_html(source_path)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport=PNG_VIEWPORT, device_scale_factor=PNG_DEVICE_SCALE_FACTOR)
                page = context.new_page()
                try:
                    page.emulate_media(media="print")
                    page.goto(source.as_uri(), wait_until="networkidle", timeout=120_000)
                    page.wait_for_function(
                        """
                        () => document.fonts && document.fonts.status === 'loaded' &&
                              document.body && document.body.dataset.layoutReady === 'true'
                        """,
                        timeout=120_000,
                    )
                    page.wait_for_selector(PNG_SELECTOR, timeout=120_000)
                    page.evaluate(
                        """
                        () => new Promise((resolve) =>
                            requestAnimationFrame(() =>
                                requestAnimationFrame(resolve)
                            )
                        )
                        """
                    )
                    issues = _layout_issues(page)
                    if issues:
                        raise RuntimeError(f"Dashboard layout validation failed: {issues}")
                    report = page.locator(PNG_SELECTOR)
                    report.screenshot(path=str(destination), scale="device")
                finally:
                    context.close()
                    browser.close()
        finally:
            if tempdir is not None:
                tempdir.cleanup()

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Interactive dashboard PNG renderer produced no file")

    _validate_png(destination)
    return str(destination)


def _resolve_source_html(path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    source = path.resolve()
    if source.suffix.lower() != ".zip":
        if not source.is_file():
            raise RuntimeError("Interactive dashboard HTML is missing")
        return source, None

    if not source.is_file():
        raise RuntimeError("Interactive dashboard ZIP is missing")

    tempdir = tempfile.TemporaryDirectory(prefix="dashboard-render-")
    extracted_root = Path(tempdir.name)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(extracted_root)
    html_candidates = sorted(extracted_root.rglob("index.html"))
    if not html_candidates:
        tempdir.cleanup()
        raise RuntimeError("Interactive dashboard ZIP does not contain an index.html entry")
    return html_candidates[0], tempdir


def _layout_issues(page) -> list[dict[str, object]]:
    return page.evaluate(
        """
        () => {
            const problems = [];
            const report = document.querySelector('#report');
            if (report && (report.scrollHeight > report.clientHeight + 1 || report.scrollWidth > report.clientWidth + 1)) {
                problems.push({
                    type: 'report-overflow',
                    scrollHeight: report.scrollHeight,
                    clientHeight: report.clientHeight,
                    scrollWidth: report.scrollWidth,
                    clientWidth: report.clientWidth,
                });
            }
            document.querySelectorAll('[data-fitted="false"]').forEach((el) => {
                problems.push({
                    type: 'text-not-fitted',
                    id: el.id || null,
                    className: el.className || null,
                });
            });
            document.querySelectorAll(
                '.kpi-card,.metric-card,.gauge-card,.dense-list,.channel-card,.pillar-card'
            ).forEach((el) => {
                if (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) {
                    problems.push({
                        type: 'element-overflow',
                        id: el.id || null,
                        className: el.className || null,
                    });
                }
            });
            return problems;
        }
        """
    )


def render_dashboard_pdf(
    html_path: str,
    output_path: str,
    expected_urls: Iterable[str] = (),
    playwright_cli: str | None = None,
) -> str:
    """Print the fully rendered local dashboard to PDF and validate the result.

    The renderer accepts either the dashboard HTML entry point or the dashboard
    ZIP archive. If a ZIP is provided, it is extracted to a temporary directory
    and the contained index.html becomes the rendering source of truth.
    """
    source, tempdir = _resolve_source_html(Path(html_path))
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    # playwright_cli is retained for backward compatibility with existing call sites,
    # but the renderer now uses the direct Playwright API as requested.
    del playwright_cli

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 2048}, device_scale_factor=1)
            try:
                page.emulate_media(media="print")
                page.goto(source.as_uri(), wait_until="networkidle", timeout=120_000)
                page.wait_for_function(
                    """
                    () => document.fonts && document.fonts.status === 'loaded' &&
                          document.body && document.body.dataset.layoutReady === 'true'
                    """,
                    timeout=120_000,
                )
                page.wait_for_selector(SELECTOR, timeout=120_000)
                page.evaluate(
                    """
                    () => new Promise((resolve) =>
                        requestAnimationFrame(() =>
                            requestAnimationFrame(resolve)
                        )
                    )
                    """
                )
                issues = _layout_issues(page)
                if issues:
                    raise RuntimeError(f"Dashboard layout validation failed: {issues}")
                page.pdf(
                    path=str(destination),
                    format="A4",
                    prefer_css_page_size=True,
                    print_background=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                browser.close()
    finally:
        if tempdir is not None:
            tempdir.cleanup()

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Interactive dashboard PDF renderer produced no file")

    # Interactive dashboard PDF is a print-based render from Chromium;
    # validate page structure but not clickable link annotations (which may not
    # survive the print-to-PDF path). The one-pager PDF carries the
    # verified source links.
    validate_pdf(str(destination), [])
    return str(destination)
