#!/usr/bin/env python3
"""Fetch SEC filing documents using the authoritative filing index JSON."""
from __future__ import annotations

import io
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SEC_BASE = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT", "Hermes earnings research contact@example.com"),
           "Accept-Encoding": "gzip, deflate"}


def _get(url: str) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response


def extract_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    # Preserve tables because financial statements and guidance commonly live there.
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def _document_text(url: str, name: str) -> str:
    response = _get(url)
    lower = name.lower()
    if lower.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    if lower.endswith(".xml"):
        return response.text
    return extract_html_text(response.text)


def extract_exhibit_number(filename: str) -> str | None:
    compact = re.sub(r"[^a-z0-9]", "", filename.lower())
    match = re.search(r"(?:exhibit|ex|dex)(\d{2})(\d)", compact)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    match = re.search(r"(?:^|[^0-9])(99)[._-]?([1-9])(?:[^0-9]|$)", filename.lower())
    return f"{match.group(1)}.{match.group(2)}" if match else None


def extract_index_exhibits(index_html: str, root: str) -> dict[str, dict[str, str]]:
    """Read exhibit types from the SEC filing-detail table when filenames omit ``ex99``."""
    soup = BeautifulSoup(index_html, "html.parser")
    exhibits: dict[str, dict[str, str]] = {}
    for row in soup.select("table.tableFile tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        exhibit_type = cells[3].get_text(" ", strip=True)
        match = re.fullmatch(r"EX-(\d{2})\.(\d+)", exhibit_type, re.I)
        number = f"{match.group(1)}.{match.group(2)}" if match else None
        link = row.find("a", href=True)
        if not number or link is None:
            continue
        url = urljoin(f"{root}/", str(link.get("href", "")))
        exhibits[number] = {"name": urlparse(url).path.rsplit("/", 1)[-1], "url": url}
    return exhibits


def _select_instance(files: list[dict[str, Any]]) -> str | None:
    candidates = [f["name"] for f in files if f.get("name", "").lower().endswith(".xml")]
    preferred = [name for name in candidates if name.lower().endswith("_htm.xml")]
    if preferred:
        return preferred[0]
    excluded = ("filingsummary", "metalinks", "_cal", "_def", "_lab", "_pre")
    return next((name for name in candidates if not any(term in name.lower() for term in excluded)), None)


def fetch_filing(accession_number: str, cik: str, primary_document: str | None = None,
                 include_exhibits: bool = False, exhibit_filter: str | None = None) -> dict[str, Any]:
    if not cik:
        raise ValueError("CIK is required")
    accession = accession_number.replace("-", "")
    root = f"{SEC_BASE}/{int(cik)}/{accession}"
    index = _get(f"{root}/index.json").json()
    files = index.get("directory", {}).get("item", [])
    names = {item.get("name") for item in files}
    main = primary_document if primary_document in names else None
    if not main:
        main = next((name for name in names if name and name.lower().endswith((".htm", ".html"))
                     and not any(x in name.lower() for x in ("index", "header", "exhibit", "ex99", "dex99"))), None)
    if not main:
        raise RuntimeError("SEC primary document could not be identified")
    instance = _select_instance(files)
    exhibits: dict[str, dict[str, str]] = {}
    for item in files:
        name = item.get("name", "")
        number = extract_exhibit_number(name)
        if not number or (exhibit_filter and number != exhibit_filter):
            continue
        exhibits[number] = {"name": name, "url": f"{root}/{name}"}
    if include_exhibits or exhibit_filter:
        detail_name = f"{accession_number}-index.html"
        try:
            indexed_exhibits = extract_index_exhibits(_get(f"{root}/{detail_name}").text, root)
            for number, meta in indexed_exhibits.items():
                if not exhibit_filter or number == exhibit_filter:
                    exhibits[number] = meta
        except requests.RequestException:
            # Filename detection above remains a valid fallback when the detail page is unavailable.
            pass
    result: dict[str, Any] = {
        "accession_number": accession, "cik": str(cik).zfill(10), "main_document": main,
        "filing_url": f"{root}/{main}", "content": _document_text(f"{root}/{main}", main),
        "xbrl_document": instance, "xbrl_url": f"{root}/{instance}" if instance else None,
        "xbrl_content": _document_text(f"{root}/{instance}", instance) if instance else None,
        "exhibits": exhibits, "exhibit_content": {},
    }
    if include_exhibits or exhibit_filter:
        for number, meta in exhibits.items():
            result["exhibit_content"][number] = _document_text(meta["url"], meta["name"])
    return result
