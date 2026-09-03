# Interactive A4 Earnings Dashboard

A production-ready static HTML counterpart to the one-page earnings PDF. It preserves the compact A4 analyst-report hierarchy while adding keyboard-accessible metric explanations and threshold scales.

## Run locally

Open `index.html` directly. The bundled `data/report.js` makes the default report work under `file://` without a web server. You can also select another dashboard-schema JSON file with **Load report JSON**.

For normal HTTP behavior:

```bash
python3 -m http.server 8000 --directory earnings-dashboard
```

Then open `http://localhost:8000`.

## Architecture

- `index.html` — semantic, company-neutral report shell and accessible metric dialog.
- `css/dashboard.css` — bundled Inter font, A4 screen layout, dense reusable cards, responsive overflow, and interaction states.
- `css/print.css` — strict A4 portrait output with controls, overlays, and screen effects removed.
- `js/dashboard.js` — reusable renderers for metrics, evidence sections, modal behavior, print control, and local JSON selection.
- `data/RKLB-2026-Q2.json` — reference report generated from the existing analysis pipeline.
- `data/report.json` / `data/report.js` — active default report. The JavaScript wrapper exists only so direct local opening works without browser `file://` fetch restrictions.
- `scripts/create_interactive_dashboard.py` — converts the company-neutral earnings-analysis JSON into the interactive schema and generates a complete static site.
- `scripts/render_interactive_dashboard_pdf.py` — waits for the final JavaScript-rendered cards, prints the page through headless Chromium, and validates the resulting one-page A4 PDF before delivery.

All company values, labels, explanations, formulas, scales, evidence, and sources come from generated data. Presentation files contain no company-specific branches or fixed report values.

## Scorecard presentation

- **Income Statement Highlights:** four core cards in the stable sequence Revenue, Gross Profit, Operating Income, and Net Income. Each card uses a centered label, prominent value, and directional YoY badge.
- **Key Ratios:** six generated margin/growth cards in one row. Each uses a centered label and value, dashed context divider, period label, and signal-colored bottom rule.
- **Valuation:** compact semicircular gauges populated from `../references/VALUATION_METRICS_REFERENCE_MAIN_METRICS_REVIEW.txt`. The renderer emits all applicable main metrics, then unique regime-specific metrics; profitable-company metrics retain Tier 1→2→3 order. The grid uses no more than eight cards per row.
- **Short Interest & Stock-Based Compensation:** a separate gauge-card section for applicable official Nasdaq short-interest observations and SEC XBRL SBC/dilution measures.
- Every card remains a native button with keyboard activation, focus styling, and the full metric-detail dialog.

## Generate with the earnings pipeline

`run_analysis.py` now creates an interactive dashboard, a browser-rendered PDF, and a 4K PNG alongside JSON, Markdown, and the original PDF output. After the final JavaScript cards render, headless Chromium prints the HTML to A4 PDF, validates the PDF, rasterizes that PDF to a 4K PNG, and uses the dashboard ZIP as the attachment for both Telegram messages. A successful run adds:

```text
<TICKER>_Qn_FYyyyy_Interactive_Dashboard/
├── index.html
├── css/
├── js/
├── assets/fonts/
└── data/
    ├── <TICKER>-<YEAR>-<QUARTER>.json
    ├── report.json
    └── report.js
<TICKER>_Qn_FYyyyy_Interactive_Dashboard.pdf
<TICKER>_Qn_FYyyyy_Interactive_Dashboard_4K.png
```

The static dashboard has no runtime dependencies. Pipeline PDF rendering requires the Playwright CLI and Chromium:

```bash
playwright install chromium
```

Set `PLAYWRIGHT_CLI=/absolute/path/to/playwright` when the executable is not on `PATH`.

You can also call the generator directly:

```python
from scripts.create_interactive_dashboard import create_interactive_dashboard
create_interactive_dashboard(analysis_data, "outputs/example-dashboard")
```

## Publish with GitHub Pages

1. In the repository settings, open **Pages**.
2. Select **Deploy from a branch**.
3. Select the branch and `/earnings-dashboard` folder if your Pages workflow supports a custom path, or copy the folder contents to a dedicated Pages branch/root.
4. Save and wait for deployment.

No backend, API keys, build command, tracker, or external CDN is required.

## Interaction and accessibility

- Every Income Statement, Key Ratio, and Valuation card is a native keyboard-focusable button.
- Enter/Space opens the metric dialog.
- Escape closes the dialog through native `<dialog>` behavior.
- Focus returns to the triggering card after close.
- Status is expressed through text, arrows, and color—not color alone.
- Visible focus states and semantic headings support keyboard and assistive-technology navigation.

## Print / Save PDF

Use the button above the report, then select A4 portrait with browser headers/footers disabled. Print CSS sets:

```css
@page { size: A4 portrait; margin: 0; }
```

The report sheet is exactly `210mm × 297mm`; controls, dialogs, shadows, and screen background are excluded from print.

## Verification checklist

- [x] A4 portrait shell with PDF-matched section order
- [x] Dense navy-bar/light-card visual system
- [x] Bundled Inter variable font
- [x] Data-driven reusable cards and text sections
- [x] Income Statement, Key Ratio, and Valuation card interaction
- [x] Definition, relevance, directionality, formula, source, and scales in dialog
- [x] Native keyboard operation, Escape close, and focus restoration
- [x] Mobile horizontal scroll that preserves report geometry
- [x] Dedicated one-page print stylesheet
- [x] Direct local operation and GitHub Pages compatibility
- [x] No external analytics or runtime dependencies

## Tests

From the repository root:

```bash
python3 -m py_compile run_analysis.py scripts/*.py tests/*.py
python3 -m unittest discover -s tests -v
```
