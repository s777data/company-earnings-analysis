# Source-Derived Business KPI Protocol

## Purpose

Business KPIs are derived from each company's current official evidence. Runtime source code must not contain industry catalogues, ticker branches, or company-specific metric definitions.

The official dashboard registry is `references/KPI_derived_reference.txt`.

## Required sources for every company and quarter

1. **IR:** Inspect the company's official investor-relations page and all quarter-matched materials, including the earnings release, shareholder/investor letter, results snapshot, earnings presentation, and supplemental operating schedules when available.
2. **SEC:** Inspect the matching SEC 10-Q and the quarter-matched 8-K Item 2.02 earnings exhibit.
3. Identify business-model-specific operating measures as an expert financial analyst. Ordinary consolidated income-statement, valuation, liquidity, cash-flow, and stock-compensation rows already displayed elsewhere must not be duplicated merely to fill space.
4. Start from SEC evidence, then reconcile against IR evidence and identify IR-only or SEC-only gaps. Never infer an undisclosed value.

## Derivation output

First produce the complete research table:

```text
metric|latest quarter value (for example, Q2 2026)|last year quarter value (for example, Q2 2025)|Analyst view|source|importance
```

Allowed source values are exactly `IR`, `SEC`, and `IR/SEC`.

Importance uses this hierarchy:

- `Tier 1 — Core`: demand, capacity/utilization, business mix, unit economics, installed-base or recurring-revenue drivers, and segment profitability central to the business model.
- `Tier 2 — High`: product, customer, channel, service, operational-efficiency, market-share, and forward demand indicators that explain Tier 1 outcomes.
- `Tier 3 — Supporting`: useful diagnostics with narrower explanatory value or without a comparable prior period.
- `Tier 4 — Context`: verified context that is decision-useful but not a primary operating driver.

Analyst views must interpret the verified current/prior observations and identify direction, business significance, and any forward-looking limitation. They must not invent causes, probabilities, or values.

## Official registry contract

`references/KPI_derived_reference.txt` uses this exact pipe-delimited header:

```text
COMPANY|TICKER|SECTOR|metric|latest quarter value( eg,Q2 2026)|last year quarter value ( eg,Q2 2025)|Analyst_view|source|importance|date_added
```

Each value cell includes its period, for example `Q2 2026: 67%` and `Q2 2025: 66%`. Undisclosed comparisons use the expected prior period plus `N/A`.

Every row is deduplicated by normalized `COMPANY|TICKER|SECTOR|metric`. A new quarter updates the existing metric observation rather than creating a duplicate. `date_added` preserves the original addition date. New source-backed metrics may be added in future runs.

Use `upsert_derived_kpis()` in `scripts/kpi_metrics.py` to update the registry atomically. The reader rejects malformed headers, unsupported source labels, malformed rows, and duplicate identities.

## Dashboard selection

The dashboard and Telegram message display the top **12** current-period metrics by importance. Tier 1 rows rank before Tier 2, Tier 3, and Tier 4. Current-quarter rows from an older fiscal period are not reused.

If the registry lacks current-period rows for the requested ticker, the result is `DERIVED_REFERENCE_REQUIRED` or `INCOMPLETE`; the skill must complete the IR/SEC derivation before publication. It must never fall back to an industry catalogue or claim that source data is unavailable merely because a ticker-specific catalogue does not exist.
