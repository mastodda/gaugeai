#!/usr/bin/env node
/**
 * generate_report_pptx.js — SSR Toolkit PowerPoint Report Generator
 *
 * Usage:
 *   node generate_report_pptx.js --results results.json --personas personas.json --insights insights.json --output report.pptx
 *
 * Reads pipeline output files and generates a client-ready PowerPoint deck.
 */

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
const args = {};
process.argv.slice(2).forEach((arg, i, arr) => {
  if (arg.startsWith("--") && arr[i + 1]) args[arg.slice(2)] = arr[i + 1];
});

const resultsPath = args.results || "results.json";
const personasPath = args.personas || "personas.json";
const insightsPath = args.insights || path.join(path.dirname(resultsPath), "insights.json");
const outputPath = args.output || "ssr_report.pptx";

// ---------------------------------------------------------------------------
// Load data
// ---------------------------------------------------------------------------
const results = JSON.parse(fs.readFileSync(resultsPath, "utf8"));
const personas = JSON.parse(fs.readFileSync(personasPath, "utf8"));

const meta = results.meta || {};
const engagement = meta.engagement || {};
const pipelineConfig = meta.pipeline_config || {};
const conceptIds = Object.keys(results.concepts);

let rawInsights = { concepts: {} };
try {
  rawInsights = JSON.parse(fs.readFileSync(insightsPath, "utf8"));
} catch (e) {
  console.warn(`⚠ No insights file found at ${insightsPath} — drivers/barriers slides will be empty.`);
}

// Normalize insights: the pipeline produces two different formats.
// Old/mock format:  { concepts: { concept_a: { purchase_drivers, pain_points, recommendations, ... } } }
// Real pipeline:    { concept_specific: { "Concept Name": { strengths: [...], weaknesses: [...], best_audience } },
//                     recommended_actions: [...], topic_analysis: [...], headline, concept_comparison, segment_insights }
//   NOTE: concept_specific is keyed by concept NAME, not concept ID.
const insights = { concepts: {} };

if (rawInsights.concepts && Object.keys(rawInsights.concepts).length > 0) {
  // Old format — use directly
  insights.concepts = rawInsights.concepts;
} else if (rawInsights.concept_specific && Object.keys(rawInsights.concept_specific).length > 0) {
  // Real pipeline format — need to match concept names to concept IDs
  const nameToId = {};
  conceptIds.forEach(cid => {
    const name = results.concepts[cid]?.concept?.name || cid;
    nameToId[name] = cid;
  });

  for (const [cname, cdata] of Object.entries(rawInsights.concept_specific)) {
    const cid = nameToId[cname] || cname;

    // Build purchase_drivers from concept strengths
    const drivers = (cdata.strengths || []).map(s => ({
      theme: typeof s === "string" ? s : (s.theme || ""),
      representative_quote: "",
      frequency: "",
    }));

    // Build pain_points from topic_analysis barriers/mixed + keyword frequencies
    // NOT from concept weaknesses (those are just metric summaries like "24% Bottom 2 Box")
    const painPoints = [];

    // First: topic_analysis items with role "barrier" or "mixed"
    if (rawInsights.topic_analysis) {
      rawInsights.topic_analysis
        .filter(t => t.role === "barrier" || t.role === "mixed")
        .forEach(t => {
          painPoints.push({
            theme: t.topic,
            severity: t.role === "barrier" ? "high" : "medium",
            representative_quote: t.concept_difference || t.detail || "",
            frequency: t.mention_rate ? `mentioned by ${t.mention_rate}` : "",
          });
        });
    }

    // Second: supplement from _precomputed keyword frequencies (barrier-type topics)
    const barrierKeywords = {
      "fit/sizing": "Consumers expressed uncertainty about fit and sizing, wanting more detail before committing to purchase.",
      "lifestyle_mismatch": "Many respondents said the product doesn't fit their current lifestyle or wardrobe needs.",
      "comparison_shopping": "Respondents indicated they would compare with other brands before purchasing.",
      "skepticism": "Consumers expressed skepticism about the product claims or value proposition.",
      "returns": "Concerns about return policy and the risk of ordering without trying first.",
    };
    const precomputed = rawInsights._precomputed?.[cid] || {};
    const kwFreqs = precomputed.keyword_frequencies || {};
    for (const [kw, description] of Object.entries(barrierKeywords)) {
      if (kwFreqs[kw] && kwFreqs[kw].pct > 15 && !painPoints.find(p => p.theme.toLowerCase().includes(kw.split("/")[0]))) {
        painPoints.push({
          theme: kw.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
          severity: kwFreqs[kw].pct > 50 ? "high" : "medium",
          representative_quote: description,
          frequency: `mentioned by ${kwFreqs[kw].pct}% of respondents`,
        });
      }
    }

    // Fallback: if still no pain points, use weaknesses as last resort
    if (painPoints.length === 0) {
      (cdata.weaknesses || []).forEach(w => {
        painPoints.push({
          theme: typeof w === "string" ? w : (w.theme || ""),
          severity: "medium",
          representative_quote: "",
          frequency: "",
        });
      });
    }

    insights.concepts[cid] = {
      executive_summary: "",
      purchase_drivers: drivers,
      pain_points: painPoints.slice(0, 4),
      recommendations: [],
      demographic_highlights: cdata.best_audience
        ? [typeof cdata.best_audience === "string" ? cdata.best_audience : JSON.stringify(cdata.best_audience)]
        : [],
    };
  }

  // Enrich drivers with topic_analysis quotes/details
  if (rawInsights.topic_analysis) {
    // Add topic analysis as additional drivers/context to all concepts
    const topicDrivers = rawInsights.topic_analysis.filter(t => t.role === "driver").slice(0, 3);
    const topicBarriers = rawInsights.topic_analysis.filter(t => t.role === "barrier" || t.role === "mixed").slice(0, 2);

    for (const cid of conceptIds) {
      if (!insights.concepts[cid]) continue;
      // Prepend topic drivers if concept has few drivers
      if (insights.concepts[cid].purchase_drivers.length === 0) {
        insights.concepts[cid].purchase_drivers = topicDrivers.map(t => ({
          theme: t.topic,
          representative_quote: t.detail || "",
          frequency: t.mention_rate ? `mentioned ${t.mention_rate}` : "",
        }));
      }
    }
  }

  // Enrich with segment_insights quotes
  if (rawInsights.segment_insights) {
    for (const cid of conceptIds) {
      if (!insights.concepts[cid]) continue;
      // Add segment evidence as representative quotes to existing drivers
      rawInsights.segment_insights.slice(0, 3).forEach((seg, i) => {
        if (insights.concepts[cid].purchase_drivers[i] && seg.evidence) {
          insights.concepts[cid].purchase_drivers[i].representative_quote = seg.evidence;
        }
      });
    }
  }

  // Top-level recommended_actions
  insights.recommended_actions = rawInsights.recommended_actions || [];
  insights.headline = rawInsights.headline || "";
  insights.concept_comparison = rawInsights.concept_comparison || null;
} else {
  console.warn("⚠ Insights file has no concept data — drivers/barriers slides will be empty.");
}

console.log(`✓ Loaded insights: ${Object.keys(insights.concepts).length} concepts`);

// (meta, engagement, pipelineConfig, conceptIds declared above)

// ---------------------------------------------------------------------------
// Design tokens
// ---------------------------------------------------------------------------
const C = {
  navy:       "1E2761",
  iceBlue:    "CADCFC",
  white:      "FFFFFF",
  offWhite:   "F5F7FA",
  darkText:   "1E293B",
  mutedText:  "64748B",
  green:      "059669",
  red:        "DC2626",
  amber:      "D97706",
  chart1:     "1E2761",
  chart2:     "3B82F6",
  chart3:     "06B6D4",
  chart4:     "8B5CF6",
  chart5:     "EC4899",
  accentBar:  "3B82F6",
};

const FONT = { head: "Georgia", body: "Calibri" };
const SLIDE_W = 10;
const SLIDE_H = 5.625;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeShadow() {
  return { type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.10 };
}

function conceptName(cid) {
  const c = results.concepts[cid];
  return c?.concept?.name || cid;
}

function dist(cid) {
  const agg = results.concepts[cid]?.aggregate || {};
  return agg.distribution || {};
}

function meanPI(cid) {
  return results.concepts[cid]?.aggregate?.mean_pi || 0;
}

function stdPI(cid) {
  return results.concepts[cid]?.aggregate?.std_pi || 0;
}

function nRespondents(cid) {
  return results.concepts[cid]?.aggregate?.n_respondents || 0;
}

function top2Box(cid) {
  const d = dist(cid);
  return ((parseFloat(d["4"]) || 0) + (parseFloat(d["5"]) || 0)) * 100;
}

function bot2Box(cid) {
  const d = dist(cid);
  return ((parseFloat(d["1"]) || 0) + (parseFloat(d["2"]) || 0)) * 100;
}

function posNegRatio(cid) {
  const t = top2Box(cid);
  const b = bot2Box(cid);
  return b > 0 ? (t / b) : 99;
}

function pctStr(v) { return (v).toFixed(1) + "%"; }

function truncate(str, maxLen) {
  if (!str) return "";
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 1).trim() + "…";
}

// Pick curated reasoning excerpts — short ones from different sentiment bands
function pickExcerpts(cid, count = 3) {
  const respondents = results.concepts[cid]?.respondents || [];
  if (respondents.length === 0) return [];

  // Sort by expected rating to get spread
  const sorted = [...respondents]
    .filter(r => r.reasoning_response)
    .sort((a, b) => (a.expected_rating || 3) - (b.expected_rating || 3));

  if (sorted.length === 0) return [];

  const picks = [];
  const step = Math.max(1, Math.floor(sorted.length / count));
  for (let i = 0; i < count && i * step < sorted.length; i++) {
    const r = sorted[i * step];
    // Extract first 1-2 sentences
    const full = r.reasoning_response || "";
    const sentences = full.match(/[^.!?]+[.!?]+/g) || [full];
    const excerpt = sentences.slice(0, 2).join("").trim();
    picks.push({
      text: truncate(excerpt, 180),
      rating: r.expected_rating ? r.expected_rating.toFixed(1) : "—",
      persona: r.persona_id || "",
    });
  }
  return picks;
}

// ---------------------------------------------------------------------------
// Slide builders
// ---------------------------------------------------------------------------
function addFooter(slide, pageNum) {
  slide.addText(
    engagement.engagement || "SSR Report",
    { x: 0.5, y: 5.25, w: 5, h: 0.3, fontSize: 8, color: C.mutedText, fontFace: FONT.body }
  );
  if (pageNum) {
    slide.addText(
      String(pageNum),
      { x: 9, y: 5.25, w: 0.5, h: 0.3, fontSize: 8, color: C.mutedText, fontFace: FONT.body, align: "right" }
    );
  }
}

// --- Slide 1: Title ---
function buildTitleSlide(pres) {
  const slide = pres.addSlide();
  slide.background = { color: C.navy };

  slide.addText(
    (engagement.engagement || "Concept Test").toUpperCase(),
    { x: 0.8, y: 1.4, w: 8.4, h: 1.2, fontSize: 36, fontFace: FONT.head, color: C.white, bold: true }
  );

  slide.addText("Synthetic Consumer Panel Study", {
    x: 0.8, y: 2.5, w: 8.4, h: 0.6, fontSize: 18, fontFace: FONT.body, color: C.iceBlue,
  });

  const details = [];
  if (engagement.client) details.push(`Client: ${engagement.client}`);
  if (engagement.date) details.push(`Date: ${engagement.date}`);
  details.push(`Panel: ${nRespondents(conceptIds[0])} synthetic respondents`);
  details.push(`Concepts tested: ${conceptIds.length}`);

  slide.addText(details.join("   |   "), {
    x: 0.8, y: 3.6, w: 8.4, h: 0.5, fontSize: 11, fontFace: FONT.body, color: C.iceBlue,
  });
}

// --- Slide 2: Study Overview ---
function buildOverviewSlide(pres, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText("Study Overview", {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  // Concepts tested
  const conceptLines = conceptIds.map((cid, i) => {
    const c = results.concepts[cid]?.concept || {};
    return { text: `${i + 1}. ${c.name || cid}`, options: { breakLine: true, fontSize: 13, fontFace: FONT.body, color: C.darkText, bold: true } };
  });

  // Interleave descriptions
  const conceptContent = [];
  conceptIds.forEach((cid, i) => {
    const c = results.concepts[cid]?.concept || {};
    conceptContent.push({ text: `${c.name || cid}`, options: { breakLine: true, fontSize: 13, fontFace: FONT.body, color: C.darkText, bold: true } });
    if (c.description) {
      conceptContent.push({ text: truncate(c.description, 120), options: { breakLine: true, fontSize: 11, fontFace: FONT.body, color: C.mutedText, paraSpaceAfter: 8 } });
    }
  });

  // Left column: Concepts
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.2, w: 4.5, h: 3.8, fill: { color: C.white }, shadow: makeShadow() });
  slide.addText("CONCEPTS TESTED", { x: 0.7, y: 1.35, w: 4.1, h: 0.4, fontSize: 10, fontFace: FONT.body, color: C.mutedText, bold: true, margin: 0 });
  slide.addText(conceptContent, { x: 0.7, y: 1.75, w: 4.1, h: 3.0, fontSize: 12, fontFace: FONT.body, color: C.darkText, valign: "top", margin: 0 });

  // Right column: Panel demographics
  const panelSummary = results.concepts[conceptIds[0]]?.panel_summary || personas.panel_summary || {};
  const demoLines = [];
  demoLines.push({ text: `${panelSummary.panel_size || "—"} respondents`, options: { breakLine: true, fontSize: 13, bold: true, color: C.darkText } });
  demoLines.push({ text: `Ages ${panelSummary.age_min || "—"} – ${panelSummary.age_max || "—"} (mean ${panelSummary.age_mean || "—"})`, options: { breakLine: true, fontSize: 11, color: C.mutedText, paraSpaceAfter: 4 } });

  if (panelSummary.gender) {
    const g = Object.entries(panelSummary.gender).map(([k, v]) => `${v} ${k}`).join(", ");
    demoLines.push({ text: `Gender: ${g}`, options: { breakLine: true, fontSize: 11, color: C.mutedText } });
  }
  if (panelSummary.region) {
    const r = Object.entries(panelSummary.region).map(([k, v]) => `${k}: ${v}`).join(", ");
    demoLines.push({ text: `Region: ${r}`, options: { breakLine: true, fontSize: 11, color: C.mutedText } });
  }
  if (panelSummary.income) {
    const inc = Object.entries(panelSummary.income).map(([k, v]) => `${k}: ${v}`).join(", ");
    demoLines.push({ text: `Income: ${inc}`, options: { breakLine: true, fontSize: 11, color: C.mutedText } });
  }

  slide.addShape(pres.shapes.RECTANGLE, { x: 5.2, y: 1.2, w: 4.3, h: 3.8, fill: { color: C.white }, shadow: makeShadow() });
  slide.addText("PANEL DEMOGRAPHICS", { x: 5.4, y: 1.35, w: 3.9, h: 0.4, fontSize: 10, fontFace: FONT.body, color: C.mutedText, bold: true, margin: 0 });
  slide.addText(demoLines, { x: 5.4, y: 1.75, w: 3.9, h: 3.0, fontFace: FONT.body, valign: "top", margin: 0 });
}

// --- Slide 3: Concept Ranking ---
function buildRankingSlide(pres, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText("Concept Ranking", {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  slide.addText("Ranked by Top-2-Box (% rating 4 or 5) — the share of the panel leaning toward purchase.", {
    x: 0.5, y: 0.9, w: 9, h: 0.4, fontSize: 11, fontFace: FONT.body, color: C.mutedText, margin: 0,
  });

  // Sort concepts by top2box descending (winner first)
  const ranked = [...conceptIds].sort((a, b) => top2Box(b) - top2Box(a));

  // Bar chart: horizontal bars render bottom-up, so reverse for display
  const chartRanked = [...ranked].reverse();
  const chartLabels = chartRanked.map(cid => conceptName(cid));
  const chartValues = chartRanked.map(cid => parseFloat(top2Box(cid).toFixed(1)));

  const chartColors = [C.chart1, C.chart2, C.chart3, C.chart4, C.chart5].slice(0, ranked.length).reverse();

  slide.addChart(pres.charts.BAR, [{ name: "Top-2-Box %", labels: chartLabels, values: chartValues }], {
    x: 0.5, y: 1.5, w: 5.5, h: 3.5,
    barDir: "bar",
    chartColors: chartColors,
    chartArea: { fill: { color: C.white }, roundedCorners: true },
    catAxisLabelColor: C.darkText,
    catAxisLabelFontSize: 11,
    valAxisLabelColor: C.mutedText,
    valAxisLabelFontSize: 9,
    valGridLine: { color: "E2E8F0", size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: C.darkText,
    dataLabelFontSize: 11,
    showLegend: false,
    valAxisMaxVal: 100,
    valAxisTitle: "Top-2-Box %",
    valAxisTitleColor: C.mutedText,
    valAxisTitleFontSize: 9,
  });

  // Summary cards on the right
  ranked.forEach((cid, i) => {
    const cardY = 1.5 + i * 1.6;
    if (cardY + 1.3 > 5.2) return; // don't overflow

    slide.addShape(pres.shapes.RECTANGLE, { x: 6.3, y: cardY, w: 3.3, h: 1.35, fill: { color: C.white }, shadow: makeShadow() });

    // Accent bar on left
    slide.addShape(pres.shapes.RECTANGLE, { x: 6.3, y: cardY, w: 0.06, h: 1.35, fill: { color: chartColors[i] || C.navy } });

    const ratio = posNegRatio(cid);
    slide.addText([
      { text: conceptName(cid), options: { breakLine: true, fontSize: 11, bold: true, color: C.darkText } },
      { text: `Top-2-Box: ${pctStr(top2Box(cid))}`, options: { breakLine: true, fontSize: 10, color: C.mutedText } },
      { text: `Pos:Neg ratio: ${ratio.toFixed(1)}:1`, options: { breakLine: true, fontSize: 10, color: C.mutedText } },
      { text: `Mean PI: ${meanPI(cid).toFixed(2)}`, options: { fontSize: 10, color: C.mutedText } },
    ], { x: 6.55, y: cardY + 0.08, w: 2.9, h: 1.2, fontFace: FONT.body, valign: "top", margin: 0 });
  });
}

// --- Per-concept: Distribution slide ---
function buildDistributionSlide(pres, cid, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText(conceptName(cid), {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  slide.addText("Purchase Intent Distribution", {
    x: 0.5, y: 0.9, w: 9, h: 0.35, fontSize: 12, fontFace: FONT.body, color: C.mutedText, margin: 0,
  });

  // Distribution bar chart
  const d = dist(cid);
  const labels = ["1\nDefinitely\nnot", "2\nProbably\nnot", "3\nNeutral", "4\nProbably\nyes", "5\nDefinitely\nyes"];
  const values = [1, 2, 3, 4, 5].map(r => parseFloat(((parseFloat(d[String(r)]) || 0) * 100).toFixed(1)));
  const barColors = [C.red, "F87171", C.amber, "34D399", C.green];

  slide.addChart(pres.charts.BAR, [{ name: "% of Panel", labels, values }], {
    x: 0.3, y: 1.4, w: 6.2, h: 3.6,
    barDir: "col",
    chartColors: barColors,
    chartArea: { fill: { color: C.white }, roundedCorners: true },
    catAxisLabelColor: C.darkText,
    catAxisLabelFontSize: 9,
    valAxisLabelColor: C.mutedText,
    valAxisLabelFontSize: 9,
    valGridLine: { color: "E2E8F0", size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: C.darkText,
    dataLabelFontSize: 10,
    showLegend: false,
    valAxisMaxVal: Math.min(100, Math.ceil(Math.max(...values) / 10) * 10 + 10),
  });

  // Metric cards on right
  const metrics = [
    { label: "TOP-2-BOX", value: pctStr(top2Box(cid)), color: C.green },
    { label: "BOTTOM-2-BOX", value: pctStr(bot2Box(cid)), color: C.red },
    { label: "POS:NEG RATIO", value: `${posNegRatio(cid).toFixed(1)}:1`, color: C.navy },
    { label: "MEAN PI", value: meanPI(cid).toFixed(2), color: C.mutedText },
  ];

  metrics.forEach((m, i) => {
    const cardY = 1.4 + i * 0.85;
    slide.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: cardY, w: 2.8, h: 0.72, fill: { color: C.white }, shadow: makeShadow() });
    slide.addText(m.label, { x: 6.95, y: cardY + 0.06, w: 2.5, h: 0.22, fontSize: 8, fontFace: FONT.body, color: C.mutedText, bold: true, margin: 0 });
    slide.addText(m.value, { x: 6.95, y: cardY + 0.25, w: 2.5, h: 0.38, fontSize: 22, fontFace: FONT.head, color: m.color, bold: true, margin: 0 });
  });
}

// --- Per-concept: Drivers & Barriers slide ---
function buildDriversSlide(pres, cid, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  const conceptInsights = insights.concepts?.[cid] || {};

  slide.addText(`${conceptName(cid)}: Drivers & Barriers`, {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 24, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  // Left: Drivers
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.15, w: 4.4, h: 4.0, fill: { color: C.white }, shadow: makeShadow() });
  slide.addText("PURCHASE DRIVERS", { x: 0.7, y: 1.25, w: 4.0, h: 0.35, fontSize: 10, fontFace: FONT.body, color: C.green, bold: true, margin: 0 });

  const drivers = (conceptInsights.purchase_drivers || []).slice(0, 3);
  const driverContent = [];
  drivers.forEach((d, i) => {
    driverContent.push({ text: d.theme, options: { breakLine: true, fontSize: 12, bold: true, color: C.darkText, paraSpaceBefore: i > 0 ? 8 : 0 } });
    if (d.detail) {
      driverContent.push({ text: truncate(d.detail, 120), options: { breakLine: true, fontSize: 10, color: C.mutedText, paraSpaceAfter: 1 } });
    }
    if (d.representative_quote) {
      driverContent.push({ text: `"${truncate(d.representative_quote, 100)}"`, options: { breakLine: true, fontSize: 10, italic: true, color: C.mutedText, paraSpaceAfter: 2 } });
    }
  });
  slide.addText(driverContent, { x: 0.7, y: 1.6, w: 4.0, h: 3.4, fontFace: FONT.body, valign: "top", margin: 0 });

  // Right: Barriers
  slide.addShape(pres.shapes.RECTANGLE, { x: 5.1, y: 1.15, w: 4.4, h: 4.0, fill: { color: C.white }, shadow: makeShadow() });
  slide.addText("PAIN POINTS", { x: 5.3, y: 1.25, w: 4.0, h: 0.35, fontSize: 10, fontFace: FONT.body, color: C.red, bold: true, margin: 0 });

  const barriers = (conceptInsights.pain_points || []).slice(0, 3);
  const barrierContent = [];
  barriers.forEach((b, i) => {
    const severity = b.severity === "high" ? " (high)" : b.severity === "medium" ? " (med)" : "";
    barrierContent.push({ text: `${b.theme}${severity}`, options: { breakLine: true, fontSize: 12, bold: true, color: C.darkText, paraSpaceBefore: i > 0 ? 8 : 0 } });
    // Show detail as description (non-italic)
    const desc = b.detail || b.representative_quote || "";
    if (desc) {
      barrierContent.push({ text: truncate(desc, 120), options: { breakLine: true, fontSize: 10, color: C.mutedText, paraSpaceAfter: 1 } });
    }
    // Show frequency if available
    if (b.frequency) {
      barrierContent.push({ text: b.frequency, options: { breakLine: true, fontSize: 9, italic: true, color: C.mutedText, paraSpaceAfter: 2 } });
    }
  });
  slide.addText(barrierContent, { x: 5.3, y: 1.6, w: 4.0, h: 3.4, fontFace: FONT.body, valign: "top", margin: 0 });
}

// --- Per-concept: Consumer Voices slide (curated excerpts) ---
function buildVoicesSlide(pres, cid, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText(`${conceptName(cid)}: Consumer Voices`, {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 24, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  slide.addText("Selected responses from across the sentiment spectrum", {
    x: 0.5, y: 0.9, w: 9, h: 0.3, fontSize: 11, fontFace: FONT.body, color: C.mutedText, margin: 0,
  });

  const excerpts = pickExcerpts(cid, 3);
  const sentimentLabels = ["Skeptical", "On the fence", "Interested"];
  const sentimentColors = [C.red, C.amber, C.green];

  excerpts.forEach((ex, i) => {
    const cardY = 1.4 + i * 1.3;
    const cardW = 8.8;
    const labelIdx = Math.min(i, sentimentLabels.length - 1);

    slide.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: cardY, w: cardW, h: 1.1, fill: { color: C.white }, shadow: makeShadow() });

    // Accent bar
    slide.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: cardY, w: 0.06, h: 1.1, fill: { color: sentimentColors[labelIdx] } });

    // Sentiment tag
    slide.addText(sentimentLabels[labelIdx].toUpperCase(), {
      x: 0.85, y: cardY + 0.08, w: 1.5, h: 0.25, fontSize: 8, fontFace: FONT.body, color: sentimentColors[labelIdx], bold: true, margin: 0,
    });

    // Quote
    slide.addText(`"${ex.text}"`, {
      x: 0.85, y: cardY + 0.32, w: cardW - 0.6, h: 0.65, fontSize: 11, fontFace: FONT.body, color: C.darkText, italic: true, valign: "top", margin: 0,
    });
  });
}

// --- Comparison slide (only if 2+ concepts) ---
function buildComparisonSlide(pres, pageNum) {
  if (conceptIds.length < 2) return;

  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText("Head-to-Head Comparison", {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  // Grouped bar chart: distribution overlay
  const chartData = conceptIds.map((cid, i) => ({
    name: conceptName(cid),
    labels: ["1 - Definitely not", "2 - Probably not", "3 - Neutral", "4 - Probably yes", "5 - Definitely yes"],
    values: [1, 2, 3, 4, 5].map(r => parseFloat(((parseFloat(dist(cid)[String(r)]) || 0) * 100).toFixed(1))),
  }));

  const chartColors = [C.chart1, C.chart2, C.chart3, C.chart4].slice(0, conceptIds.length);

  slide.addChart(pres.charts.BAR, chartData, {
    x: 0.3, y: 1.1, w: 9.2, h: 4.0,
    barDir: "col",
    barGrouping: "clustered",
    chartColors: chartColors,
    chartArea: { fill: { color: C.white }, roundedCorners: true },
    catAxisLabelColor: C.darkText,
    catAxisLabelFontSize: 9,
    valAxisLabelColor: C.mutedText,
    valAxisLabelFontSize: 9,
    valGridLine: { color: "E2E8F0", size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: C.darkText,
    dataLabelFontSize: 8,
    showLegend: true,
    legendPos: "b",
    legendFontSize: 10,
    legendColor: C.darkText,
  });
}

// --- Recommendations slide ---
function buildRecommendationsSlide(pres, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText("Recommendations", {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  slide.addText("Action items synthesized from panel responses — framed as hypotheses to validate.", {
    x: 0.5, y: 0.9, w: 9, h: 0.3, fontSize: 11, fontFace: FONT.body, color: C.mutedText, margin: 0,
  });

  // Collect all unique recommendations across concepts + top-level
  const allRecs = [];
  const seenActions = new Set();

  // Per-concept recommendations
  conceptIds.forEach(cid => {
    const recs = insights.concepts?.[cid]?.recommendations || [];
    recs.forEach(r => {
      const action = r.action || r.recommendation || r;
      const actionStr = typeof action === "string" ? action : JSON.stringify(action);
      if (!seenActions.has(actionStr)) {
        seenActions.add(actionStr);
        allRecs.push({
          action: actionStr,
          rationale: r.rationale || r.detail || "",
          priority: r.priority || "medium",
        });
      }
    });
  });

  // Top-level recommended_actions (new format)
  if (insights.recommended_actions && allRecs.length === 0) {
    insights.recommended_actions.forEach(r => {
      const action = r.action || r.recommendation || (typeof r === "string" ? r : "");
      const actionStr = typeof action === "string" ? action : JSON.stringify(action);
      if (actionStr && !seenActions.has(actionStr)) {
        seenActions.add(actionStr);
        allRecs.push({
          action: actionStr,
          rationale: r.rationale || r.detail || "",
          evidence: r.evidence || "",
          expected_impact: r.expected_impact || "",
          priority: r.priority || "medium",
        });
      }
    });
  }

  // Sort: high priority first
  allRecs.sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return (order[a.priority] ?? 2) - (order[b.priority] ?? 2);
  });

  const display = allRecs.slice(0, 4);
  display.forEach((rec, i) => {
    const cardY = 1.4 + i * 0.95;
    const prioColor = rec.priority === "high" ? C.red : rec.priority === "medium" ? C.amber : C.mutedText;

    slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: cardY, w: 9.0, h: 0.82, fill: { color: C.white }, shadow: makeShadow() });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: cardY, w: 0.06, h: 0.82, fill: { color: prioColor } });

    const textContent = [
      { text: rec.action, options: { breakLine: true, fontSize: 11, bold: true, color: C.darkText } },
    ];
    if (rec.evidence) {
      textContent.push({ text: `Evidence: ${truncate(rec.evidence, 110)}`, options: { breakLine: true, fontSize: 9, color: C.mutedText } });
    }
    if (rec.expected_impact) {
      textContent.push({ text: `Expected impact: ${truncate(rec.expected_impact, 110)}`, options: { fontSize: 9, color: C.mutedText } });
    }
    if (!rec.evidence && rec.rationale) {
      textContent.push({ text: truncate(rec.rationale, 120), options: { fontSize: 9, color: C.mutedText } });
    }

    slide.addText(textContent, { x: 0.75, y: cardY + 0.04, w: 7.5, h: 0.74, fontFace: FONT.body, valign: "top", margin: 0 });

    // Priority tag
    slide.addText(rec.priority.toUpperCase(), {
      x: 8.5, y: cardY + 0.2, w: 0.8, h: 0.3, fontSize: 8, fontFace: FONT.body, color: prioColor, bold: true, align: "center", margin: 0,
    });
  });
}

// --- Per-concept: Standout Insights slide ---
function buildStandoutSlide(pres, cid, pageNum) {
  const standoutData = insights.standout_insights?.[cid] || {};
  const allInsights = standoutData.insights || [];
  if (allInsights.length === 0) return pageNum - 1; // skip slide, don't increment

  const slide = pres.addSlide();
  slide.background = { color: C.offWhite };
  addFooter(slide, pageNum);

  slide.addText(`${conceptName(cid)}: Standout Consumer Insights`, {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 24, fontFace: FONT.head, color: C.navy, bold: true, margin: 0,
  });

  slide.addText("Specific suggestions and unique objections extracted from consumer reasoning", {
    x: 0.5, y: 0.9, w: 9, h: 0.3, fontSize: 11, fontFace: FONT.body, color: C.mutedText, margin: 0,
  });

  // Group by theme
  const themes = {};
  allInsights.forEach(ins => {
    const t = ins.theme || "Other";
    if (!themes[t]) themes[t] = [];
    themes[t].push(ins);
  });

  // Render up to 5 insights (across themes), fitting on one slide
  const display = allInsights.slice(0, 5);
  const typeColors = { suggestion: C.green, objection: C.amber };

  display.forEach((ins, i) => {
    const cardY = 1.35 + i * 0.82;
    if (cardY + 0.72 > 5.3) return;

    const accentColor = typeColors[ins.type] || C.accentBar;

    slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: cardY, w: 9.0, h: 0.72, fill: { color: C.white }, shadow: makeShadow() });
    slide.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: cardY, w: 0.06, h: 0.72, fill: { color: accentColor } });

    const content = [
      { text: ins.theme, options: { breakLine: true, fontSize: 10, bold: true, color: C.darkText } },
      { text: `"${truncate(ins.quote || "", 120)}"`, options: { breakLine: true, fontSize: 10, italic: true, color: C.mutedText } },
    ];
    if (ins.why_it_matters) {
      content.push({ text: truncate(ins.why_it_matters, 100), options: { fontSize: 9, color: C.mutedText } });
    }

    slide.addText(content, { x: 0.75, y: cardY + 0.03, w: 7.5, h: 0.66, fontFace: FONT.body, valign: "top", margin: 0 });

    // Type tag
    const typeLabel = (ins.type || "insight").toUpperCase();
    slide.addText(typeLabel, {
      x: 8.4, y: cardY + 0.2, w: 0.9, h: 0.25, fontSize: 7, fontFace: FONT.body, color: accentColor, bold: true, align: "center", margin: 0,
    });
  });

  // If more than 5, note how many more
  if (allInsights.length > 5) {
    slide.addText(`+ ${allInsights.length - 5} more insights available in the full report`, {
      x: 0.5, y: 5.0, w: 9, h: 0.25, fontSize: 9, fontFace: FONT.body, color: C.mutedText, italic: true, margin: 0,
    });
  }

  return pageNum;
}

// --- Methodology appendix slide ---
function buildMethodologySlide(pres, pageNum) {
  const slide = pres.addSlide();
  slide.background = { color: C.navy };

  slide.addText("Methodology", {
    x: 0.5, y: 0.3, w: 9, h: 0.7, fontSize: 28, fontFace: FONT.head, color: C.white, bold: true, margin: 0,
  });

  const methodText = [
    { text: "This study used Semantic Similarity Rating (SSR), a validated method for generating synthetic consumer survey data using large language models.", options: { breakLine: true, fontSize: 12, color: C.iceBlue, paraSpaceAfter: 12 } },
    { text: "How it works:", options: { breakLine: true, fontSize: 12, color: C.white, bold: true, paraSpaceAfter: 4 } },
    { text: "1.  AI personas are created with realistic demographic and lifestyle profiles matching the target consumer.", options: { breakLine: true, fontSize: 11, color: C.iceBlue, paraSpaceAfter: 2 } },
    { text: "2.  Each persona views the product concept and responds freely to purchase intent questions — no forced scale.", options: { breakLine: true, fontSize: 11, color: C.iceBlue, paraSpaceAfter: 2 } },
    { text: "3.  Responses are scored against calibrated reference statements using semantic similarity, producing a Likert distribution.", options: { breakLine: true, fontSize: 11, color: C.iceBlue, paraSpaceAfter: 2 } },
    { text: "4.  Results are aggregated across the panel to produce distributional metrics and qualitative insights.", options: { breakLine: true, fontSize: 11, color: C.iceBlue, paraSpaceAfter: 12 } },
    { text: "Validation:", options: { breakLine: true, fontSize: 12, color: C.white, bold: true, paraSpaceAfter: 4 } },
    { text: "SSR achieves ~90% of human test–retest reliability for concept ranking (Maier et al., 2025). Concept rankings are more reliable than absolute scores. Results should be treated as directional hypotheses to validate with real consumers.", options: { breakLine: true, fontSize: 11, color: C.iceBlue, paraSpaceAfter: 12 } },
  ];

  slide.addText(methodText, { x: 0.7, y: 1.1, w: 8.6, h: 4.0, fontFace: FONT.body, valign: "top", margin: 0 });

  // Config details
  const configStr = `Model: ${pipelineConfig.llm_model || "—"}  |  Panel: ${nRespondents(conceptIds[0])} respondents  |  Samples/persona: ${pipelineConfig.samples_per_persona || "—"}`;
  slide.addText(configStr, {
    x: 0.7, y: 5.0, w: 8.6, h: 0.35, fontSize: 9, fontFace: FONT.body, color: C.mutedText,
  });
}

// ---------------------------------------------------------------------------
// Build the deck
// ---------------------------------------------------------------------------
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "SSR Toolkit";
pres.title = engagement.engagement || "SSR Report";

let page = 0;

// 1. Title
buildTitleSlide(pres);
page++;

// 2. Overview
buildOverviewSlide(pres, ++page);

// 3. Ranking
buildRankingSlide(pres, ++page);

// 4-6. Per concept: distribution, drivers, voices, standout insights
conceptIds.forEach(cid => {
  buildDistributionSlide(pres, cid, ++page);
  buildDriversSlide(pres, cid, ++page);
  buildVoicesSlide(pres, cid, ++page);
  // Standout insights (only added if data exists)
  const prevPage = page;
  page = buildStandoutSlide(pres, cid, ++page);
});

// 7. Comparison (if 2+ concepts)
if (conceptIds.length >= 2) {
  buildComparisonSlide(pres, ++page);
}

// 8. Recommendations
buildRecommendationsSlide(pres, ++page);

// 9. Methodology
buildMethodologySlide(pres, ++page);

// Write
pres.writeFile({ fileName: outputPath }).then(() => {
  console.log(`✓ Report saved: ${outputPath} (${page} slides)`);
}).catch(err => {
  console.error("Error generating PPTX:", err);
  process.exit(1);
});