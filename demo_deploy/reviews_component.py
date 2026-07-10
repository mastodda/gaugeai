"""
reviews_component.py — Renders the Reviews Explorer as an HTML component.

Accepts merged respondent data (results.json joined with personas.json)
and returns an HTML string suitable for st.components.v1.html().

Usage in Streamlit:
    from reviews_component import render_reviews_html
    import streamlit.components.v1 as components

    html = render_reviews_html(results, personas)
    components.html(html, height=900, scrolling=True)
"""

import json


def merge_results_and_personas(results: dict, personas: dict) -> dict:
    """
    Join respondent-level results with persona demographics.

    Returns a dict structured for the React component:
    {
        "meta": { ... },
        "concepts": {
            "concept_id": {
                "concept": { "concept_id": ..., "name": ... },
                "respondents": [ { ...respondent fields + persona fields... } ],
                "aggregate": { ... computed from respondents ... }
            }
        }
    }
    """
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}

    meta_raw = results.get("meta", {})
    engagement = meta_raw.get("engagement", {})
    config = meta_raw.get("pipeline_config", {})

    meta = {
        "engagement": engagement.get("engagement", "Unnamed"),
        "client": engagement.get("client", ""),
        "panel_size": len(personas["personas"]),
        "llm_model": config.get("llm_model", "unknown"),
        "timestamp": meta_raw.get("timestamp", ""),
    }

    concepts = {}
    for concept_id, concept_data in results["concepts"].items():
        concept_info = concept_data["concept"]
        raw_respondents = concept_data["respondents"]

        merged_respondents = []
        for resp in raw_respondents:
            persona = persona_lookup.get(resp["persona_id"], {})
            pmf = resp["averaged_pmf"]

            # Compute top2box and bottom2box from PMF
            p4 = float(pmf.get("4", 0))
            p5 = float(pmf.get("5", 0))
            p1 = float(pmf.get("1", 0))
            p2 = float(pmf.get("2", 0))
            top2 = p4 + p5
            bot2 = p1 + p2

            merged_respondents.append({
                "persona_id": resp["persona_id"],
                "free_text_response": resp["free_text_response"],
                "reasoning_response": resp.get("reasoning_response", ""),
                "expected_rating": resp["expected_rating"],
                "mode_rating": resp["mode_rating"],
                "top2box": round(top2, 4),
                "bottom2box": round(bot2, 4),
                "age": persona.get("age"),
                "gender": persona.get("gender"),
                "region": persona.get("region"),
                "income": persona.get("income"),
            })

        # Compute aggregate from actual respondent data
        n = len(merged_respondents)
        if n > 0:
            ratings = [r["expected_rating"] for r in merged_respondents]
            mean_pi = sum(ratings) / n
            std_pi = (sum((x - mean_pi) ** 2 for x in ratings) / n) ** 0.5
            avg_top2 = sum(r["top2box"] for r in merged_respondents) / n
            avg_bot2 = sum(r["bottom2box"] for r in merged_respondents) / n
            pos_neg_ratio = avg_top2 / avg_bot2 if avg_bot2 > 0 else float("inf")

            # Use aggregate from pipeline if available, compute if not
            agg = concept_data.get("aggregate", {})
            aggregate = {
                "distribution": agg.get("distribution", {}),
                "mean_pi": round(mean_pi, 4),
                "std_pi": round(std_pi, 4),
                "top_2_box": round(avg_top2, 4),
                "positive_negative_ratio": round(pos_neg_ratio, 2),
            }
        else:
            aggregate = {
                "distribution": {},
                "mean_pi": 0,
                "std_pi": 0,
                "top_2_box": 0,
                "positive_negative_ratio": 0,
            }

        concepts[concept_id] = {
            "concept": {
                "concept_id": concept_id,
                "name": concept_info.get("name", concept_id),
            },
            "respondents": merged_respondents,
            "aggregate": aggregate,
        }

    return {"meta": meta, "concepts": concepts}


def render_reviews_html(results: dict, personas: dict, height: int = 2400) -> str:
    """
    Generate a self-contained HTML string with the Reviews Explorer React app.

    The real pipeline data is injected as a JSON blob that the React component reads.
    """
    merged = merge_results_and_personas(results, personas)
    data_json = json.dumps(merged)

    # Escape for embedding in JS template literal
    data_json_escaped = data_json.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600;6..72,700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'DM Sans', system-ui, sans-serif; background: #f5f2ed; }}
</style>
</head>
<body>
<div id="root"></div>
<script>
// ── Injected pipeline data ─────────────────────────────────────────
const PIPELINE_DATA = JSON.parse(`{data_json_escaped}`);

// ── React aliases ──────────────────────────────────────────────────
const {{ useState, useMemo, useCallback }} = React;
const e = React.createElement;

// ── Sentiment bands ────────────────────────────────────────────────
const SENTIMENT_BANDS = [
  {{ key: "strong",   label: "Strong intent",   rangeLabel: "4.0–5.0", color: "#067D62", range: [4.0, 5.01] }},
  {{ key: "leaning",  label: "Leaning positive", rangeLabel: "3.5–4.0", color: "#2E8B57", range: [3.5, 4.0] }},
  {{ key: "neutral",  label: "Neutral",          rangeLabel: "2.8–3.5", color: "#946800", range: [2.8, 3.5] }},
  {{ key: "soft_neg", label: "Leaning negative", rangeLabel: "2.2–2.8", color: "#C05621", range: [2.2, 2.8] }},
  {{ key: "low",      label: "Low intent",       rangeLabel: "< 2.2",   color: "#B12704", range: [0, 2.2] }},
];

function sentimentBucket(r) {{
  for (const b of SENTIMENT_BANDS) if (r >= b.range[0] && r < b.range[1]) return b.key;
  return "neutral";
}}
function getBand(key) {{ return SENTIMENT_BANDS.find(b => b.key === key); }}

// ── Stars SVG ──────────────────────────────────────────────────────
function Stars({{ rating, size }}) {{
  size = size || 18;
  const full = Math.floor(rating);
  const partial = rating - full;
  const empty = 5 - full - (partial > 0 ? 1 : 0);
  const starPath = "10,1.5 12.6,7.1 18.8,7.6 14,11.8 15.4,17.9 10,14.7 4.6,17.9 6,11.8 1.2,7.6 7.4,7.1";

  const children = [];
  for (let i = 0; i < full; i++)
    children.push(e("svg", {{ key: "f"+i, width: size, height: size, viewBox: "0 0 20 20" }},
      e("polygon", {{ points: starPath, fill: "#DE7921" }})));

  if (partial > 0) {{
    const pct = Math.round(partial * 100);
    children.push(e("svg", {{ key: "p", width: size, height: size, viewBox: "0 0 20 20" }},
      e("defs", null, e("linearGradient", {{ id: "sg"+pct }},
        e("stop", {{ offset: pct+"%", stopColor: "#DE7921" }}),
        e("stop", {{ offset: pct+"%", stopColor: "#D5D5D5" }}))),
      e("polygon", {{ points: starPath, fill: "url(#sg"+pct+")" }})));
  }}

  for (let i = 0; i < empty; i++)
    children.push(e("svg", {{ key: "e"+i, width: size, height: size, viewBox: "0 0 20 20" }},
      e("polygon", {{ points: starPath, fill: "#D5D5D5" }})));

  return e("span", {{ style: {{ display: "inline-flex", gap: 1, verticalAlign: "middle" }} }}, ...children);
}}

// ── Badge ──────────────────────────────────────────────────────────
function Badge({{ children, active, onClick }}) {{
  return e("button", {{
    onClick,
    style: {{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "4px 12px", borderRadius: 16,
      border: active ? "1.5px solid #1a3a4a" : "1px solid #ccc",
      background: active ? "#1a3a4a" : "white",
      color: active ? "white" : "#444",
      fontSize: 12, cursor: "pointer", transition: "all 0.15s ease",
      fontWeight: active ? 600 : 400, fontFamily: "'DM Sans', system-ui, sans-serif",
    }}
  }}, children, active ? e("span", {{ style: {{ marginLeft: 2, fontSize: 10 }} }}, "✕") : null);
}}

// ── Concept Summary ────────────────────────────────────────────────
function ConceptSummary({{ concept, aggregate, respondents, ratingFilter, onRatingFilter }}) {{
  const dist = useMemo(() => {{
    const counts = {{}};
    SENTIMENT_BANDS.forEach(b => {{ counts[b.key] = 0; }});
    respondents.forEach(r => {{ counts[sentimentBucket(r.expected_rating)]++; }});
    const total = respondents.length || 1;
    return Object.fromEntries(Object.entries(counts).map(([k, v]) => [k, v / total]));
  }}, [respondents]);

  const summaryText = useMemo(() => {{
    const top2 = aggregate.top_2_box;
    const ratio = aggregate.positive_negative_ratio;
    if (top2 > 0.55) return "Strong positive reception. " + Math.round(top2*100) + "% of panelists rated favorably (4-5), with a " + ratio.toFixed(1) + ":1 positive-to-negative ratio.";
    if (top2 > 0.45) return "Moderately positive reception. " + Math.round(top2*100) + "% rated favorably with a " + ratio.toFixed(1) + ":1 positive-to-negative ratio. The concept resonated with a slight majority.";
    return "Mixed reception. Only " + Math.round(top2*100) + "% rated favorably. The " + ratio.toFixed(1) + ":1 positive-to-negative ratio suggests the concept needs refinement.";
  }}, [aggregate]);

  return e("div", {{ style: {{ background: "white", borderRadius: 8, padding: 24, border: "1px solid #e0e0e0" }} }},
    e("h3", {{ style: {{ fontSize: 18, fontWeight: 700, margin: "0 0 4px", fontFamily: "'Newsreader', Georgia, serif", color: "#0f1111" }} }}, concept.name),
    e("div", {{ style: {{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }} }},
      e(Stars, {{ rating: aggregate.mean_pi, size: 20 }}),
      e("span", {{ style: {{ fontSize: 14, color: "#565656" }} }}, aggregate.mean_pi.toFixed(2) + " out of 5"),
      e("span", {{ style: {{ color: "#ccc" }} }}, "|"),
      e("span", {{ style: {{ fontSize: 14, color: "#565656" }} }}, respondents.length + " synthetic responses")),

    // Sentiment bars
    e("div", {{ style: {{ maxWidth: 380, marginBottom: 16 }} }},
      ...SENTIMENT_BANDS.map(band => {{
        const pct = dist[band.key] || 0;
        const isActive = ratingFilter === null ? null : ratingFilter === band.key;
        return e("button", {{
          key: band.key,
          onClick: () => onRatingFilter(ratingFilter === band.key ? null : band.key),
          style: {{ display: "flex", alignItems: "center", gap: 8, width: "100%", background: "none", border: "none", padding: "3px 0", cursor: "pointer", opacity: isActive === null ? 1 : isActive ? 1 : 0.4 }}
        }},
          e("span", {{ style: {{ width: 160, textAlign: "left", whiteSpace: "nowrap", display: "flex", alignItems: "baseline", gap: 4 }} }},
            e("span", {{ style: {{ fontSize: 12, fontWeight: 500, color: band.color }} }}, band.label),
            e("span", {{ style: {{ fontSize: 10, color: "#999", fontWeight: 400 }} }}, band.rangeLabel)),
          e("span", {{ style: {{ flex: 1, height: 16, background: "#e8e8e8", borderRadius: 3, overflow: "hidden" }} }},
            e("span", {{ style: {{ display: "block", height: "100%", borderRadius: 3, width: (pct*100)+"%", background: band.color, opacity: isActive === false ? 0.5 : 0.85, transition: "width 0.3s ease" }} }})),
          e("span", {{ style: {{ fontSize: 12, color: "#565656", width: 36, textAlign: "right" }} }}, Math.round(pct*100)+"%"));
      }})),

    // Key metrics
    e("div", {{ style: {{ display: "flex", gap: 24, marginBottom: 14, flexWrap: "wrap" }} }},
      ...[
        {{ label: "Top 2 Box", value: Math.round(aggregate.top_2_box*100)+"%" }},
        {{ label: "Pos:Neg Ratio", value: aggregate.positive_negative_ratio.toFixed(1)+":1" }},
        {{ label: "Std Dev", value: aggregate.std_pi.toFixed(2) }},
      ].map(m => e("div", {{ key: m.label, style: {{ padding: "6px 14px", background: "#f7f7f7", borderRadius: 6 }} }},
        e("div", {{ style: {{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: 0.5 }} }}, m.label),
        e("div", {{ style: {{ fontSize: 18, fontWeight: 700, color: "#1a3a4a" }} }}, m.value)))),

    // Summary
    e("p", {{ style: {{ fontSize: 14, color: "#444", lineHeight: 1.55, margin: 0, borderLeft: "3px solid #DE7921", paddingLeft: 12 }} }}, summaryText));
}}

// ── Review Card ────────────────────────────────────────────────────
function ReviewCard({{ respondent, isExpanded, onToggle, showReasoning, onToggleReasoning }}) {{
  const rating = respondent.expected_rating;
  const band = getBand(sentimentBucket(rating));
  const ageBand = respondent.age < 30 ? "18-29" : respondent.age < 45 ? "30-44" : respondent.age < 60 ? "45-59" : "60+";
  const hasReasoning = !!respondent.reasoning_response;

  return e("div", {{ style: {{ borderBottom: "1px solid #eee", padding: "16px 0" }} }},
    // Header
    e("div", {{ style: {{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 6 }} }},
      e("div", null,
        e("div", {{ style: {{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }} }},
          e("div", {{ style: {{
            width: 28, height: 28, borderRadius: 14,
            background: "hsl(" + ((respondent.persona_id.charCodeAt(respondent.persona_id.length-1)*47)%360) + ", 35%, 70%)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, fontWeight: 700, color: "white",
          }} }}, respondent.persona_id.slice(-4)),
          e("span", {{ style: {{ fontSize: 13, color: "#565656" }} }},
            respondent.gender + ", " + ageBand + ", " + respondent.region + (respondent.income ? " · " + respondent.income : ""))),
        e("div", {{ style: {{ display: "flex", alignItems: "center", gap: 8 }} }},
          e(Stars, {{ rating, size: 15 }}),
          e("span", {{ style: {{ fontSize: 14, fontWeight: 600, color: "#0f1111", fontFamily: "'Newsreader', Georgia, serif" }} }}, band.label))),
      e("span", {{ style: {{
        fontSize: 11, padding: "3px 8px", borderRadius: 4,
        background: band.color + "14", color: band.color,
        fontWeight: 600, whiteSpace: "nowrap",
      }} }}, "PI: " + rating.toFixed(2))),

    // Response text
    e("p", {{
      onClick: onToggle,
      style: {{
        fontSize: 14, lineHeight: 1.6, color: "#333", margin: "4px 0 0", cursor: "pointer",
        overflow: isExpanded ? "visible" : "hidden",
        display: isExpanded ? "block" : "-webkit-box",
        WebkitLineClamp: isExpanded ? undefined : 3,
        WebkitBoxOrient: "vertical",
      }}
    }}, "\\u201c" + respondent.free_text_response + "\\u201d"),

    !isExpanded && respondent.free_text_response.length > 180
      ? e("button", {{ onClick: onToggle, style: {{ background: "none", border: "none", padding: 0, color: "#0066c0", fontSize: 13, cursor: "pointer" }} }}, "Read more")
      : null,

    // Reasoning section
    hasReasoning ? e("div", {{ style: {{ marginTop: 8 }} }},
      e("button", {{
        onClick: onToggleReasoning,
        style: {{
          background: "none", border: "none", padding: 0,
          color: "#0066c0", fontSize: 13, cursor: "pointer",
          display: "flex", alignItems: "center", gap: 4,
        }}
      }},
        e("span", {{ style: {{ fontSize: 10, transform: showReasoning ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.15s", display: "inline-block" }} }}, "▶"),
        "Why they feel this way"),
      showReasoning ? e("div", {{ style: {{
        marginTop: 6, padding: "10px 14px",
        background: "#f9f7f4", borderRadius: 6,
        borderLeft: "3px solid " + band.color,
        fontSize: 13, lineHeight: 1.6, color: "#444",
      }} }}, respondent.reasoning_response) : null
    ) : null);
}}

// ── Main App ───────────────────────────────────────────────────────
function ReviewsExplorer() {{
  const data = PIPELINE_DATA;
  const conceptKeys = Object.keys(data.concepts);
  const [selectedConcept, setSelectedConcept] = useState(conceptKeys[0]);
  const [ratingFilter, setRatingFilter] = useState(null);
  const [sortBy, setSortBy] = useState("rating_desc");
  const [genderFilter, setGenderFilter] = useState(null);
  const [ageFilter, setAgeFilter] = useState(null);
  const [regionFilter, setRegionFilter] = useState(null);
  const [incomeFilter, setIncomeFilter] = useState(null);
  const [expandedCards, setExpandedCards] = useState({{}});
  const [reasoningCards, setReasoningCards] = useState({{}});
  const [searchText, setSearchText] = useState("");

  const conceptData = data.concepts[selectedConcept];
  const respondents = conceptData.respondents;

  const filteredRespondents = useMemo(() => {{
    let list = [...respondents];
    if (ratingFilter !== null) list = list.filter(r => sentimentBucket(r.expected_rating) === ratingFilter);
    if (genderFilter) list = list.filter(r => r.gender === genderFilter);
    if (ageFilter) {{
      const [lo, hi] = ageFilter === "18-29" ? [18,29] : ageFilter === "30-44" ? [30,44] : ageFilter === "45-59" ? [45,59] : [60,100];
      list = list.filter(r => r.age >= lo && r.age <= hi);
    }}
    if (regionFilter) list = list.filter(r => r.region === regionFilter);
    if (incomeFilter) list = list.filter(r => r.income === incomeFilter);
    if (searchText) {{
      const q = searchText.toLowerCase();
      list = list.filter(r =>
        (r.free_text_response || "").toLowerCase().includes(q) ||
        (r.reasoning_response || "").toLowerCase().includes(q));
    }}
    if (sortBy === "rating_desc") list.sort((a,b) => b.expected_rating - a.expected_rating);
    else if (sortBy === "rating_asc") list.sort((a,b) => a.expected_rating - b.expected_rating);
    return list;
  }}, [respondents, ratingFilter, genderFilter, ageFilter, regionFilter, incomeFilter, searchText, sortBy]);

  const toggleCard = useCallback(id => setExpandedCards(prev => ({{ ...prev, [id]: !prev[id] }})), []);
  const toggleReasoning = useCallback(id => setReasoningCards(prev => ({{ ...prev, [id]: !prev[id] }})), []);

  const clearAllFilters = () => {{
    setRatingFilter(null); setGenderFilter(null); setAgeFilter(null);
    setRegionFilter(null); setIncomeFilter(null); setSearchText("");
  }};
  const hasFilters = ratingFilter !== null || genderFilter || ageFilter || regionFilter || incomeFilter || searchText;

  const uniqueGenders = [...new Set(respondents.map(r => r.gender))].sort();
  const ageBands = ["18-29", "30-44", "45-59", "60+"];
  const uniqueRegions = [...new Set(respondents.map(r => r.region))].sort();
  const uniqueIncomes = [...new Set(respondents.map(r => r.income).filter(Boolean))];

  return e("div", {{ style: {{ minHeight: "100vh", background: "#f5f2ed" }} }},

    // Header
    e("div", {{ style: {{ background: "#1a3a4a", padding: "14px 20px" }} }},
      e("h1", {{ style: {{ fontSize: 18, fontWeight: 700, color: "white", margin: 0, fontFamily: "'Newsreader', Georgia, serif" }} }}, "Synthetic Panel Reviews"),
      e("p", {{ style: {{ fontSize: 12, color: "#9dc1d3", margin: "2px 0 0" }} }},
        data.meta.engagement + " · " + data.meta.panel_size + " respondents · " + data.meta.llm_model)),

    // Concept tabs
    e("div", {{ style: {{ display: "flex", gap: 0, padding: "0 20px", background: "#1a3a4a", borderBottom: "3px solid #DE7921" }} }},
      ...conceptKeys.map(cid => e("button", {{
        key: cid,
        onClick: () => {{ setSelectedConcept(cid); clearAllFilters(); }},
        style: {{
          padding: "8px 16px", background: selectedConcept === cid ? "#DE7921" : "transparent",
          border: "none", color: selectedConcept === cid ? "white" : "#9dc1d3",
          fontSize: 13, fontWeight: selectedConcept === cid ? 700 : 400,
          cursor: "pointer", borderRadius: "6px 6px 0 0", transition: "all 0.15s ease",
        }}
      }}, data.concepts[cid].concept.name))),

    // Content
    e("div", {{ style: {{ maxWidth: 860, margin: "0 auto", padding: "16px 20px 40px" }} }},

      // Summary
      e(ConceptSummary, {{
        concept: conceptData.concept, aggregate: conceptData.aggregate,
        respondents, ratingFilter, onRatingFilter: setRatingFilter,
      }}),

      // Filters
      e("div", {{ style: {{ marginTop: 16, padding: "14px 16px", background: "white", borderRadius: 8, border: "1px solid #e0e0e0" }} }},
        e("div", {{ style: {{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }} }},
          e("span", {{ style: {{ fontSize: 14, fontWeight: 600, color: "#0f1111", fontFamily: "'Newsreader', Georgia, serif" }} }}, "Filter responses"),
          e("div", {{ style: {{ display: "flex", alignItems: "center", gap: 12 }} }},
            hasFilters ? e("button", {{ onClick: clearAllFilters, style: {{ background: "none", border: "none", padding: 0, color: "#0066c0", fontSize: 12, cursor: "pointer" }} }}, "Clear all") : null,
            e("select", {{
              value: sortBy, onChange: ev => setSortBy(ev.target.value),
              style: {{ padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", fontSize: 12, background: "white" }}
            }}, e("option", {{ value: "rating_desc" }}, "Highest rated"), e("option", {{ value: "rating_asc" }}, "Lowest rated")))),

        // Search
        e("div", {{ style: {{ marginBottom: 8 }} }},
          e("input", {{
            type: "text", placeholder: "Search responses...", value: searchText,
            onChange: ev => setSearchText(ev.target.value),
            style: {{ width: "100%", padding: "6px 10px", borderRadius: 4, border: "1px solid #ccc", fontSize: 13, background: "white" }}
          }})),

        // Filter rows
        e("div", {{ style: {{ display: "flex", flexDirection: "column", gap: 6 }} }},
          e("div", {{ style: {{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }} }},
            e("span", {{ style: {{ fontSize: 11, color: "#888", width: 52, textTransform: "uppercase", letterSpacing: 0.5 }} }}, "Gender"),
            ...uniqueGenders.map(g => e(Badge, {{ key: g, active: genderFilter === g, onClick: () => setGenderFilter(genderFilter === g ? null : g) }}, g))),
          e("div", {{ style: {{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }} }},
            e("span", {{ style: {{ fontSize: 11, color: "#888", width: 52, textTransform: "uppercase", letterSpacing: 0.5 }} }}, "Age"),
            ...ageBands.map(a => e(Badge, {{ key: a, active: ageFilter === a, onClick: () => setAgeFilter(ageFilter === a ? null : a) }}, a))),
          e("div", {{ style: {{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }} }},
            e("span", {{ style: {{ fontSize: 11, color: "#888", width: 52, textTransform: "uppercase", letterSpacing: 0.5 }} }}, "Region"),
            ...uniqueRegions.map(r => e(Badge, {{ key: r, active: regionFilter === r, onClick: () => setRegionFilter(regionFilter === r ? null : r) }}, r))),
          uniqueIncomes.length > 0 ? e("div", {{ style: {{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }} }},
            e("span", {{ style: {{ fontSize: 11, color: "#888", width: 52, textTransform: "uppercase", letterSpacing: 0.5 }} }}, "Income"),
            ...uniqueIncomes.map(inc => e(Badge, {{ key: inc, active: incomeFilter === inc, onClick: () => setIncomeFilter(incomeFilter === inc ? null : inc) }}, inc))) : null)),

      // Results count
      e("div", {{ style: {{ marginTop: 12, marginBottom: 4, fontSize: 13, color: "#565656" }} }},
        "Showing " + filteredRespondents.length + " of " + respondents.length + " responses" + (hasFilters ? " (filtered)" : "")),

      // Review cards
      e("div", {{ style: {{ background: "white", borderRadius: 8, border: "1px solid #e0e0e0", padding: "4px 16px" }} }},
        filteredRespondents.length === 0
          ? e("div", {{ style: {{ padding: "40px 0", textAlign: "center", color: "#888", fontSize: 14 }} }}, "No responses match the current filters.")
          : filteredRespondents.map(r => e(ReviewCard, {{
              key: r.persona_id,
              respondent: r,
              isExpanded: !!expandedCards[r.persona_id],
              onToggle: () => toggleCard(r.persona_id),
              showReasoning: !!reasoningCards[r.persona_id],
              onToggleReasoning: () => toggleReasoning(r.persona_id),
            }})))));
}}

ReactDOM.render(e(ReviewsExplorer), document.getElementById("root"));
</script>
</body>
</html>"""
    return html
