#!/usr/bin/env python3
"""Minimal module for test compatibility - functions moved to render_interactive_dashboard_pdf.py"""
from __future__ import annotations

# Import from the new location
from render_interactive_dashboard_pdf import (
    _compact_summary,
    _compact_items,
    _direction_marker,
    _select_call_summary_insights,
    COMPACT_LABELS,
    SEMANTIC_SYMBOL_COLORS,
    COLORS,
    validate_pdf,
)

# Make them available at module level
__all__ = [
    '_compact_summary',
    '_compact_items',
    '_direction_marker',
    '_select_call_summary_insights',
    'COMPACT_LABELS',
    'SEMANTIC_SYMBOL_COLORS',
    'COLORS',
    'validate_pdf',
]