# Business KPI Metrics Reference

## Provenance and scope

This reference is derived only from the supplied **KPIs research.pdf** and defines the new company-specific operating-KPI section. It does not import metrics from the financial-dashboard or valuation reference files. Generic income-statement, valuation, cash-flow, and stock-compensation metrics remain in their existing dashboard sections and should not be duplicated as business KPIs.

The supplied research uses a restaurant business to demonstrate the selection process. The implemented catalogue is therefore activated only when verified source text contains strong restaurant context. Unsupported industries must return an explicit no-applicable-catalogue status rather than fabricate company-specific KPIs.

## Evidence policy

Allowed source labels are exactly:

- `IR` — a company investor-relations earnings release or supplemental operating report.
- `SEC` — a company filing or structured fact from SEC.gov.
- `IR/SEC` — the metric is present in both the company-prepared earnings release and SEC filing evidence.

Every value must preserve a citation URL and source excerpt. Missing values are displayed as `N/A`; they are never inferred. Analyst views must be generated from the reported current/prior values and the metric directionality, not from unsupported claims.

## Required row schema

```text
metric | latest quarter value | last-year quarter value | analyst view | source | importance
```

Machine-readable rows also carry `key`, `latest_period`, `prior_period`, `tier`, `signal`, `impact`, `directionality`, `citation`, and `available`.

## Selection policy

1. Research the company's business model and management-defined operating measures from the verified IR release and SEC filing.
2. Separate company-specific operating KPIs from ordinary financial statement, valuation, liquidity, and SBC metrics already shown elsewhere.
3. Assign importance based on decision usefulness:
   - **Tier 1 — Core:** demand, unit productivity, core unit economics, expansion engine, and operating scale.
   - **Tier 2 — High:** operating drivers, mix, capacity, and cost inputs that explain Tier 1 movement.
   - **Tier 3 — Supporting:** useful diagnostics with more overlap or narrower explanatory value.
   - **Tier 4 — Context:** include only when selected by source-backed research and space permits.
4. Retain every applicable Tier 1 metric.
5. Display all lower-tier rows in descending importance after Tier 1.
6. Display all **16** KPI cards. If a metric is not disclosed, keep the importance-ordered card visible with `N/A` rather than silently dropping or reordering it.
7. Preserve exactly the source labels `IR`, `SEC`, or `IR/SEC`.

## Restaurant KPI catalogue derived from the supplied research

### Tier 1 — Core

| Metric | Why it matters | Directionality |
|---|---|---|
| Same Restaurant Sales Growth | Existing-store demand independent of new openings | Higher is generally better |
| Guest Traffic Growth | Demand quality; separates traffic from pricing | Higher is generally better |
| Average Unit Volume (AUV) | Mature-location sales productivity | Higher is generally better |
| Restaurant-Level Profit Margin | Core unit economics | Higher and expanding is better |
| Net New Restaurant Openings | Physical expansion engine | Higher is favorable when unit economics remain healthy |
| Total Restaurant Count | Operating scale and footprint | Higher is favorable when productivity remains healthy |
| Restaurant Revenue | Connects store growth and comparable sales to scale | Higher profitable growth is better |

### Tier 2 — High

| Metric | Why it matters | Directionality |
|---|---|---|
| Menu Price + Product Mix | Explains the non-traffic component of comparable sales | Context-dependent |
| Digital Revenue Mix | Channel adoption and delivery/margin mix | Context-dependent |
| Food, Beverage & Packaging % of Revenue | Largest restaurant input-cost bucket | Lower is generally better |
| Labor % of Revenue | Labor efficiency and wage pressure | Lower is generally better |
| Restaurant Footprint Growth | Normalizes expansion relative to existing scale | Higher is favorable with healthy unit economics |
| Restaurant Operating Weeks | Capacity actually available during the period | Higher indicates more capacity; assess productivity too |
| Restaurant-Level Profit | Restaurant profitability dollars | Higher is generally better |

### Tier 3 — Supporting

| Metric | Why it matters | Directionality |
|---|---|---|
| Occupancy % of Revenue | Fixed-cost operating leverage | Lower is generally better |
| Other Restaurant Operating Expenses % | Delivery and other controllable operating costs | Lower is generally better |

## Presentation contract

- Place **KPI** immediately below **Income Statement Highlights** in both Telegram and the HTML dashboard.
- Use 16 readable cards in two rows of eight across the same available dashboard width as Income Statement Highlights.
- Each card presents metric name, source/importance, current-quarter value, prior-year-quarter value, and a short analyst view.
- Use the existing dashboard's seven-state signal color spectrum.
- Keep the report within one A4 portrait page. Each KPI row uses the same card height as Income Statement Highlights; Key Ratios uses half-height wrapping cards; Key Risks and Investment Thesis use compact 12 mm two-column wrapped lists; and Grade Reasoning uses a half-height 10 mm wrapped grid that displays all rows without overlap. Key Channels & Segments and Strategic Pillars retain their previously validated half-height cards.
