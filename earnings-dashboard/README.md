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

All company values, labels, explanations, formulas, scales, evidence, and sources come from generated data. Presentation files contain no company-specific branches or fixed report values.

## Generate with the earnings pipeline

`run_analysis.py` now creates an interactive dashboard alongside JSON, Markdown, and PDF outputs. A successful run adds:

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
```

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
