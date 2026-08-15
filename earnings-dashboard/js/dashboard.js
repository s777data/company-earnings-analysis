(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const statusLabel = (status) => String(status || "neutral").replaceAll("_", " ");
  const statusClass = (status) => `status-${String(status || "neutral").replace(/[^a-z_]/g, "")}`;
  const marker = (status) => ({
    best: "↑", strong_positive: "↑", positive: "↑", neutral: "→",
    caution: "!", negative: "↓", worst: "↓"
  })[status] || "→";
  const text = (value, fallback = "N/A") => value === null || value === undefined || value === "" ? fallback : String(value);
  const compact = (value, maximum = 185) => {
    const clean = text(value, "Not available").replace(/\s+/g, " ").trim();
    return clean.length <= maximum ? clean : `${clean.slice(0, maximum - 1).trimEnd()}…`;
  };
  const formatMoney = (value) => {
    if (!Number.isFinite(value)) return "N/A";
    const absolute = Math.abs(value);
    const sign = value < 0 ? "-" : "";
    if (absolute >= 1e12) return `${sign}$${(absolute / 1e12).toFixed(1)}T`;
    if (absolute >= 1e9) return `${sign}$${(absolute / 1e9).toFixed(1)}B`;
    if (absolute >= 1e6) return `${sign}$${(absolute / 1e6).toFixed(1)}M`;
    return `${sign}$${absolute.toLocaleString()}`;
  };

  let lastTrigger = null;
  const dialog = $("metric-dialog");

  function scaleIndex(metric) {
    const value = Number(metric.raw_value);
    if (!Number.isFinite(value)) return -1;
    return (metric.scale || []).findIndex((step) => step.max === null || value < Number(step.max));
  }

  function openMetric(metric, trigger) {
    lastTrigger = trigger;
    $("dialog-title").textContent = text(metric.name);
    $("dialog-value").textContent = text(metric.display_value);
    $("dialog-status").textContent = `Status: ${statusLabel(metric.status)}`;
    $("dialog-status").className = `dialog-status ${statusClass(metric.status)}`;
    $("dialog-description").textContent = text(metric.description);
    $("dialog-why").textContent = text(metric.why_it_matters);
    $("dialog-direction").textContent = text(metric.directionality);
    $("dialog-formula").textContent = text(metric.formula);
    $("dialog-source").textContent = text(metric.source_note);
    const scale = $("dialog-scale");
    scale.replaceChildren();
    const active = scaleIndex(metric);
    if (!metric.scale || metric.scale.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No universal threshold scale applies; interpret this metric in company and industry context.";
      scale.append(empty);
    } else {
      metric.scale.forEach((step, index) => {
        const segment = document.createElement("div");
        segment.className = `scale-segment ${statusClass(step.signal)}${index === active ? " active" : ""}`;
        segment.textContent = step.label;
        segment.setAttribute("aria-label", `${step.label}${index === active ? ", current range" : ""}`);
        scale.append(segment);
      });
    }
    dialog.showModal();
  }

  dialog.addEventListener("close", () => {
    if (lastTrigger) lastTrigger.focus();
  });

  function comparisonTrend(comparison) {
    const value = text(comparison, "");
    if (/^\s*\+/.test(value)) return { className: "trend-up", marker: "▲" };
    if (/^\s*-/.test(value)) return { className: "trend-down", marker: "▼" };
    return { className: "trend-flat", marker: "" };
  }

  function metricCard(metric, variant = "default") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `metric-card metric-card--${variant} ${statusClass(metric.status)}`;
    button.setAttribute("aria-label", `Open details for ${text(metric.name)}: ${text(metric.display_value)}, ${statusLabel(metric.status)}`);
    const value = document.createElement("span");
    value.className = "metric-value";
    value.textContent = text(metric.display_value);
    const name = document.createElement("span");
    name.className = "metric-name";
    name.textContent = text(metric.name);
    const comparison = document.createElement("span");
    comparison.className = "metric-comparison";
    comparison.textContent = text(metric.comparison, "Comparison unavailable");

    if (variant === "income") {
      const trend = comparisonTrend(metric.comparison);
      comparison.classList.add("comparison-badge", trend.className);
      if (trend.marker) comparison.textContent = `${trend.marker}  ${comparison.textContent}`;
      button.append(name, value, comparison);
    } else if (variant === "ratio") {
      const divider = document.createElement("span");
      divider.className = "metric-divider";
      divider.setAttribute("aria-hidden", "true");
      button.append(name, value, divider, comparison);
    } else {
      button.append(value, name, comparison);
    }
    button.addEventListener("click", () => openMetric(metric, button));
    return button;
  }

  function renderMetrics(id, metrics, variant = "default") {
    const container = $(id);
    container.replaceChildren(...(metrics || []).map((metric) => metricCard(metric, variant)));
    if (!metrics || metrics.length === 0) container.append(emptyState("No verified metrics available."));
  }

  function emptyState(message) {
    const row = document.createElement("div");
    row.className = "dense-item status-neutral";
    row.textContent = message;
    return row;
  }

  function detailOf(item) {
    return item.detail || item.desc || item.evidence || item.driver || item.text || item.summary || item.quantification;
  }

  function labelOf(item) {
    return item.name || item.topic || item.risk || item.label || "";
  }

  function denseItem(item, limit = 185) {
    const status = item.signal || item.tier || "neutral";
    const row = document.createElement("div");
    row.className = `dense-item ${statusClass(status)}`;
    const icon = document.createElement("span");
    icon.className = "marker";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = marker(status);
    const body = document.createElement("span");
    const label = labelOf(item);
    if (label) {
      const strong = document.createElement("strong");
      strong.textContent = `${label}: `;
      body.append(strong);
    }
    body.append(document.createTextNode(compact(detailOf(item), limit)));
    row.append(icon, body);
    return row;
  }

  function renderList(id, items, maximum, limit) {
    const container = $(id);
    const selected = (items || []).slice(0, maximum);
    container.replaceChildren(...selected.map((item) => denseItem(item, limit)));
    if (selected.length === 0) container.append(emptyState("No verified evidence available."));
  }

  function renderCards(id, items, type) {
    const container = $(id);
    const selected = (items || []).slice(0, type === "channel" ? 4 : 5);
    container.replaceChildren(...selected.map((item) => {
      const status = item.signal || item.tier || "neutral";
      const card = document.createElement("article");
      card.className = `${type}-card ${statusClass(status)}`;
      const heading = document.createElement("h3");
      heading.textContent = text(labelOf(item), type === "channel" ? "Business area" : "Strategic theme");
      const body = document.createElement("div");
      body.textContent = compact(detailOf(item), type === "channel" ? 170 : 145);
      card.append(heading, body);
      return card;
    }));
    if (selected.length === 0) container.append(emptyState("No verified evidence available."));
  }

  function renderThesis(thesis) {
    const rows = [];
    if (thesis.recommendation) rows.push({ name: "Recommendation", detail: thesis.recommendation, signal: "neutral" });
    for (const [key, label] of [["base_case", "Base"], ["bull_case", "Bull"], ["bear_case", "Bear"]]) {
      if (thesis[key]) rows.push({ name: label, detail: thesis[key].summary || thesis[key].detail, signal: key === "bull_case" ? "positive" : key === "bear_case" ? "negative" : "neutral" });
    }
    if (thesis.method) rows.push({ name: "Method", detail: thesis.method, signal: "neutral" });
    renderList("thesis-content", rows, 4, 155);
  }

  function sourceLinks(sources) {
    const container = $("source-links");
    container.replaceChildren();
    const links = [["SEC", sources.filing_url], ["XBRL", sources.xbrl_url], ["Transcript", sources.transcript_url]].filter(([, url]) => url);
    links.forEach(([label, url], index) => {
      if (index) container.append(document.createTextNode(" • "));
      const link = document.createElement("a");
      link.href = url;
      link.textContent = label;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      container.append(link);
    });
  }

  function render(report) {
    if (!report || !report.company || !report.sections) throw new Error("The report JSON does not match the dashboard schema.");
    const company = report.company;
    const sections = report.sections;
    $("grade").textContent = text(company.grade);
    $("confidence").textContent = Number.isFinite(company.confidence) ? `${Math.round(company.confidence * 100)}% CONF.` : "CONF. N/A";
    $("recommendation").textContent = text(company.recommendation);
    $("ticker").textContent = text(company.ticker);
    document.title = `${text(company.ticker)} ${text(company.period)} Earnings Dashboard`;
    const market = [
      company.report_date ? `Quarter Ended ${company.report_date}` : null,
      company.call_date ? `Call: ${company.call_date}` : null,
      Number.isFinite(company.price) ? `$${company.price.toFixed(2)}` : null,
      Number.isFinite(company.market_cap) ? `Mkt Cap ${formatMoney(company.market_cap)}` : null,
      Number.isFinite(company.pe_ttm) ? `P/E ${company.pe_ttm.toFixed(1)}x` : null,
      Number.isFinite(company.low_52) && Number.isFinite(company.high_52) ? `52W $${company.low_52.toFixed(2)}–$${company.high_52.toFixed(2)}` : null,
    ].filter(Boolean);
    $("period-line").textContent = market.join(" | ") || text(company.period);
    $("test-banner").hidden = !company.test_run;

    renderMetrics("income-cards", sections.income_statement, "income");
    renderMetrics("ratio-cards", sections.key_ratios, "ratio");
    renderMetrics("valuation-cards", sections.valuation);
    renderList("capital-content", sections.capital_liquidity, 8, 120);
    renderList("guidance-content", sections.guidance, 6, 155);
    renderList("call-content", sections.earnings_call, 8, 165);
    renderCards("channels-content", sections.channels, "channel");
    renderCards("pillars-content", sections.strategic_pillars, "pillar");
    renderList("risks-content", sections.risks, 5, 155);
    renderThesis(sections.thesis || {});
    sourceLinks(report.sources || {});
  }

  function showError(error) {
    const box = $("load-error");
    box.textContent = `Dashboard data error: ${error.message}`;
    box.hidden = false;
  }

  $("print-button").addEventListener("click", () => window.print());
  $("report-file").addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (!file) return;
    try {
      render(JSON.parse(await file.text()));
      $("load-error").hidden = true;
    } catch (error) { showError(error); }
  });

  try {
    render(window.EARNINGS_REPORT);
  } catch (error) {
    showError(error);
  }
})();
