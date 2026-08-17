---
name: company-earnings-analysis
version: 2.7
description: Evidence-gated analysis of the latest quarterly SEC filing and mandatory web earnings-call transcript
category: research
model: high-reasoning
---

# Company Earnings Analysis

Produces a source-traceable quarterly earnings analysis, Markdown report, JSON record, validated one-page PDF, reusable interactive A4 HTML dashboard, and optional verified Telegram delivery.

## Non-negotiable publication gates

The run stops rather than substituting plausible values when any of these gates fails:

1. A recent SEC 10-Q is identified.
2. The SEC filing index identifies the primary filing and an XBRL instance document.
3. XBRL supplies `DocumentFiscalPeriodFocus`, `DocumentFiscalYearFocus`, report date, and revenue.
4. A web-sourced transcript for the same fiscal period is verified to contain prepared remarks and analyst Q&A. Any provider-reported call date must fall from the verified report date through 120 days afterward; an inconsistent or invalid date is suppressed as `N/A` with a warning.
5. The configured `robinhood-trading` MCP is available, authenticated, and connected to the account named by `ROBINHOOD_EXPECTED_ACCOUNT`.
6. A usable Robinhood quote is returned. No fixed market-data fallback is permitted.
7. Financial rows retain numeric values, periods, concepts, contexts, and source URLs.
8. Growth drivers, grade, confidence, and five-year thesis are computed before publication.
9. The PDF remains within one A4 page, passes post-generation page-size, heading, signature, and clickable-source-link validation, and contains SEC and transcript source URLs.
10. Telegram success requires a zero-exit `hermes send --json` response and a verified nonempty PDF attachment.

## Sources

- Financial statements: SEC 10-Q XBRL instance document.
- Earnings release: quarter-matched SEC 8-K Item 2.02 and its exhibits when available.
- Company-specific operating KPIs: the company-prepared earnings-release exhibit plus the matching SEC 10-Q, using `references/BUSINESS_KPI_METRICS_REFERENCE.md`. Source labels are restricted to `IR`, `SEC`, and `IR/SEC`; values without source evidence remain `N/A`.
- Earnings call: web transcript only. SEC exhibits are not accepted as a substitute.
- Quote and broker fundamentals: `robinhood-trading` MCP only. When a test explicitly requests market data at close, prefer the newest completed daily regular-session candle, but if the daily series lags a newer broker-stamped regular-session last trade, use that newer regular-session trade and preserve its exact venue timestamp. Never substitute extended-hours pricing.
- Short interest and days to cover: the official Nasdaq short-interest report. This source is settlement-date data, not a live quote. Calculate Short Interest % of Float only when a separately verified public-float denominator is available; never substitute shares outstanding for public float.
- Stock-based compensation, diluted shares, backlog, equity, cash, debt, revenue, gross profit, operating income, and cash flow: SEC filing/XBRL facts with period and concept citations.

Supported transcript hosts include StockAnalysis, Seeking Alpha, Motley Fool, MarketBeat, StreetInsider, and Investing.com. The accepted transcript URL is retained in every output.

## Fiscal-period policy

Never infer a fiscal quarter from the filing month. The report uses SEC XBRL `DocumentFiscalPeriodFocus`, `DocumentFiscalYearFocus`, and the SEC report date. The current implementation analyzes quarterly 10-Q periods Q1 through Q3. Annual Q4 analysis requires a separate 10-K workflow and is intentionally rejected.

## XBRL policy

- Prefer consolidated contexts without explicit or typed dimensions.
- Recognize both `RevenueFromContractWithCustomerExcludingAssessedTax` and `RevenueFromContractWithCustomerIncludingAssessedTax` as standard revenue concepts; retain the exact selected concept in citations.
- Income-statement metrics prefer a roughly three-month context ending on the report date.
- Balance-sheet metrics use an instant context ending on the report date.
- Retain the selected concept, context, start date, end date, duration, and unit.
- Select prior-year comparisons only when the duration is comparable and the period end is approximately one year earlier.
- Annualized revenue and free cash flow are explicitly labeled annualized; they are not mislabeled TTM.
- Extract `RevenueRemainingPerformanceObligation` for backlog and `AllocatedShareBasedCompensationExpense`/`ShareBasedCompensation` for SBC only from matching consolidated periods.
- A zero or negative earnings-based P/E is displayed as `N/M` (`Not meaningful`), never as cheap or attractive.
- Valuation cards follow `references/VALUATION_METRICS_REFERENCE_MAIN_METRICS_REVIEW.txt`: all applicable main metrics first, then unique profitability metrics in Tier 1→2→3 order when earnings and FCF are positive, or unique negative-regime metrics otherwise. Omit unsupported or economically meaningless denominator-based metrics rather than forcing an `N/A` multiple.

## Analysis policy

The analysis is deterministic and evidence-gated:

- Financial signals use verified year-over-year comparisons. A declining diluted weighted-average share count is classified as anti-dilutive/positive, but is described as a buyback only when separate capital-allocation evidence confirms repurchases.
- Transcript insights retain exact character offsets, verbatim evidence, and the transcript URL in structured output. Transcript validation recognizes provider-neutral prepared-section labels such as `prepared remarks`, `opening remarks`, `initial remarks`, and `business update`, while still requiring substantive prepared remarks and analyst Q&A. Detect analyst Q&A boundaries from normalized transcript lines and provider-neutral operator transitions (for example, explicit Q&A headings and “first question comes from” handoffs), not a single heading regular expression. Track speaker roles from transcript title lines and admit Q&A evidence only from management responses; exclude analyst prompts even when they are declarative fragments without a question mark. The PDF renders a true compression of every displayed item in Guidance & Outlook, Earnings Call Summary, Key Channels & Segments, and Strategic Pillars: each displayed summary must be shorter than its source sentence while retaining quantified values, direction, comparison baseline, named segments, and material qualifiers. Unchanged source prose is not displayed. No summary is clipped or ended with ellipses. Use semantically unambiguous, embedded-font-supported symbols to replace redundant labels or wording (for example, `⚙ Product`, `♻ Capital`, `⚡ Power & Energy`, and `◆ Q&A`); never replace a material company, segment, metric, timing, comparison, or risk qualifier with an ambiguous icon. Apply one seven-level sentiment color to the complete font treatment of every data row in every PDF section: marker, semantic symbol, label, value, comparison, and narrative text must all use `_signal(item) -> COLORS[signal]`. The display spectrum is blue-led for favorable signals (`best` darkest blue, `strong_positive` deep blue, `positive` dark blue), then yellow `neutral`, orange `caution`, red `negative`, and dark red `worst`; never render a positive signal in green. Telegram mirrors this with `🟦`, `🔷`, `🔵`, `🟡`, `🟠`, `🔴`, `🟥`. Do not independently recolor topic symbols by their semantic category. In the PDF Earnings Call Summary, preserve `Management Tone` as the visible label rather than renaming it to `Outlook`. When a channel lacks an explicit signal, derive it from verified directional wording before rendering. Direction markers use the row signal color: favorable `↑`, neutral `→`, and adverse `↓`; a compact statement containing both explicit favorable `↑` and adverse `↓` evidence is mixed and must use the neutral marker and base font color. Outcome-aware phrases such as “beat expectations” and “above expectations” are favorable even if their explanation includes lower costs. Apply a PDF-only global font scale of `1.5` at the renderer boundary and scale multiline line heights by the same factor. Preserve the one-page A4 contract and every selected statement by reallocating unused panel height rather than dropping or clipping evidence.
- Risks are qualitative disclosures; the code does not invent probabilities or EPS impacts. When the company does not quantify them, render an explicit company-not-quantified disclosure instead of raw `N/A prob / N/A EPS impact` placeholders.
- Strategic pillars are independently selected durable themes using evidence distinct from the earnings-call summary, guidance, and channel cards; they must never be a copied view of transcript insights.
- Confidence reflects source and metric completeness.
- The grade is based on a documented evidence score, not a default letter.
- The five-year thesis derives EPS scenarios from reported growth and independently bounded exit multiples. Expected return is calculated from those assumptions rather than reverse-engineered from a target return.
- Recommendation can be `BUY`, `HOLD`, `SELL`, or `INSUFFICIENT DATA`; it is never predetermined.

## Rich output contract

The renderer consumes a company-neutral schema. Runtime source code must not contain ticker branches, company names, quarter-specific values, excerpts, recommendations, grades, or PDF coordinates tied to a particular issuer.

**Telegram Message 1 — Enhanced Dashboard** contains:

1. Ticker, verified fiscal quarter/year, grade, and confidence.
2. Financial highlights with values, YoY changes, and seven-level signals.
3. KPI immediately below Financial Highlights: the top 12 company-specific operating measures (within the requested 12–15 range) with current-quarter value, prior-year-quarter value, analyst view, `IR|SEC|IR/SEC` source, and importance. Every applicable Tier 1 row is retained; lower tiers fill the remaining slots by importance.
4. Valuation with explicit TTM versus annualized labels.
5. Key-risk matrix. Explicit company-quantified probability and EPS impact are shown when available; otherwise the report states that the company did not quantify them instead of rendering raw `N/A prob / N/A EPS impact` placeholders.
6. Evidence-backed key drivers.
7. Five-year base, bull, and bear thesis with transparent weights, EPS paths, exit multiples, prices, and IRRs.
8. SEC, IR/SEC release, and transcript links plus the PDF attachment notice.

**Telegram Message 2 — Earnings Call Summary** groups complete, coherent, evidence-linked statements under the seven signal levels. Prepared remarks and substantive management answers from analyst Q&A are both required. Analyst questions—including question fragments transcribed without a question mark—participant names/titles, lowercase continuation fragments, operator queue instructions, provider summaries, participant introductions, clipped words, and arbitrary keyword windows are excluded. Classify management confidence once during transcript enrichment from the aggregate verified management language using the ordered taxonomy `Confident -> Resolute|Authoritative|Decisive|Assured`, `Vague -> Evasive|Equivocal|Noncommittal|Ambiguous`, or `Not Confident -> Defensive / Faltering|Anxious|Hesitant|Tentative`. Use complete word/phrase boundaries so `confident` never matches `confidential`. Store category, subcategory, rank, and auditable aggregate-score reasoning on the structured `Management Tone` insight. Telegram renders `Management Tone: <category> -> <subcategory>, <statement>` first; the PDF consumes those same fields and must not independently classify them. The PDF is attached to this message too, matching the restored two-message contract.

**One-page PDF** preserves this hierarchy. Its Earnings Call Summary must use the same ordered insight selection as Telegram Message 2, then apply PDF-only true compression; topic icons and direction markers remain semantic, while the complete row font and direction marker use the source insight's seven-level signal color so neutral Telegram rows cannot become visually positive because they contain words such as “growth” or “increased.” Telegram formatting and delivery code remain unchanged by PDF presentation fixes.

- Header/recommendation metadata; recommendation typography must shrink dynamically so long labels such as `INSUFFICIENT DATA` cannot overlap the ticker
- Income Statement Highlights
- KPI — twelve compact source-backed operating scorecards in one A4-width row
- Key Ratios
- Valuation
- Short Interest & Stock-Based Compensation Metrics
- Capital & Liquidity / Guidance & Outlook / Earnings Call Summary
- Key Channels & Segments
- Strategic Pillars
- Key Risks / Investment Thesis
- Clickable SEC and transcript evidence footer

## Signal colors

The JSON, Markdown, Telegram messages, and PDF use a seven-level semantic scale:

- `best` — exceptional / darkest blue
- `strong_positive` — strong positive / deep blue
- `positive` — positive / dark blue
- `neutral` — neutral / yellow
- `caution` — caution / orange
- `negative` — negative / red
- `worst` — severe negative / dark red

The PDF uses ASCII markers to avoid missing emoji glyphs while retaining the same colors.

## Usage

Set the authorized Robinhood account in the environment before a live run:

```bash
export ROBINHOOD_EXPECTED_ACCOUNT="<authorized account number>"
python run_analysis.py --ticker <TICKER> --output-format both
```

Successful analyses deliver the two Telegram messages with the validated browser-rendered interactive A4 PDF attached automatically. Playwright waits for the final JavaScript metric cards before printing; delivery never uses a partially rendered page. Optional flags:

- `--max-filing-age-days N`
- `--output-format json|markdown|both|pdf`
- `--output-dir PATH`
- `--no-deliver` to suppress automatic delivery
- `--telegram-target telegram` or an explicit approved Hermes target
- `--dry-run` to construct delivery records without sending
- `--test-allow-stale-quote` only for an explicitly requested test run; it preserves the official Robinhood quote but visibly marks JSON, Markdown, PDF, and both Telegram messages `TEST ONLY — STALE MARKET DATA — NOT ACTIONABLE`. Normal runs still fail on stale quotes.

Delivery is automatic by user preference. Automated tests mock the delivery boundary and never contact Telegram.

## Outputs

Generated filenames use ticker and verified fiscal period:

- `<TICKER>_Qn_FYyyyy_analysis.json`
- `<TICKER>_Qn_FYyyyy_analysis.md`
- `<TICKER>_Qn_FYyyyy_Earnings_OnePager.pdf`
- `<TICKER>_Qn_FYyyyy_Interactive_Dashboard/index.html` plus static CSS, JavaScript, bundled Inter font, and reusable JSON data
- `<TICKER>_Qn_FYyyyy_Interactive_Dashboard.pdf` rendered from the final HTML, validated as one-page A4, and attached to both Telegram messages

The JSON excludes raw filing and transcript text while retaining source URLs and citations. The HTML dashboard is company-neutral, renders all repeated cards from generated JSON, works when opened locally, and is deployable to GitHub Pages without a backend. Income Statement Highlights uses all eight Tier 1 reference metrics in one fixed row and shows both YoY and QoQ labels, explicitly marking unavailable comparisons. KPI appears immediately below it and uses the business-KPI reference only: all applicable Tier 1 rows plus lower tiers selected by importance, with exactly twelve scorecards so the requested range remains legible inside one validated A4 page. Every KPI card carries current-quarter value, prior-year-quarter value, analyst view, importance, and an allowed source label. Unsupported company catalogues produce an explicit unavailable state rather than invented metrics. Key Ratios uses the four Tier 1 reference ratios plus only the lower-tier reference metrics selected by the generated analysis, capped at eight cards in one row. Grade Reasoning is rearranged into a compact six-column strip to preserve the one-page A4 boundary without changing unrelated scorecard formats. Capital & Liquidity, Guidance & Outlook, Earnings Call Summary, Key Channels & Segments, and Strategic Pillars render their selected source-backed statements in full without ellipsis truncation; the renderer waits for local fonts, adapts narrative typography to the fixed one-page panels, and applies each row's full seven-level signal color to its marker, label, value, and narrative. Capital & Liquidity consumes the structured `value` field, channel signals are preserved or derived from unambiguous directional evidence, and Management Tone retains the Telegram classification prefix (`category → subcategory`) before its complete statement. Valuation cards use compact semicircular gauges, tier badges, formula and impact copy from the repository reference guide, accessible detail dialogs, and a fixed eight-column, one-row maximum that retains every applicable Tier 1 metric before lower-tier selections. Short Interest & SBC is rendered as a signal-colored dense list directly below Capital & Liquidity; together those two stacked panels equal the height of Earnings Call Summary. Only applicable valuation metrics with verified, economically meaningful inputs are emitted, while unavailable required Tier 1 financial and ownership-risk metrics remain visible as explicit `N/A` cards/rows rather than being silently dropped. All interactive card variants retain keyboard activation. Each successful skill run replaces prior ticker JSON snapshots in `earnings-dashboard/data/` with `<TICKER>-<YYYY>-<QUARTER>.json` plus the current `report.json`/`report.js` aliases. The static dashboard itself has no runtime dependency; pipeline PDF rendering requires Playwright with Chromium or an explicit `PLAYWRIGHT_CLI` path.

## Verification

Run from the skill directory:

```bash
python3 -m py_compile run_analysis.py scripts/*.py tests/*.py
python3 -m unittest discover -s tests -v
```

The regression suite covers XBRL period/dimension selection, prior-year comparisons, source-backed business-KPI selection and no-bleed prior comparisons, derived key-ratio cards, enforced earnings-query filtering, complete prepared-remarks and Q&A transcripts, decimal-safe sentence boundaries, analyst-question and operator/provider-boilerplate rejection, non-invented risk quantification, number formatting, authorized-account verification, normal stale-quote rejection, conspicuous test-only stale labeling, delivery dry-run safety, missing attachments, the full KPI-inclusive one-page PDF hierarchy and clickable sources, both rich Telegram message contracts, non-predetermined recommendations, Markdown completeness, and absence of company-specific runtime fixtures.

## Robinhood MCP compatibility

The integration supports both MCP SDK 1.x (`isError`, `structuredContent`) and MCP SDK 2.x (`is_error`, `structured_content`) result models. Robinhood sessions are cached under `~/.tokens/` with directory mode `0700` and token-file mode `0600`. A malformed TOTP value falls back to Robinhood app approval rather than crashing login. Authentication or account mismatch still fails closed and never activates unofficial market-data fallbacks.

<!-- END OF SKILL.md -->
