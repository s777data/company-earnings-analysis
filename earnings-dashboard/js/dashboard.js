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

  function kpiCard(metric) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `kpi-card ${statusClass(metric.status)}`;
    button.setAttribute("aria-label", `Open KPI details for ${text(metric.name)}: ${text(metric.latest_value)}`);

    const header = document.createElement("span");
    header.className = "kpi-card-header";

    const heading = document.createElement("span");
    heading.className = "kpi-card-name";
    heading.textContent = text(metric.name);

    const badges = document.createElement("span");
    badges.className = "kpi-badges";
    for (const [className, label] of [["kpi-source", metric.source], ["kpi-tier", metric.importance]]) {
      const badge = document.createElement("span");
      badge.className = className;
      badge.textContent = text(label);
      badges.append(badge);
    }
    header.append(heading, badges);

    const latest = document.createElement("span");
    latest.className = "kpi-latest";
    const latestValue = document.createElement("strong");
    const latestText = text(metric.latest_value);
    latestValue.textContent = latestText;
    if (latestText.length > 12) latestValue.classList.add("kpi-value--long");
    const latestPeriod = document.createElement("small");
    latestPeriod.textContent = text(metric.latest_period);
    latest.append(latestValue, latestPeriod);

    const divider = document.createElement("span");
    divider.className = "kpi-divider";
    divider.setAttribute("aria-hidden", "true");

    const prior = document.createElement("span");
    prior.className = "kpi-prior";
    const priorValue = document.createElement("strong");
    const priorText = text(metric.prior_value);
    priorValue.textContent = priorText;
    if (priorText.length > 12) priorValue.classList.add("kpi-value--long");
    const priorPeriod = document.createElement("small");
    priorPeriod.textContent = text(metric.prior_period);
    prior.append(priorValue, priorPeriod);

    const view = document.createElement("span");
    view.className = "kpi-view";
    const viewLabel = document.createElement("strong");
    viewLabel.textContent = "Analyst view";
    view.append(viewLabel, document.createTextNode(text(metric.analyst_view, "No source-backed comparison available.")));

    button.append(header, latest, divider, prior, view);
    button.addEventListener("click", () => openMetric(metric, button));
    return button;
  }

  function renderKpis(metrics) {
    const container = $("kpi-cards");
    const items = (metrics || []).slice(0, 16);
    container.classList.remove("kpi-grid--single", "kpi-grid--double");
    if (items.length === 0) {
      container.replaceChildren(emptyState("No applicable source-backed business KPI catalogue was available."));
      return;
    }

    const split = Math.ceil(items.length / 2);
    const rows = items.length <= 8 ? [items] : [items.slice(0, split), items.slice(split)];
    container.classList.add(items.length <= 8 ? "kpi-grid--single" : "kpi-grid--double");
    container.replaceChildren(...rows.map((rowItems) => {
      const row = document.createElement("div");
      row.className = "kpi-row";
      row.style.setProperty("--kpi-columns", String(rowItems.length));
      row.replaceChildren(...rowItems.map(kpiCard));
      return row;
    }));
  }

  function gaugeDomain(metric) {
    const value = Number(metric.raw_value);
    const scale = metric.scale || [];
    if (!Number.isFinite(value) || scale.length === 0) return null;
    const finiteMaximums = scale.filter((step) => step.max !== null).map((step) => Number(step.max)).filter(Number.isFinite);
    if (finiteMaximums.length === 0) return null;
    const largest = Math.max(...finiteMaximums);
    const minimum = Math.min(0, value);
    const ceiling = Math.max(largest * 1.35, 1);
    return {
      minimum,
      ceiling,
      position: Math.max(0, Math.min(1, (value - minimum) / (ceiling - minimum)))
    };
  }

  function arcPoint(position) {
    const angle = Math.PI * (1 - position);
    return [50 + 42 * Math.cos(angle), 46 - 42 * Math.sin(angle)];
  }

  function arcSegment(start, end) {
    const [x1, y1] = arcPoint(start);
    const [x2, y2] = arcPoint(end);
    return `M${x1.toFixed(2)} ${y1.toFixed(2)} A42 42 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
  }

  function thresholdSuffix(metric) {
    const display = text(metric.display_value);
    if (display.endsWith("%")) return "%";
    if (display.endsWith("d")) return "d";
    if (display.endsWith("x")) return "x";
    return "";
  }

  function gaugeCard(metric) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `gauge-card ${statusClass(metric.status)}`;
    button.setAttribute("aria-label", `Open details for ${text(metric.name)}: ${text(metric.display_value)}, ${text(metric.assessment)}`);

    const header = document.createElement("span");
    header.className = "gauge-card-header";
    const name = document.createElement("span");
    name.className = "gauge-card-name";
    name.textContent = text(metric.name);
    const tier = document.createElement("span");
    tier.className = "gauge-tier";
    tier.textContent = Number.isFinite(Number(metric.tier)) ? `Tier ${metric.tier}` : "Context";
    header.append(name, tier);

    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 100 58");
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("mini-gauge");
    const domain = gaugeDomain(metric);
    const scale = metric.scale || [];
    const higherIsBetter = /higher/i.test(text(metric.directionality, ""));
    const lowerPalettes = {
      2: ["#16a34a", "#dc2626"],
      3: ["#16a34a", "#facc15", "#dc2626"],
      4: ["#16a34a", "#facc15", "#f97316", "#dc2626"],
      5: ["#16a34a", "#84cc16", "#facc15", "#f97316", "#dc2626"]
    };
    const basePalette = lowerPalettes[Math.max(2, Math.min(5, scale.length))] || lowerPalettes[5];
    const palette = higherIsBetter ? [...basePalette].reverse() : basePalette;

    const track = document.createElementNS(namespace, "path");
    track.setAttribute("d", "M8 46 A42 42 0 0 1 92 46");
    track.classList.add("gauge-track");
    svg.append(track);

    if (domain) {
      let start = 0;
      scale.forEach((step, index) => {
        const rawEnd = step.max === null ? domain.ceiling : Number(step.max);
        const end = Math.max(start, Math.min(1, (rawEnd - domain.minimum) / (domain.ceiling - domain.minimum)));
        const segment = document.createElementNS(namespace, "path");
        segment.setAttribute("d", arcSegment(start, end));
        segment.setAttribute("stroke", palette[Math.min(index, palette.length - 1)]);
        segment.classList.add("gauge-arc", "gauge-segment");
        svg.append(segment);
        start = end;
      });
      if (start < 1) {
        const finalSegment = document.createElementNS(namespace, "path");
        finalSegment.setAttribute("d", arcSegment(start, 1));
        finalSegment.setAttribute("stroke", palette[Math.min(scale.length - 1, palette.length - 1)]);
        finalSegment.classList.add("gauge-arc", "gauge-segment");
        svg.append(finalSegment);
      }

      const suffix = thresholdSuffix(metric);
      const finiteThresholds = scale.filter((step) => step.max !== null).map((step) => Number(step.max));
      const labels = [`<${finiteThresholds[0]}${suffix}`, ...finiteThresholds.map((value) => `${value}${suffix}`), `>${finiteThresholds.at(-1)}${suffix}`];
      const positions = [0, ...finiteThresholds.map((value) => Math.max(0, Math.min(1, (value - domain.minimum) / (domain.ceiling - domain.minimum)))), 1];
      labels.forEach((label, index) => {
        const [x, y] = arcPoint(positions[index]);
        const node = document.createElementNS(namespace, "text");
        node.setAttribute("x", x.toFixed(2));
        node.setAttribute("y", (y + (index === 0 || index === labels.length - 1 ? 8 : -3)).toFixed(2));
        node.setAttribute("text-anchor", index === 0 ? "start" : index === labels.length - 1 ? "end" : "middle");
        node.classList.add("gauge-threshold");
        node.textContent = label;
        svg.append(node);
      });

      const needle = document.createElementNS(namespace, "line");
      needle.setAttribute("x1", "50"); needle.setAttribute("y1", "46");
      needle.setAttribute("x2", "50"); needle.setAttribute("y2", "17");
      needle.setAttribute("transform", `rotate(${-90 + domain.position * 180} 50 46)`);
      needle.classList.add("gauge-needle");
      const hub = document.createElementNS(namespace, "circle");
      hub.setAttribute("cx", "50"); hub.setAttribute("cy", "46"); hub.setAttribute("r", "2.4");
      hub.classList.add("gauge-hub");
      svg.append(needle, hub);
    } else {
      svg.classList.add("gauge-unscaled");
      const fallbackPalette = higherIsBetter
        ? ["#dc2626", "#facc15", "#f97316", "#16a34a"]
        : ["#16a34a", "#facc15", "#f97316", "#dc2626"];
      fallbackPalette.forEach((color, index) => {
        const segment = document.createElementNS(namespace, "path");
        segment.setAttribute("d", arcSegment(index / fallbackPalette.length, (index + 1) / fallbackPalette.length));
        segment.setAttribute("stroke", color);
        segment.classList.add("gauge-arc", "gauge-segment", "gauge-context-segment");
        svg.append(segment);
      });
    }

    const result = document.createElement("span");
    result.className = "gauge-result";
    const value = document.createElement("strong");
    value.textContent = text(metric.display_value);
    const assessment = document.createElement("span");
    assessment.textContent = text(metric.assessment, "Context Only");
    const direction = document.createElement("small");
    direction.textContent = text(metric.directionality);
    result.append(value, assessment, direction);

    const facts = document.createElement("span");
    facts.className = "gauge-facts";
    const formula = document.createElement("span");
    formula.textContent = `▣ ${compact(metric.formula, 62)}`;
    const impact = document.createElement("span");
    impact.textContent = `↗ ${compact(metric.why_it_matters, 66)}`;
    facts.append(formula, impact);

    button.append(header, svg, result, facts);
    button.addEventListener("click", () => openMetric(metric, button));
    return button;
  }

  function renderGaugeMetrics(id, metrics) {
    const container = $(id);
    const items = (metrics || []).slice(0, 8);
    container.replaceChildren(...items.map(gaugeCard));
    if (items.length === 0) container.append(emptyState("No applicable verified metrics available."));
  }

  function renderMetrics(id, metrics, variant = "default") {
    const container = $(id);
    const items = (metrics || []).slice(0, 8);
    if (variant === "ratio") {
      container.style.setProperty("--ratio-columns", String(Math.max(items.length, 1)));
    }
    container.replaceChildren(...items.map((metric) => metricCard(metric, variant)));
    if (!metrics || metrics.length === 0) container.append(emptyState("No verified metrics available."));
  }

  function emptyState(message) {
    const row = document.createElement("div");
    row.className = "dense-item status-neutral";
    row.textContent = message;
    return row;
  }

  function detailOf(item) {
    return item.detail || item.desc || item.evidence || item.driver || item.text || item.summary || item.quantification || item.value;
  }

  function labelOf(item) {
    return item.name || item.topic || item.risk || item.label || "";
  }

  function denseItem(item, limit = null) {
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
    const detail = text(detailOf(item), "Not available").replace(/\s+/g, " ").trim();
    body.append(document.createTextNode(limit ? compact(detail, limit) : detail));
    row.append(icon, body);
    return row;
  }

  function renderList(id, items, maximum, limit = null) {
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
      body.textContent = text(detailOf(item), "Not available").replace(/\s+/g, " ").trim();
      card.append(heading, body);
      return card;
    }));
    if (selected.length === 0) container.append(emptyState("No verified evidence available."));
  }

  function fitText(container, minimumPx, decrementPx = 0.15) {
    if (!container || container.clientHeight === 0) return;
    let size = Number.parseFloat(getComputedStyle(container).fontSize);
    while (container.scrollHeight > container.clientHeight + 1 && size > minimumPx) {
      size = Math.max(minimumPx, size - decrementPx);
      container.style.fontSize = `${size.toFixed(2)}px`;
    }
    container.dataset.fitted = container.scrollHeight <= container.clientHeight + 1 ? "true" : "false";
  }

  function fitNarrativeSections() {
    ["capital-content", "short-interest-content", "guidance-content", "call-content"].forEach((id) => fitText($(id), 3.65));
    document.querySelectorAll(".channel-card, .pillar-card").forEach((card) => fitText(card, 3.55));
    document.body.dataset.layoutReady = "true";
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

  function renderGradeReasoning(gradeBreakdown) {
    const container = $("grade-reasoning-content");
    if (!gradeBreakdown) {
      container.append(emptyState("Grade breakdown not available."));
      return;
    }
    
    const categories = [
      { key: "financial_metrics", label: "Financial Metrics", icon: "📊" },
      { key: "valuation", label: "Valuation", icon: "💰" },
      { key: "earnings_call", label: "Earnings Call", icon: "📞" },
      { key: "management_execution", label: "Management Execution", icon: "👔" },
      { key: "future_growth", label: "Future Growth", icon: "🚀" },
    ];
    
    const rows = [];
    
    for (const cat of categories) {
      const data = gradeBreakdown[cat.key];
      if (!data) continue;
      
      const grade = data.grade || "N/A";
      const reason = data.reason || "No reasoning available";
      const weight = data.weight || 0;
      
      // Signal based on grade
      let signal = "neutral";
      if (grade.startsWith("A")) signal = "positive";
      else if (grade.startsWith("B")) signal = "positive";
      else if (grade.startsWith("C+")) signal = "neutral";
      else if (grade.startsWith("C")) signal = "caution";
      else if (grade.startsWith("D")) signal = "negative";
      else if (grade === "F") signal = "worst";
      
      rows.push({ 
        name: `${cat.icon} ${cat.label} (${Math.round(weight * 100)}%)`, 
        detail: `${grade} — ${reason}`, 
        signal 
      });
    }
    
    // Final grade
    const finalGrade = gradeBreakdown.final_grade || "N/A";
    const finalScore = gradeBreakdown.final_score || 0;
    let finalSignal = "neutral";
    if (finalGrade.startsWith("A")) finalSignal = "best";
    else if (finalGrade.startsWith("B")) finalSignal = "positive";
    else if (finalGrade.startsWith("C+")) finalSignal = "neutral";
    else if (finalGrade.startsWith("C")) finalSignal = "caution";
    else if (finalGrade.startsWith("D")) finalSignal = "negative";
    else if (finalGrade === "F") finalSignal = "worst";
    
    rows.push({ 
      name: "🏁 Final Grade (weighted)", 
      detail: `${finalGrade} (score: ${finalScore.toFixed(2)})`, 
      signal: finalSignal 
    });
    
    renderList("grade-reasoning-content", rows, 6, 200);
  }

  function sourceLinks(sources) {
    const container = $("source-links");
    container.replaceChildren();
    const links = [["SEC", sources.filing_url], ["XBRL", sources.xbrl_url], ["IR", sources.investor_relations_url], ["IR/SEC release", sources.earnings_release_url], ["Transcript", sources.transcript_url], ["Short interest", sources.short_interest_url]].filter(([, url]) => url);
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
    renderKpis(sections.business_kpis);
    renderMetrics("ratio-cards", sections.key_ratios, "ratio");
    $("valuation-regime").textContent = `${text(sections.valuation_regime, "Applicable metrics")} · guide order · applicable only`;
    renderGaugeMetrics("valuation-cards", sections.valuation);
    renderList("capital-content", sections.capital_liquidity, 8);
    renderList("short-interest-content", sections.short_interest_sbc, 6);
    renderList("guidance-content", sections.guidance, 6);
    renderList("call-content", sections.earnings_call, 8);
    renderCards("channels-content", sections.channels, "channel");
    renderCards("pillars-content", sections.strategic_pillars, "pillar");
    renderList("risks-content", sections.risks, 5, 155);
    renderThesis(sections.thesis || {});
    
    // Render grade reasoning
    renderGradeReasoning(report.grade_breakdown);
    
    sourceLinks(report.sources || {});
    document.body.dataset.layoutReady = "false";
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => requestAnimationFrame(fitNarrativeSections));
    } else {
      requestAnimationFrame(fitNarrativeSections);
    }
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
