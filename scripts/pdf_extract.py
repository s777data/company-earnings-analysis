#!/usr/bin/env python3
"""
PDF Extract Tool
Extracts text and tables from PDF documents.
"""

import json
import sys
import os
import io
import re
from typing import Dict, List, Optional, Union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

HEADERS = {
    "User-Agent": "Hermes Company Earnings Analysis (contact: sandy6123@gmail.com)"
}

def extract_pdf(
    source: Union[str, bytes],
    pages: Union[str, List[int]] = "all",
    extract_tables: bool = False
) -> Dict:
    """
    Extract text and optionally tables from PDF.
    
    Args:
        source: URL, file path, or bytes
        pages: "all" or list of page numbers (1-indexed)
        extract_tables: Whether to extract tables
    
    Returns:
        Dict with text, tables, metadata
    """
    # Load PDF
    pdf_bytes = load_pdf(source)
    if not pdf_bytes:
        return {"error": "Failed to load PDF"}
    
    result = {
        "text": "",
        "pages": [],
        "tables": [],
        "metadata": {},
        "page_count": 0
    }
    
    # Try pdfplumber first (better for tables)
    if PDFPLUMBER_AVAILABLE:
        result = extract_with_pdfplumber(pdf_bytes, pages, extract_tables)
    
    # Fallback to PyMuPDF
    if not result["text"] and PYMUPDF_AVAILABLE:
        result = extract_with_pymupdf(pdf_bytes, pages)
    
    if not result["text"]:
        result["error"] = "No PDF extraction library available (pdfplumber or PyMuPDF)"
    
    return result

def load_pdf(source: Union[str, bytes]) -> Optional[bytes]:
    """Load PDF from URL, file path, or bytes."""
    if isinstance(source, bytes):
        return source
    
    if isinstance(source, str):
        if source.startswith("http://") or source.startswith("https://"):
            if not REQUESTS_AVAILABLE:
                return None
            try:
                resp = requests.get(source, headers=HEADERS, timeout=30)
                if resp.status_code == 200:
                    return resp.content
            except Exception:
                return None
        else:
            # File path
            try:
                with open(source, "rb") as f:
                    return f.read()
            except Exception:
                return None
    
    return None

def extract_with_pdfplumber(pdf_bytes: bytes, pages: Union[str, List[int]], extract_tables: bool) -> Dict:
    """Extract using pdfplumber."""
    result = {"text": "", "pages": [], "tables": [], "metadata": {}, "page_count": 0}
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result["metadata"] = pdf.metadata or {}
            result["page_count"] = len(pdf.pages)
            
            page_indices = get_page_indices(pages, len(pdf.pages))
            
            for idx in page_indices:
                page = pdf.pages[idx]
                page_num = idx + 1
                
                # Extract text
                text = page.extract_text()
                if text:
                    result["pages"].append({
                        "page": page_num,
                        "text": text
                    })
                    result["text"] += f"\n--- PAGE {page_num} ---\n{text}\n"
                
                # Extract tables
                if extract_tables:
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table:
                            result["tables"].append({
                                "page": page_num,
                                "table_index": table_idx,
                                "data": table
                            })
        
        return result
    except Exception as e:
        return {"error": f"pdfplumber extraction failed: {e}", "text": "", "pages": [], "tables": []}

def extract_with_pymupdf(pdf_bytes: bytes, pages: Union[str, List[int]]) -> Dict:
    """Extract using PyMuPDF (fitz)."""
    result = {"text": "", "pages": [], "tables": [], "metadata": {}, "page_count": 0}
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result["metadata"] = doc.metadata or {}
        result["page_count"] = doc.page_count
        
        page_indices = get_page_indices(pages, doc.page_count)
        
        for idx in page_indices:
            page = doc[idx]
            page_num = idx + 1
            
            text = page.get_text()
            if text:
                result["pages"].append({
                    "page": page_num,
                    "text": text
                })
                result["text"] += f"\n--- PAGE {page_num} ---\n{text}\n"
        
        doc.close()
        return result
    except Exception as e:
        return {"error": f"PyMuPDF extraction failed: {e}", "text": "", "pages": []}

def get_page_indices(pages: Union[str, List[int]], total_pages: int) -> List[int]:
    """Convert page specification to 0-indexed page list."""
    if pages == "all":
        return list(range(total_pages))
    
    if isinstance(pages, list):
        # Convert to 0-indexed, validate
        indices = []
        for p in pages:
            if isinstance(p, int) and 1 <= p <= total_pages:
                indices.append(p - 1)
        return indices
    
    return list(range(total_pages))

def extract_financial_tables(tables: List[Dict]) -> List[Dict]:
    """Identify and extract financial statement tables."""
    financial_tables = []
    
    financial_keywords = [
        "revenue", "income", "earnings", "profit", "loss",
        "balance sheet", "cash flow", "assets", "liabilities",
        "equity", "eps", "per share", "operating", "gross margin"
    ]
    
    for table in tables:
        # Check if table contains financial data
        table_text = " ".join(str(cell) for row in table["data"] for cell in row if cell).lower()
        
        if any(kw in table_text for kw in financial_keywords):
            financial_tables.append({
                "page": table["page"],
                "type": "financial_statement",
                "data": table["data"]
            })
    
    return financial_tables

def clean_text(text: str) -> str:
    """Clean extracted text."""
    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    # Remove page numbers, headers/footers patterns
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return text.strip()

import re

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract text from PDF")
    parser.add_argument("--source", required=True, help="PDF URL, file path, or - for stdin")
    parser.add_argument("--pages", default="all", help="Pages to extract (all or comma-separated)")
    parser.add_argument("--tables", action="store_true", help="Extract tables")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    
    args = parser.parse_args()
    
    # Parse pages
    if args.pages == "all":
        pages = "all"
    else:
        pages = [int(p.strip()) for p in args.pages.split(",")]
    
    # Load source
    if args.source == "-":
        source = sys.stdin.buffer.read()
    else:
        source = args.source
    
    result = extract_pdf(source, pages=pages, extract_tables=args.tables)
    
    if args.output == "text":
        print(result.get("text", ""))
        if result.get("tables"):
            print("\n--- TABLES ---")
            for t in result["tables"]:
                print(f"\nPage {t['page']}, Table {t['table_index']}:")
                for row in t["data"]:
                    print(" | ".join(str(c) for c in row))
    else:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()