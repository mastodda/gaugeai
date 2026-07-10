"""
app.py — SSR Results Explorer

Streamlit app for interactively exploring SSR pipeline output.
Reads results.json and personas.json from a pipeline run.

Usage:
    streamlit run explorer/app.py -- --data-dir output/run_20260215_143000

    Or use the file picker in the sidebar (defaults to explorer/mock_data).
"""

import json
import argparse
import sys
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components

from reviews_component import render_reviews_html
from report_generator import generate_summary_pdf, generate_responses_pdf


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SSR Results Explorer",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_data(data_dir: str) -> tuple[dict, dict]:
    """Load results.json and personas.json from a run directory."""
    data_path = Path(data_dir).resolve()
    with open(data_path / "results.json") as f:
        results = json.load(f)
    with open(data_path / "personas.json") as f:
        personas = json.load(f)
    return results, personas


@st.cache_data
def load_insights(data_dir: str) -> dict | None:
    """Load insights.json if it exists. Returns None if not available."""
    insights_path = Path(data_dir).resolve() / "insights.json"
    if insights_path.exists():
        with open(insights_path) as f:
            return json.load(f)
    return None


def build_respondent_df(results: dict, personas: dict) -> pd.DataFrame:
    """
    Join respondent-level results with persona demographics into a flat DataFrame.

    One row per (concept, respondent).
    """
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}

    rows = []
    for concept_id, concept_data in results["concepts"].items():
        concept_name = concept_data["concept"].get("name", concept_id)
        for resp in concept_data["respondents"]:
            persona = persona_lookup.get(resp["persona_id"], {})
            pmf = resp["averaged_pmf"]

            rows.append({
                "concept_id": concept_id,
                "concept_name": concept_name,
                "persona_id": resp["persona_id"],
                "free_text": resp["free_text_response"],
                "reasoning": resp.get("reasoning_response", ""),
                "expected_rating": resp["expected_rating"],
                "mode_rating": resp["mode_rating"],
                "p1": pmf.get("1", 0),
                "p2": pmf.get("2", 0),
                "p3": pmf.get("3", 0),
                "p4": pmf.get("4", 0),
                "p5": pmf.get("5", 0),
                "age": persona.get("age"),
                "gender": persona.get("gender"),
                "region": persona.get("region"),
                "income": persona.get("income"),
            })

    df = pd.DataFrame(rows)

    # Derived columns
    df["top2box"] = df["p4"] + df["p5"]
    df["bottom2box"] = df["p1"] + df["p2"]
    df["sentiment"] = pd.cut(
        df["expected_rating"],
        bins=[0, 2.5, 3.5, 5.01],
        labels=["Negative", "Neutral", "Positive"],
    )
    df["age_band"] = _make_age_bands(df["age"])
    return df


def _make_age_bands(ages: pd.Series, max_bands: int = 4) -> pd.Series:
    """Cut ages into bands sized to the actual panel range, not a fixed 18-60+ grid."""
    amin, amax = int(ages.min()), int(ages.max())
    span = amax - amin + 1
    n_bands = min(max_bands, max(1, span // 3))
    width = -(-span // n_bands)  # ceil division
    edges, labels = [amin - 0.5], []
    lo = amin
    while lo <= amax:
        hi = min(lo + width - 1, amax)
        edges.append(hi + 0.5)
        labels.append(f"{lo}" if lo == hi else f"{lo}-{hi}")
        lo = hi + 1
    return pd.cut(ages, bins=edges, labels=labels)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

LIKERT_LABELS = {1: "1 – Very unlikely", 2: "2", 3: "3 – Neutral", 4: "4", 5: "5 – Very likely"}
LIKERT_ORDER = ["1", "2", "3", "4", "5"]

# Unreliable demographic axes per the paper's findings
UNRELIABLE_AXES = {"gender", "region", "ethnicity"}

INCOME_ORDER = ["low", "moderate", "upper-moderate", "high"]


def demographic_chart(
    df: pd.DataFrame,
    demo_col: str,
    concept_col: str = "concept_name",
    sort_order: list[str] | None = None,
) -> alt.Chart:
    """Mean expected rating by demographic segment, grouped by concept."""
    grouped = (
        df.groupby([concept_col, demo_col], observed=True)
        .agg(
            mean_rating=("expected_rating", "mean"),
            count=("expected_rating", "count"),
        )
        .reset_index()
    )

    x_sort = sort_order if sort_order else alt.EncodingSortField(field=demo_col)

    chart = (
        alt.Chart(grouped)
        .mark_bar()
        .encode(
            x=alt.X(f"{demo_col}:N", sort=x_sort, title=demo_col.replace("_", " ").title()),
            y=alt.Y("mean_rating:Q", title="Mean Purchase Intent", scale=alt.Scale(domain=[1, 5])),
            color=alt.Color(f"{concept_col}:N", title="Concept"),
            xOffset=f"{concept_col}:N",
            tooltip=[
                alt.Tooltip(f"{concept_col}:N", title="Concept"),
                alt.Tooltip(f"{demo_col}:N"),
                alt.Tooltip("mean_rating:Q", format=".2f", title="Mean PI"),
                alt.Tooltip("count:Q", title="n"),
            ],
        )
        .properties(height=300)
    )
    return chart


# ---------------------------------------------------------------------------
# Sidebar — data source selection
# ---------------------------------------------------------------------------

st.sidebar.title("📊 SSR Explorer")

# Determine default data dir
# Resolve __file__ to handle Streamlit's path quirks
_app_dir = Path(__file__).resolve().parent
default_dir = _app_dir / "mock_data"
if "--data-dir" in sys.argv:
    idx = sys.argv.index("--data-dir")
    if idx + 1 < len(sys.argv):
        default_dir = Path(sys.argv[idx + 1]).resolve()

data_dir = st.sidebar.text_input(
    "Data directory",
    value=str(default_dir),
    help="Path to directory containing results.json and personas.json",
)

# Validate
data_path = Path(data_dir).resolve()
if not (data_path / "results.json").exists():
    st.error(f"❌ No results.json found in `{data_dir}`")
    st.info("Generate mock data with: `python explorer/generate_mock_data.py`")
    st.stop()
if not (data_path / "personas.json").exists():
    st.error(f"❌ No personas.json found in `{data_dir}`")
    st.stop()

# Load
results, personas = load_data(data_dir)
insights = load_insights(data_dir)
df = build_respondent_df(results, personas)

AGE_BAND_ORDER = [str(c) for c in df["age_band"].cat.categories]
# Only offer demographic axes that actually vary in this panel
DEMO_AXES = [
    ax for ax in ["age_band", "income", "gender", "region"]
    if df[ax].nunique() > 1
] or ["age_band"]

# Sidebar metadata
meta = results.get("meta", {})
engagement = meta.get("engagement", {})
config = meta.get("pipeline_config", {})

st.sidebar.markdown("---")
st.sidebar.markdown(f"**{engagement.get('engagement', 'Unnamed')}**")
st.sidebar.caption(f"Client: {engagement.get('client', '—')}")
st.sidebar.caption(f"Model: {config.get('llm_model', '—')}")
st.sidebar.caption(f"Panel: {len(personas['personas'])} respondents")
st.sidebar.caption(f"Concepts: {len(results['concepts'])}")

# --- PDF exports ---
st.sidebar.markdown("---")
from report_generator import generate_summary_pdf, generate_responses_pdf

# Load insights if available
insights = None
insights_path = Path(data_dir).resolve() / "insights.json"
if insights_path.exists():
    with open(insights_path) as f:
        insights = json.load(f)

st.sidebar.download_button(
    "📄 Download Summary PDF",
    generate_summary_pdf(results, personas, insights),
    "ssr_summary_report.pdf",
    "application/pdf",
)
st.sidebar.download_button(
    "📋 Download All Responses",
    generate_responses_pdf(results, personas),
    "ssr_full_responses.pdf",
    "application/pdf",
)

# --- PPTX export ---

@st.cache_data
def generate_pptx(data_dir_path: str, _insights_exists: bool = False) -> bytes | None:
    """
    Generate a PowerPoint report by calling generate_report_pptx.js.
    Returns the .pptx file bytes, or None on failure.
    """
    import subprocess
    import tempfile

    dp = Path(data_dir_path).resolve()
    results_file = dp / "results.json"
    personas_file = dp / "personas.json"
    insights_file = dp / "insights.json"

    if not results_file.exists() or not personas_file.exists():
        return None

    # Find the generator script — check common locations
    script_candidates = [
        Path(__file__).resolve().parent / "generate_report_pptx.js",
        Path(__file__).resolve().parent.parent / "generate_report_pptx.js",
        dp / "generate_report_pptx.js",
    ]
    script_path = None
    for candidate in script_candidates:
        if candidate.exists():
            script_path = candidate
            break

    if script_path is None:
        return None

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = tmp.name

    cmd = [
        "node", str(script_path),
        "--results", str(results_file),
        "--personas", str(personas_file),
        "--output", tmp_path,
    ]
    if insights_file.exists():
        cmd.extend(["--insights", str(insights_file)])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=str(script_path.parent),  # run from script's directory so node_modules resolves
        )
        if result.stdout:
            print(f"[PPTX] {result.stdout.strip()}")
        if result.stderr:
            print(f"[PPTX stderr] {result.stderr.strip()}")
        if result.returncode == 0 and Path(tmp_path).exists():
            return Path(tmp_path).read_bytes()
        else:
            print(f"[PPTX] Generation failed (rc={result.returncode})")
            return None
    except Exception:
        return None
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


pptx_bytes = generate_pptx(data_dir, _insights_exists=insights is not None)
if pptx_bytes:
    engagement_name = engagement.get("engagement", "report").replace(" ", "_").lower()
    st.sidebar.download_button(
        "📊 Download PowerPoint",
        pptx_bytes,
        f"ssr_{engagement_name}.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
else:
    st.sidebar.caption("⚠️ PPTX export unavailable (missing generate_report_pptx.js or insights.json)")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_insights, tab_compare, tab_demographics, tab_responses, tab_metadata = st.tabs([
    "📈 Overview",
    "💡 Insights",
    "⚖️ Compare",
    "👥 Demographics",
    "💬 Responses",
    "🔧 Metadata",
])


# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------

with tab_overview:

    # ------------------------------------------------------------------
    # Build per-concept metrics for ranking
    # ------------------------------------------------------------------
    concepts = list(results["concepts"].keys())
    concept_metrics = []
    for cid in concepts:
        cdata = results["concepts"][cid]
        agg = cdata["aggregate"]
        dist = agg["distribution"]
        top2 = float(dist.get("4", 0)) + float(dist.get("5", 0))
        bot2 = float(dist.get("1", 0)) + float(dist.get("2", 0))
        mid = float(dist.get("3", 0))
        ratio = top2 / bot2 if bot2 > 0 else float("inf")
        concept_metrics.append({
            "concept_id": cid,
            "name": cdata["concept"].get("name", cid),
            "mean_pi": agg["mean_pi"],
            "std_pi": agg["std_pi"],
            "top2box": top2,
            "bottom2box": bot2,
            "mid_box": mid,
            "pos_neg_ratio": ratio,
            "n": agg["n_respondents"],
        })

    # ------------------------------------------------------------------
    # Ranked concept list — one row per concept, ordered by mean PI
    # ------------------------------------------------------------------
    st.header("Concept Ranking")
    st.caption(
        "Ranked by mean purchase intent. Per the SSR methodology, "
        "**concept ranking is more reliable than absolute PI values.**"
    )

    ranked = sorted(concept_metrics, key=lambda cm: cm["mean_pi"], reverse=True)
    for rank, cm in enumerate(ranked, 1):
        cid = cm["concept_id"]
        concept_data = results["concepts"][cid]["concept"]
        with st.container(border=True):
            st.markdown(f"#### #{rank} — {cm['name']}")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Mean PI", f"{cm['mean_pi']:.2f}")
            m2.metric("Top 2 Box", f"{cm['top2box']:.0%}")
            m3.metric("Bottom 2 Box", f"{cm['bottom2box']:.0%}")
            m4.metric("+/− Ratio", f"{cm['pos_neg_ratio']:.1f}:1")
            m5.metric("Std Dev", f"{cm['std_pi']:.2f}")

            img_path = concept_data.get("image_path")
            if img_path:
                img_file = Path(img_path)
                if not img_file.exists():
                    img_file = Path(data_dir).resolve() / img_path
                if not img_file.exists():
                    img_file = Path(data_dir).resolve() / Path(img_path).name
                if img_file.exists():
                    with st.expander("📷 Concept image"):
                        st.image(str(img_file), width=400)

    # ------------------------------------------------------------------
    # Metric-by-metric winners (collapsed by default)
    # ------------------------------------------------------------------
    if len(concept_metrics) >= 2:
        with st.expander("🏆 Metric-by-metric winners"):
            metric_defs = [
                ("mean_pi", "Mean PI", "higher", ".2f"),
                ("top2box", "Top 2 Box", "higher", ".0%"),
                ("pos_neg_ratio", "+/− Ratio", "higher", ".1f"),
                ("bottom2box", "Bottom 2 Box", "lower", ".0%"),
                ("std_pi", "Consensus (Low Std)", "lower", ".2f"),
            ]

            ranking_rows = []
            wins = {cm["name"]: 0 for cm in concept_metrics}

            for key, label, direction, fmt in metric_defs:
                values = [(cm["name"], cm[key]) for cm in concept_metrics]
                if direction == "higher":
                    winner_name = max(values, key=lambda x: x[1])[0]
                else:
                    winner_name = min(values, key=lambda x: x[1])[0]

                # Only count a win if there's a meaningful difference
                sorted_vals = sorted([v for _, v in values], reverse=(direction == "higher"))
                margin = abs(sorted_vals[0] - sorted_vals[1]) if len(sorted_vals) > 1 else 0
                is_tie = margin < 0.005  # within rounding

                row = {"Metric": label, "Favors": "Tie" if is_tie else winner_name}
                for cm in concept_metrics:
                    val = cm[key]
                    if fmt == ".0%":
                        row[cm["name"]] = f"{val:.0%}"
                    elif fmt == ".1f":
                        row[cm["name"]] = f"{val:.1f}:1" if key == "pos_neg_ratio" else f"{val:.1f}"
                    else:
                        row[cm["name"]] = f"{val:{fmt}}"

                if not is_tie:
                    wins[winner_name] += 1

                ranking_rows.append(row)

            max_wins = max(wins.values())
            leaders = [name for name, w in wins.items() if w == max_wins]

            if len(leaders) == 1 and max_wins > 0:
                st.success(f"🏆 **{leaders[0]}** leads on {max_wins} of {len(metric_defs)} metrics")
            elif max_wins > 0:
                st.info(f"📊 **Tied**: {' and '.join(leaders)} each lead on {max_wins} metrics")
            else:
                st.info("📊 Concepts are statistically indistinguishable on these metrics")

            st.dataframe(
                pd.DataFrame(ranking_rows),
                hide_index=True,
                width="stretch",
                column_config={
                    "Favors": st.column_config.TextColumn("Winner", width="medium"),
                },
            )


# ---------------------------------------------------------------------------
# Tab 2: Demographics
# ---------------------------------------------------------------------------

with tab_demographics:
    st.header("Demographic Breakdowns")

    demo_axis = st.selectbox(
        "Segment by",
        options=DEMO_AXES,
        format_func=lambda x: x.replace("_", " ").title(),
    )
    st.caption(
        f"Panel: ages {int(df['age'].min())}–{int(df['age'].max())}, "
        f"{df['persona_id'].nunique()} respondents. "
        "Only axes that vary in this panel are shown."
    )

    # Reliability warning
    if demo_axis in UNRELIABLE_AXES:
        st.warning(
            f"⚠️ **{demo_axis.title()}** is flagged as an unreliable demographic axis. "
            "The SSR paper found that LLMs inconsistently capture gender, region, and "
            "ethnicity differences. Interpret these breakdowns with caution."
        )

    sort_order = None
    if demo_axis == "income":
        sort_order = [i for i in INCOME_ORDER if i in df["income"].unique()]
    elif demo_axis == "age_band":
        sort_order = AGE_BAND_ORDER

    st.altair_chart(
        demographic_chart(df, demo_axis, sort_order=sort_order),
        width="stretch",
    )

    # Also show distribution faceted by demographic
    st.subheader("Distribution by Segment")

    pmf_melted = df.melt(
        id_vars=["concept_name", demo_axis],
        value_vars=["p1", "p2", "p3", "p4", "p5"],
        var_name="rating_col",
        value_name="prob",
    )
    pmf_melted["Rating"] = pmf_melted["rating_col"].str.replace("p", "")
    facet_grouped = (
        pmf_melted.groupby(["concept_name", demo_axis, "Rating"], observed=True)["prob"]
        .mean()
        .reset_index()
    )

    facet_chart = (
        alt.Chart(facet_grouped)
        .mark_bar()
        .encode(
            x=alt.X("Rating:N", sort=LIKERT_ORDER, title="Rating"),
            y=alt.Y("prob:Q", title="Proportion", axis=alt.Axis(format=".0%")),
            color=alt.Color("concept_name:N", title="Concept"),
            xOffset="concept_name:N",
        )
        .properties(height=200, width=180)
        .facet(
            facet=alt.Facet(f"{demo_axis}:N", title=demo_axis.replace("_", " ").title(),
                            sort=sort_order),
            columns=4,
        )
    )
    st.altair_chart(facet_chart)

    # Segment size table
    st.subheader("Segment Sizes")
    segment_counts = df.groupby(demo_axis, observed=True)["persona_id"].nunique().reset_index()
    segment_counts.columns = [demo_axis.replace("_", " ").title(), "Respondents"]
    st.dataframe(segment_counts, hide_index=True)


# ---------------------------------------------------------------------------
# Tab 3: Individual Responses
# ---------------------------------------------------------------------------

with tab_responses:
    st.header("Individual Response Browser")
    st.caption(
        "Interactive reviews panel — filter by sentiment band, demographics, "
        "and search text. Click responses to expand. Reasoning responses "
        "(stage 2) are available via the expandable section on each card."
    )

    # Render the React reviews component with real pipeline data
    reviews_html = render_reviews_html(results, personas)
    components.html(reviews_html, height=2400, scrolling=True)


# ---------------------------------------------------------------------------
# Tab 4: Insights (LLM-synthesized)
# ---------------------------------------------------------------------------

with tab_insights:
    st.header("Actionable Insights")
    st.caption(
        "⚗️ These are **hypotheses to test**, not proven facts. "
        "Synthetic panel data is best used to prioritize what to validate with real consumers."
    )

    if insights is None:
        st.warning(
            "No insights.json found in this run directory. "
            "Insights are auto-generated at pipeline time using GPT-4o-mini.\n\n"
            "To generate insights for an existing run:\n"
            "```\npython -m core.insights_generator path/to/results.json\n```"
        )
    elif "error" in insights:
        st.error(f"Insight generation failed: {insights['error']}")
    else:
        # ── Headline ──────────────────────────────────────────────
        headline = insights.get("headline", "")
        if headline:
            st.info(f"**{headline}**")

        # ── Ranking Interpretation ────────────────────────────────
        ranking = insights.get("concept_ranking", [])
        interp = insights.get("ranking_interpretation", {})
        if ranking or interp:
            st.subheader("⚖️ Concept Ranking")
            top_pick = interp.get("top_pick", "")
            if top_pick:
                st.success(f"**Top pick:** {top_pick}")
            if ranking:
                rank_rows = [
                    {
                        "Rank": r["rank"],
                        "Concept": r["name"],
                        "Mean PI": f"{r['mean_pi']:.2f}",
                        "Top 2 Box": f"{r['top2box']:.0%}",
                        "Tie Group": r.get("tie_group", "—"),
                        "Δ from #1": f"{r.get('delta_from_top', 0):.2f}",
                    }
                    for r in ranking
                ]
                st.dataframe(pd.DataFrame(rank_rows), hide_index=True, width="stretch")
            seps = interp.get("meaningful_separations", "")
            if seps:
                st.markdown(f"**Meaningful separations:** {seps}")
            noise = interp.get("within_noise_notes", "")
            if noise:
                st.caption(f"Within noise: {noise}")

        # ── Per-concept drivers/pain points ───────────────────────
        concept_specific = insights.get("concept_specific", {})
        if concept_specific:
            st.markdown("---")
            st.subheader("📋 Concept Profiles")

            # Keys may be concept names or concept IDs depending on generator version
            id_to_name = {
                cid: cdata["concept"].get("name", cid)
                for cid, cdata in results["concepts"].items()
            }
            # Order profiles by ranking when available
            rank_order = [r["name"] for r in ranking] if ranking else None
            items = list(concept_specific.items())
            if rank_order:
                items.sort(key=lambda kv: rank_order.index(id_to_name.get(kv[0], kv[0]))
                           if id_to_name.get(kv[0], kv[0]) in rank_order else 99)

            for i, (key, cdata) in enumerate(items):
                cname = id_to_name.get(key, key)
                with st.expander(f"**{cname}**", expanded=(i == 0)):
                    rank_context = cdata.get("rank_context", "")
                    if rank_context:
                        st.caption(rank_context)
                    best = cdata.get("best_audience", "")
                    if best:
                        st.caption(f"🎯 Best audience: {best}")

                    drivers = cdata.get("purchase_drivers", cdata.get("strengths", []))
                    pains = cdata.get("pain_points", cdata.get("weaknesses", []))

                    dcol, pcol = st.columns(2)
                    with dcol:
                        st.markdown("**✅ Purchase drivers**")
                        for item in drivers:
                            if isinstance(item, dict):
                                st.markdown(f"- **{item.get('theme', '')}** — {item.get('detail', '')}")
                                if item.get("evidence"):
                                    st.caption(f"> {item['evidence']}")
                            else:
                                st.markdown(f"- {item}")
                    with pcol:
                        st.markdown("**⚠️ Pain points**")
                        for item in pains:
                            if isinstance(item, dict):
                                st.markdown(f"- **{item.get('theme', '')}** — {item.get('detail', '')}")
                                if item.get("evidence"):
                                    st.caption(f"> {item['evidence']}")
                            else:
                                st.markdown(f"- {item}")

        # ── Segment Insights (the main event) ─────────────────────
        segment_insights = insights.get("segment_insights", [])
        if segment_insights:
            st.markdown("---")
            st.subheader("👥 Segment-Level Findings")
            st.caption("Sorted by actionability. Based on pre-computed segment metrics.")

            for i, si in enumerate(segment_insights, 1):
                axis = si.get("segment_axis", "")
                finding = si.get("finding", "")
                implication = si.get("implication", "")
                evidence = si.get("evidence", "")

                with st.expander(
                    f"**{i}. {axis.replace('_', ' ').title()}**: {finding[:100]}{'...' if len(finding) > 100 else ''}",
                    expanded=(i <= 3),
                ):
                    st.markdown(finding)
                    if implication:
                        st.markdown(f"**Implication:** {implication}")
                    if evidence:
                        st.caption(f'> {evidence}')

                    # Render pre-computed segment data for this axis if available
                    precomputed = insights.get("_precomputed", {})
                    axis_key = axis.lower().replace(" ", "_")
                    has_data = False
                    for cid in precomputed:
                        sm = precomputed[cid].get("segment_metrics", {})
                        if axis_key in sm:
                            has_data = True
                            break

                    if has_data:
                        seg_rows = []
                        all_segs = set()
                        for cid in precomputed:
                            sm = precomputed[cid].get("segment_metrics", {}).get(axis_key, {})
                            all_segs |= set(sm.keys())

                        for seg in sorted(all_segs):
                            row = {"Segment": seg}
                            for cid in precomputed:
                                sm = precomputed[cid].get("segment_metrics", {}).get(axis_key, {})
                                cname = results["concepts"].get(cid, {}).get("concept", {}).get("name", cid)
                                data = sm.get(seg, {})
                                row[cname] = f"{data.get('mean_pi', 0):.2f}" if data else "—"
                                row[f"n ({cname})"] = data.get("n", 0) if data else 0
                            seg_rows.append(row)

                        if seg_rows:
                            st.dataframe(
                                pd.DataFrame(seg_rows).sort_values(
                                    list(seg_rows[0].keys())[1], ascending=False
                                ),
                                hide_index=True,
                                width="stretch",
                            )

        # ── Topic Analysis ────────────────────────────────────────
        topic_analysis = insights.get("topic_analysis", [])
        if topic_analysis:
            st.markdown("---")
            st.subheader("🔍 Topic Analysis")
            st.caption("Based on pre-computed keyword frequencies across all responses.")

            for ta in topic_analysis:
                topic = ta.get("topic", "")
                rate = ta.get("mention_rate", "")
                role = ta.get("role", "")
                detail = ta.get("detail", "")
                concept_diff = ta.get("concept_difference", "")

                role_icon = {"driver": "🟢", "barrier": "🔴", "mixed": "🟡"}.get(role, "⚪")

                with st.expander(f"{role_icon} **{topic}** — {rate} mention rate ({role})"):
                    st.markdown(detail)
                    if concept_diff:
                        st.markdown(f"**Concept difference:** {concept_diff}")

        # ── Recommended Actions ───────────────────────────────────
        actions = insights.get("recommended_actions", [])
        if actions:
            st.markdown("---")
            st.subheader("🎯 Recommended Actions")

            for i, rec in enumerate(actions, 1):
                priority = rec.get("priority", "medium")
                priority_badge = {"high": "🔴 HIGH", "medium": "🟡 MED", "low": "🟢 LOW"}.get(priority, "")
                action = rec.get("action", "")
                evidence = rec.get("evidence", "")
                impact = rec.get("expected_impact", "")

                with st.expander(
                    f"**{i}. {action}** — {priority_badge}",
                    expanded=(priority == "high"),
                ):
                    if evidence:
                        st.markdown(f"**Evidence:** {evidence}")
                    if impact:
                        st.markdown(f"**Expected impact:** {impact}")

        # ── Methodology Notes ─────────────────────────────────────
        notes = insights.get("methodology_notes", [])
        if notes:
            st.markdown("---")
            st.subheader("📝 Methodology Notes")
            for n in notes:
                st.markdown(f"- {n}")

        # ── Meta ──────────────────────────────────────────────────
        imeta = insights.get("_meta", {})
        st.markdown("---")
        st.caption(
            f"Generated by {imeta.get('model', 'unknown')} · "
            f"{imeta.get('n_concepts', '?')} concepts analyzed · "
            f"~{imeta.get('prompt_tokens_approx', '?'):,} input tokens"
        )


# ---------------------------------------------------------------------------
# Tab 5: Head-to-Head Comparison
# ---------------------------------------------------------------------------

with tab_compare:
    st.header("Concept Comparison")

    concept_names = df["concept_name"].unique().tolist()
    if len(concept_names) < 2:
        st.info("Need at least 2 concepts for comparison.")
    else:
        cc1, cc2 = st.columns(2)
        with cc1:
            left_concept = st.selectbox("Concept A", concept_names, index=0)
        with cc2:
            right_concept = st.selectbox("Concept B", concept_names, index=min(1, len(concept_names) - 1))

        left_df = df[df["concept_name"] == left_concept]
        right_df = df[df["concept_name"] == right_concept]
        compare_df = df[df["concept_name"].isin([left_concept, right_concept])]

        # Key metrics as grouped bar chart
        st.subheader("Key Metrics")

        metric_rows = []
        for concept_df, name in [(left_df, left_concept), (right_df, right_concept)]:
            top2 = concept_df["top2box"].mean()
            bot2 = concept_df["bottom2box"].mean()
            metric_rows.extend([
                {"Concept": name, "Metric": "Mean PI", "Value": concept_df["expected_rating"].mean()},
                {"Concept": name, "Metric": "Top 2 Box", "Value": top2},
                {"Concept": name, "Metric": "Bottom 2 Box", "Value": bot2},
                {"Concept": name, "Metric": "+/− Ratio", "Value": top2 / bot2 if bot2 > 0 else 0},
                {"Concept": name, "Metric": "Std Dev", "Value": concept_df["expected_rating"].std()},
            ])
        metrics_long = pd.DataFrame(metric_rows)

        metrics_chart = (
            alt.Chart(metrics_long)
            .mark_bar()
            .encode(
                x=alt.X("Concept:N", title=None, axis=alt.Axis(labels=False)),
                y=alt.Y("Value:Q", title=None),
                color=alt.Color("Concept:N", title="Concept"),
                column=alt.Column("Metric:N", title=None,
                                  sort=["Mean PI", "Top 2 Box", "Bottom 2 Box", "+/− Ratio", "Std Dev"]),
                tooltip=[
                    alt.Tooltip("Concept:N"),
                    alt.Tooltip("Metric:N"),
                    alt.Tooltip("Value:Q", format=".2f"),
                ],
            )
            .properties(height=250, width=120)
            .resolve_scale(y="independent")
        )
        st.altair_chart(metrics_chart)

        # Demographic comparison
        st.subheader("Demographic Comparison")
        compare_demo = st.selectbox(
            "Compare by",
            options=DEMO_AXES,
            format_func=lambda x: x.replace("_", " ").title(),
            key="compare_demo",
        )

        if compare_demo in UNRELIABLE_AXES:
            st.warning(f"⚠️ **{compare_demo.title()}** is flagged as unreliable.")

        compare_sort = None
        if compare_demo == "income":
            compare_sort = [i for i in INCOME_ORDER if i in df["income"].unique()]
        elif compare_demo == "age_band":
            compare_sort = AGE_BAND_ORDER

        st.altair_chart(
            demographic_chart(compare_df, compare_demo, sort_order=compare_sort),
            width="stretch",
        )

        # Representative quotes
        st.subheader("Representative Quotes by Sentiment")
        for sentiment_label in ["Positive", "Neutral", "Negative"]:
            st.markdown(f"**{sentiment_label}**")
            q1, q2 = st.columns(2)
            for col, concept_name in [(q1, left_concept), (q2, right_concept)]:
                with col:
                    subset = df[
                        (df["concept_name"] == concept_name)
                        & (df["sentiment"] == sentiment_label)
                    ]
                    if len(subset) > 0:
                        sample = subset.sample(min(2, len(subset)), random_state=42)
                        for _, row in sample.iterrows():
                            st.caption(f"{concept_name} — {row['persona_id']} (E[r]={row['expected_rating']:.2f})")
                            st.markdown(f"> {row['free_text']}")
                            if row.get("reasoning"):
                                st.markdown(f"> **Why:** {row['reasoning']}")
                    else:
                        st.caption(f"No {sentiment_label.lower()} responses")


# ---------------------------------------------------------------------------
# Tab 6: Metadata & Reliability
# ---------------------------------------------------------------------------

with tab_metadata:
    st.header("Run Metadata & Reliability")

    st.subheader("Pipeline Configuration")
    config_display = {
        "LLM Provider": str(config.get("llm_provider", "—")),
        "LLM Model": str(config.get("llm_model", "—")),
        "LLM Temperature": str(config.get("llm_temperature", "—")),
        "Embedding Model": str(config.get("embedding_model", "—")),
        "SSR Epsilon (ε)": str(config.get("ssr_epsilon", "—")),
        "SSR Temperature (T)": str(config.get("ssr_temperature", "—")),
        "Samples per Persona": str(config.get("samples_per_persona", "—")),
        "Seed": str(config.get("seed", "—")),
        "Reference Sets": ", ".join(config.get("reference_sets", [])),
    }
    st.dataframe(
        pd.DataFrame(config_display.items(), columns=["Parameter", "Value"]),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Engagement Info")
    st.json(engagement)

    st.subheader("Panel Summary")
    panel = personas.get("panel_summary", {})
    st.json(panel)

    # Reliability indicators
    st.subheader("Reliability Indicators")

    st.markdown("**Demographic Segment Representation**")
    st.caption(
        "Segments with fewer respondents produce less reliable breakdowns. "
        "The paper recommends N ≥ 20 per segment for meaningful analysis."
    )

    for axis in ["age_band", "income", "gender", "region"]:
        counts = df.groupby(axis, observed=True)["persona_id"].nunique()
        min_n = counts.min()
        flag = "⚠️" if min_n < 20 else "✅"
        unreliable = " *(unreliable axis per paper)*" if axis in UNRELIABLE_AXES else ""
        st.markdown(
            f"{flag} **{axis.replace('_', ' ').title()}**: "
            f"min segment = {min_n}, max = {counts.max()}{unreliable}"
        )

    st.markdown("---")
    st.markdown("**Methodological Notes**")
    st.markdown(
        "- SSR distributions are **soft** (probabilistic), not hard ratings. "
        "Each respondent produces a PMF over 1-5, not a single number.\n"
        "- **Mean PI alone can look lukewarm.** The paper's full dataset had "
        "std of only ~0.2 across concepts. Focus on distribution shape, "
        "top-2-box, and +/− ratio.\n"
        "- **Concept ranking** (which concept wins) is more reliable than "
        "absolute PI values.\n"
        "- Synthetic responses are **less positively biased** than human "
        "surveys — expect lower absolute PI values than a traditional panel."
    )

    st.markdown(f"**Run timestamp:** {meta.get('timestamp', '—')}")