"""
report_generator.py — PDF export for SSR Results Explorer

Two export modes:
1. Executive Summary PDF — overview charts, metrics, insights, sample responses
2. Full Responses PDF — every individual response in a styled card format

Usage (standalone):
    python report_generator.py --data-dir output/run_xxx --mode summary
    python report_generator.py --data-dir output/run_xxx --mode responses

Usage (from Streamlit):
    from report_generator import generate_summary_pdf, generate_responses_pdf
    pdf_bytes = generate_summary_pdf(results, personas, insights)
    pdf_bytes = generate_responses_pdf(results, personas, concept_filter=["concept_a"])
"""

import json
import io
import textwrap
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, HRFlowable,
)
from reportlab.lib.utils import ImageReader


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

BRAND_DARK = HexColor("#1a1a2e")
BRAND_PRIMARY = HexColor("#16213e")
BRAND_ACCENT = HexColor("#0f3460")
BRAND_HIGHLIGHT = HexColor("#e94560")
BRAND_LIGHT_BG = HexColor("#f5f5f5")
BRAND_GREEN = HexColor("#2d6a4f")
BRAND_AMBER = HexColor("#e9c46a")
BRAND_RED = HexColor("#e76f51")
BRAND_BLUE = HexColor("#457b9d")
BRAND_GRAY = HexColor("#6c757d")
WHITE = white

CONCEPT_COLORS = ["#457b9d", "#e76f51", "#2a9d8f", "#e9c46a", "#6a4c93"]

SENTIMENT_COLORS = {
    "Positive": "#2d6a4f",
    "Neutral": "#e9c46a",
    "Negative": "#e76f51",
}

INCOME_ORDER = ["low", "moderate", "upper-moderate", "high"]
AGE_ORDER = ["18-29", "30-44", "45-59", "60+"]


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=22, textColor=BRAND_DARK, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=11, textColor=BRAND_GRAY, spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading1"],
        fontSize=15, textColor=BRAND_PRIMARY, spaceBefore=18, spaceAfter=8,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        "SubSection", parent=styles["Heading2"],
        fontSize=12, textColor=BRAND_ACCENT, spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "ReportBody", parent=styles["Normal"],
        fontSize=9.5, leading=13, textColor=black, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "SmallText", parent=styles["Normal"],
        fontSize=8, leading=10, textColor=BRAND_GRAY, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "QuoteText", parent=styles["Normal"],
        fontSize=9, leading=12, textColor=HexColor("#333333"),
        leftIndent=12, rightIndent=12, spaceAfter=4,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        "CardHeader", parent=styles["Normal"],
        fontSize=10, leading=13, textColor=BRAND_DARK,
        spaceBefore=2, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "MetricValue", parent=styles["Normal"],
        fontSize=18, textColor=BRAND_PRIMARY, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "MetricLabel", parent=styles["Normal"],
        fontSize=8, textColor=BRAND_GRAY, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, textColor=BRAND_GRAY, alignment=TA_RIGHT,
    ))
    return styles


# ---------------------------------------------------------------------------
# Data helpers (mirror app.py logic)
# ---------------------------------------------------------------------------

def _build_respondent_records(results, personas):
    """Flat list of dicts, one per (concept, respondent)."""
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}
    rows = []
    for concept_id, concept_data in results["concepts"].items():
        concept_name = concept_data["concept"].get("name", concept_id)
        for resp in concept_data["respondents"]:
            persona = persona_lookup.get(resp["persona_id"], {})
            pmf = resp["averaged_pmf"]
            p4 = pmf.get("4", 0)
            p5 = pmf.get("5", 0)
            p1 = pmf.get("1", 0)
            p2 = pmf.get("2", 0)
            er = resp["expected_rating"]

            if er >= 4.0:
                sentiment = "Strong intent"
            elif er >= 3.5:
                sentiment = "Leaning positive"
            elif er >= 2.8:
                sentiment = "Neutral"
            elif er >= 2.2:
                sentiment = "Leaning negative"
            else:
                sentiment = "Low intent"

            # Simpler 3-bucket for filtering
            if er >= 3.5:
                sentiment_3 = "Positive"
            elif er >= 2.5:
                sentiment_3 = "Neutral"
            else:
                sentiment_3 = "Negative"

            age = persona.get("age", 0)
            if age <= 29:
                age_band = "18-29"
            elif age <= 44:
                age_band = "30-44"
            elif age <= 59:
                age_band = "45-59"
            else:
                age_band = "60+"

            rows.append({
                "concept_id": concept_id,
                "concept_name": concept_name,
                "persona_id": resp["persona_id"],
                "free_text": resp["free_text_response"],
                "reasoning": resp.get("reasoning_response", ""),
                "expected_rating": er,
                "mode_rating": resp["mode_rating"],
                "top2box": p4 + p5,
                "bottom2box": p1 + p2,
                "sentiment": sentiment,
                "sentiment_3": sentiment_3,
                "age": age,
                "age_band": age_band,
                "gender": persona.get("gender", "—"),
                "region": persona.get("region", "—"),
                "income": persona.get("income", "—"),
                "pmf": pmf,
            })
    return rows


def _concept_metrics(results):
    """Per-concept aggregate metrics list."""
    metrics = []
    for cid, cdata in results["concepts"].items():
        agg = cdata["aggregate"]
        dist = agg["distribution"]
        top2 = float(dist.get("4", 0)) + float(dist.get("5", 0))
        bot2 = float(dist.get("1", 0)) + float(dist.get("2", 0))
        ratio = top2 / bot2 if bot2 > 0 else float("inf")
        metrics.append({
            "concept_id": cid,
            "name": cdata["concept"].get("name", cid),
            "description": cdata["concept"].get("description", ""),
            "mean_pi": agg["mean_pi"],
            "std_pi": agg["std_pi"],
            "top2box": top2,
            "bottom2box": bot2,
            "pos_neg_ratio": ratio,
            "n": agg["n_respondents"],
            "distribution": dist,
        })
    return metrics


# ---------------------------------------------------------------------------
# Chart rendering (matplotlib -> ReportLab Image)
# ---------------------------------------------------------------------------

def _fig_to_image(fig, width=6*inch, dpi=150):
    """Convert matplotlib figure to a ReportLab Image flowable."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    img_reader = ImageReader(buf)
    iw, ih = img_reader.getSize()
    aspect = ih / iw
    return Image(buf, width=width, height=width * aspect)


def _likert_distribution_chart(concept_metrics_list, width_inches=6.5):
    """Grouped bar chart of Likert distributions across concepts."""
    n_concepts = len(concept_metrics_list)
    ratings = ["1", "2", "3", "4", "5"]
    x = np.arange(len(ratings))
    bar_width = 0.7 / max(n_concepts, 1)

    fig, ax = plt.subplots(figsize=(width_inches, 3.2))
    for i, cm in enumerate(concept_metrics_list):
        vals = [float(cm["distribution"].get(r, 0)) for r in ratings]
        offset = (i - (n_concepts - 1) / 2) * bar_width
        bars = ax.bar(x + offset, vals, bar_width, label=cm["name"],
                      color=CONCEPT_COLORS[i % len(CONCEPT_COLORS)], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(["1\nVery\nunlikely", "2", "3\nNeutral", "4", "5\nVery\nlikely"],
                       fontsize=8)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("Proportion", fontsize=9)
    ax.set_title("Purchase Intent Distribution", fontsize=11, fontweight="bold", pad=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(0.5, max(
        float(cm["distribution"].get(r, 0))
        for cm in concept_metrics_list for r in ratings
    ) * 1.15))

    fig.tight_layout()
    return fig


def _demographic_chart(rows, demo_key, sort_order=None, width_inches=6.5):
    """Mean PI by demographic segment, grouped by concept."""
    from collections import defaultdict
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[r["concept_name"]][r[demo_key]].append(r["expected_rating"])

    concept_names = list(groups.keys())
    if sort_order:
        segments = [s for s in sort_order if any(s in groups[c] for c in concept_names)]
    else:
        all_segs = set()
        for c in concept_names:
            all_segs.update(groups[c].keys())
        segments = sorted(all_segs)

    x = np.arange(len(segments))
    bar_width = 0.7 / max(len(concept_names), 1)

    fig, ax = plt.subplots(figsize=(width_inches, 3.0))
    for i, cname in enumerate(concept_names):
        means = []
        for seg in segments:
            vals = groups[cname].get(seg, [])
            means.append(np.mean(vals) if vals else 0)
        offset = (i - (len(concept_names) - 1) / 2) * bar_width
        ax.bar(x + offset, means, bar_width, label=cname,
               color=CONCEPT_COLORS[i % len(CONCEPT_COLORS)], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(segments, fontsize=8)
    ax.set_ylabel("Mean Purchase Intent", fontsize=9)
    ax.set_ylim(1, 5)
    ax.set_title(f"Mean PI by {demo_key.replace('_', ' ').title()}", fontsize=11,
                 fontweight="bold", pad=10)
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Response card builder (shared between summary sample + full export)
# ---------------------------------------------------------------------------

def _response_card_elements(row, styles, show_reasoning=True):
    """Build a list of flowables for a single response card."""
    elements = []

    # Sentiment color
    s3 = row["sentiment_3"]
    if s3 == "Positive":
        sent_color = BRAND_GREEN
    elif s3 == "Neutral":
        sent_color = HexColor("#b8860b")
    else:
        sent_color = BRAND_RED

    # Star rating visual
    er = row["expected_rating"]
    full_stars = int(er)
    stars_str = "★" * full_stars + "☆" * (5 - full_stars)

    # Header line: persona | demographics | rating
    demo_parts = []
    if row.get("gender") and row["gender"] != "—":
        demo_parts.append(row["gender"].title())
    if row.get("age"):
        demo_parts.append(f"Age {row['age']}")
    if row.get("income") and row["income"] != "—":
        demo_parts.append(row["income"].title() + " income")
    if row.get("region") and row["region"] != "—":
        demo_parts.append(row["region"])
    demo_str = " · ".join(demo_parts) if demo_parts else "—"

    header_html = (
        f'<b>{row["persona_id"]}</b> &nbsp; '
        f'<font size="8" color="#6c757d">{demo_str}</font>'
    )
    elements.append(Paragraph(header_html, styles["CardHeader"]))

    # Rating + sentiment badge
    rating_html = (
        f'<font size="14" color="{sent_color.hexval()}">{stars_str}</font> &nbsp; '
        f'<font size="9"><b>{er:.2f}</b></font> &nbsp; '
        f'<font size="8" color="{sent_color.hexval()}">{row["sentiment"]}</font>'
    )
    elements.append(Paragraph(rating_html, styles["ReportBody"]))

    # Free text response
    free_text = row["free_text"]
    # Split on pipe if the two-sample concatenation is present
    if " | " in free_text:
        free_text = free_text.split(" | ")[0]
    # Truncate very long responses for card display
    if len(free_text) > 600:
        free_text = free_text[:597] + "..."

    elements.append(Paragraph(
        f'<i>"{free_text}"</i>', styles["QuoteText"]
    ))

    # Reasoning (collapsible in app, just shown smaller here)
    if show_reasoning and row.get("reasoning"):
        reasoning = row["reasoning"]
        if len(reasoning) > 400:
            reasoning = reasoning[:397] + "..."
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(
            f'<font size="8" color="#6c757d"><b>Why they feel this way:</b></font>',
            styles["SmallText"],
        ))
        elements.append(Paragraph(
            f'<font size="8" color="#555555">{reasoning}</font>',
            styles["SmallText"],
        ))

    return elements


def _response_card_table(row, styles, show_reasoning=True):
    """Wrap a response card in a light-background table for visual separation."""
    inner = _response_card_elements(row, styles, show_reasoning)
    # Use a table with one cell to create the card background
    card_content = []
    for el in inner:
        card_content.append(el)

    # Combine into a single cell
    t = Table([[card_content]], colWidths=[6.3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---------------------------------------------------------------------------
# Page template with footer
# ---------------------------------------------------------------------------

def _add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(HexColor("#999999"))
    canvas.drawRightString(
        doc.pagesize[0] - 0.5 * inch,
        0.4 * inch,
        f"SSR Synthetic Survey Report  ·  Page {doc.page}"
    )
    canvas.drawString(
        0.5 * inch,
        0.4 * inch,
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    canvas.restoreState()


# ===========================================================================
# PUBLIC API: Generate Executive Summary PDF
# ===========================================================================

def generate_summary_pdf(results, personas, insights=None, sample_size=3):
    """
    Generate an executive summary PDF report.

    Args:
        results: parsed results.json
        personas: parsed personas.json
        insights: parsed insights.json (optional)
        sample_size: number of sample responses per sentiment band per concept

    Returns:
        bytes — the PDF file content
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.6*inch, bottomMargin=0.7*inch,
    )
    styles = _build_styles()
    story = []

    meta = results.get("meta", {})
    engagement = meta.get("engagement", {})
    config = meta.get("pipeline_config", {})
    rows = _build_respondent_records(results, personas)
    cm_list = _concept_metrics(results)

    # ---- Title page ----
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("Synthetic Survey Report", styles["ReportTitle"]))
    story.append(Paragraph(
        f'{engagement.get("engagement", "Untitled")} — {engagement.get("client", "")}',
        styles["ReportSubtitle"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f'Date: {engagement.get("date", "—")} &nbsp;&nbsp; '
        f'Panel: {len(personas["personas"])} respondents &nbsp;&nbsp; '
        f'Concepts: {len(results["concepts"])} &nbsp;&nbsp; '
        f'Model: {config.get("llm_model", "—")}',
        styles["SmallText"],
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "This report presents synthetic consumer panel results generated using "
        "the Semantic Similarity Rating (SSR) methodology. Concept rankings are "
        "more reliable than absolute scores. All findings should be treated as "
        "hypotheses to validate with real consumers.",
        styles["ReportBody"],
    ))
    story.append(PageBreak())

    # ---- Section 1: Concept Overview ----
    story.append(Paragraph("1. Concept Overview", styles["SectionHeader"]))

    # Metrics table
    header = ["Concept", "Mean PI", "Top 2 Box", "+/- Ratio", "Bottom 2 Box", "N"]
    table_data = [header]
    for cm in cm_list:
        table_data.append([
            cm["name"],
            f'{cm["mean_pi"]:.2f}',
            f'{cm["top2box"]:.0%}',
            f'{cm["pos_neg_ratio"]:.1f}:1',
            f'{cm["bottom2box"]:.0%}',
            str(cm["n"]),
        ])

    t = Table(table_data, colWidths=[2*inch, 0.8*inch, 0.9*inch, 0.8*inch, 1*inch, 0.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Winner banner
    if len(cm_list) >= 2:
        sorted_by_pi = sorted(cm_list, key=lambda c: c["mean_pi"], reverse=True)
        winner = sorted_by_pi[0]
        runner = sorted_by_pi[1]
        lift = (winner["top2box"] / runner["top2box"] - 1) * 100 if runner["top2box"] > 0 else 0
        story.append(Paragraph(
            f'<b>{winner["name"]}</b> leads with {winner["top2box"]:.0%} Top 2 Box '
            f'(+{lift:.0f}% vs {runner["name"]}). '
            f'Positive-to-negative ratio: {winner["pos_neg_ratio"]:.1f}:1.',
            styles["ReportBody"],
        ))
        story.append(Spacer(1, 8))

    # Concept descriptions
    for cm in cm_list:
        if cm.get("description"):
            story.append(Paragraph(
                f'<b>{cm["name"]}:</b> {cm["description"]}',
                styles["SmallText"],
            ))
    story.append(Spacer(1, 8))

    # ---- Section 2: Distribution Chart ----
    story.append(Paragraph("2. Purchase Intent Distribution", styles["SectionHeader"]))
    fig = _likert_distribution_chart(cm_list)
    story.append(_fig_to_image(fig, width=6.2*inch))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Distributions show average probability mass across all respondents. "
        "Per SSR methodology, these are soft (probabilistic) distributions.",
        styles["SmallText"],
    ))
    story.append(Spacer(1, 8))

    # ---- Section 3: Demographic Breakdowns ----
    story.append(Paragraph("3. Demographic Breakdowns", styles["SectionHeader"]))

    for demo_key, sort_order in [("age_band", AGE_ORDER), ("income", INCOME_ORDER)]:
        fig = _demographic_chart(rows, demo_key, sort_order)
        story.append(_fig_to_image(fig, width=6.2*inch))
        story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Note: Age and income breakdowns replicate well in synthetic panels. "
        "Gender, region, and ethnicity are unreliable per the research literature.",
        styles["SmallText"],
    ))
    story.append(PageBreak())

    # ---- Section 4: Key Insights (if available) ----
    if insights:
        story.append(Paragraph("4. Key Insights", styles["SectionHeader"]))

        for cid, cinsights in insights.get("concepts", {}).items():
            cname = cid
            for cm in cm_list:
                if cm["concept_id"] == cid:
                    cname = cm["name"]
                    break

            story.append(Paragraph(cname, styles["SubSection"]))

            # Executive summary
            if cinsights.get("executive_summary"):
                story.append(Paragraph(cinsights["executive_summary"], styles["ReportBody"]))
                story.append(Spacer(1, 4))

            # Top drivers
            drivers = cinsights.get("purchase_drivers", [])[:3]
            if drivers:
                story.append(Paragraph("<b>Purchase Drivers</b>", styles["ReportBody"]))
                for d in drivers:
                    story.append(Paragraph(
                        f'• <b>{d["theme"]}</b>: {d["detail"]}',
                        styles["SmallText"],
                    ))

            # Top pain points
            pains = cinsights.get("pain_points", [])[:3]
            if pains:
                story.append(Spacer(1, 4))
                story.append(Paragraph("<b>Pain Points</b>", styles["ReportBody"]))
                for p in pains:
                    sev = p.get("severity", "")
                    sev_str = f' [{sev}]' if sev else ""
                    story.append(Paragraph(
                        f'• <b>{p["theme"]}</b>{sev_str}: {p["detail"]}',
                        styles["SmallText"],
                    ))

            story.append(Spacer(1, 10))

        # Recommendations
        for cid, cinsights in insights.get("concepts", {}).items():
            recs = cinsights.get("recommendations", [])
            if recs:
                story.append(Paragraph("Recommended Actions", styles["SubSection"]))
                for r in recs[:5]:
                    priority = r.get("priority", "")
                    p_str = f' [{priority}]' if priority else ""
                    story.append(Paragraph(
                        f'• <b>{r.get("action", "")}</b>{p_str}: {r.get("rationale", "")}',
                        styles["SmallText"],
                    ))
                break  # Only show recs once

        story.append(PageBreak())

    # ---- Section 5: Sample Responses ----
    section_num = 5 if insights else 4
    story.append(Paragraph(f"{section_num}. Sample Responses", styles["SectionHeader"]))
    story.append(Paragraph(
        f"A selection of {sample_size} responses per sentiment band per concept. "
        "Full responses are available in the detailed responses export.",
        styles["SmallText"],
    ))
    story.append(Spacer(1, 8))

    import random
    rng = random.Random(42)

    for cm in cm_list:
        story.append(Paragraph(cm["name"], styles["SubSection"]))
        concept_rows = [r for r in rows if r["concept_id"] == cm["concept_id"]]

        for sentiment_label in ["Positive", "Neutral", "Negative"]:
            band_rows = [r for r in concept_rows if r["sentiment_3"] == sentiment_label]
            if not band_rows:
                continue

            story.append(Paragraph(
                f'<font color="{SENTIMENT_COLORS[sentiment_label]}">'
                f'<b>{sentiment_label}</b></font> ({len(band_rows)} responses)',
                styles["ReportBody"],
            ))

            sample = rng.sample(band_rows, min(sample_size, len(band_rows)))
            for row in sample:
                card = _response_card_table(row, styles, show_reasoning=True)
                story.append(KeepTogether([card, Spacer(1, 6)]))

        story.append(Spacer(1, 8))

    # ---- Section 6: Methodology ----
    story.append(PageBreak())
    story.append(Paragraph(f"{section_num + 1}. Methodology & Configuration", styles["SectionHeader"]))

    method_text = (
        "This report uses the Semantic Similarity Rating (SSR) methodology. "
        "LLM-generated personas provide free-text responses to product concepts, "
        "which are then embedded and compared against calibrated reference statements "
        "to produce probabilistic Likert distributions. This avoids the center-clustering "
        "bias inherent in direct Likert elicitation. Six reference sets are averaged "
        "for robustness."
    )
    story.append(Paragraph(method_text, styles["ReportBody"]))
    story.append(Spacer(1, 8))

    config_rows = [
        ["Parameter", "Value"],
        ["LLM Model", str(config.get("llm_model", "—"))],
        ["LLM Temperature", str(config.get("llm_temperature", "—"))],
        ["Embedding Model", str(config.get("embedding_model", "—"))],
        ["SSR Epsilon", str(config.get("ssr_epsilon", "—"))],
        ["SSR Temperature", str(config.get("ssr_temperature", "—"))],
        ["Samples per Persona", str(config.get("samples_per_persona", "—"))],
        ["Seed", str(config.get("seed", "—"))],
        ["Panel Size", str(len(personas["personas"]))],
        ["Panel Tier", str(personas.get("panel_summary", {}).get("tier", "—"))],
    ]
    ct = Table(config_rows, colWidths=[2*inch, 3.5*inch])
    ct.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(ct)

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "<i>This synthetic survey data is generated by LLMs and should be treated "
        "as directional hypotheses. Concept rankings are more reliable than absolute scores. "
        "Validate key findings with real consumer research.</i>",
        styles["SmallText"],
    ))

    # Build
    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    buf.seek(0)
    return buf.getvalue()


# ===========================================================================
# PUBLIC API: Generate Full Responses PDF
# ===========================================================================

def generate_responses_pdf(results, personas, concept_filter=None, sort_by="rating_desc"):
    """
    Generate a PDF with every individual response in styled card format.

    Args:
        results: parsed results.json
        personas: parsed personas.json
        concept_filter: optional list of concept_ids to include
        sort_by: "rating_desc" (default), "rating_asc", "concept"

    Returns:
        bytes — the PDF file content
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.6*inch, bottomMargin=0.7*inch,
    )
    styles = _build_styles()
    story = []

    meta = results.get("meta", {})
    engagement = meta.get("engagement", {})
    rows = _build_respondent_records(results, personas)
    cm_list = _concept_metrics(results)

    if concept_filter:
        rows = [r for r in rows if r["concept_id"] in concept_filter]

    # Sort
    if sort_by == "rating_desc":
        rows.sort(key=lambda r: r["expected_rating"], reverse=True)
    elif sort_by == "rating_asc":
        rows.sort(key=lambda r: r["expected_rating"])
    else:
        rows.sort(key=lambda r: (r["concept_name"], -r["expected_rating"]))

    # ---- Title ----
    story.append(Paragraph("Individual Responses", styles["ReportTitle"]))
    story.append(Paragraph(
        f'{engagement.get("engagement", "")} — {engagement.get("client", "")}',
        styles["ReportSubtitle"],
    ))
    story.append(Paragraph(
        f'{len(rows)} responses across {len(set(r["concept_id"] for r in rows))} concept(s)',
        styles["SmallText"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 12))

    # ---- Summary stats header ----
    for cm in cm_list:
        if concept_filter and cm["concept_id"] not in concept_filter:
            continue
        story.append(Paragraph(
            f'<b>{cm["name"]}</b>: Mean PI {cm["mean_pi"]:.2f} · '
            f'Top 2 Box {cm["top2box"]:.0%} · '
            f'+/- Ratio {cm["pos_neg_ratio"]:.1f}:1 · '
            f'N={cm["n"]}',
            styles["ReportBody"],
        ))
    story.append(Spacer(1, 12))

    # ---- Responses grouped by concept ----
    concept_ids_in_order = []
    seen = set()
    for r in rows:
        if r["concept_id"] not in seen:
            concept_ids_in_order.append(r["concept_id"])
            seen.add(r["concept_id"])

    for cid in concept_ids_in_order:
        concept_rows = [r for r in rows if r["concept_id"] == cid]
        cname = concept_rows[0]["concept_name"] if concept_rows else cid

        story.append(Paragraph(cname, styles["SectionHeader"]))

        # Sentiment distribution summary
        pos = sum(1 for r in concept_rows if r["sentiment_3"] == "Positive")
        neu = sum(1 for r in concept_rows if r["sentiment_3"] == "Neutral")
        neg = sum(1 for r in concept_rows if r["sentiment_3"] == "Negative")
        total = len(concept_rows)

        story.append(Paragraph(
            f'<font color="{BRAND_GREEN.hexval()}">Positive: {pos} ({pos/total:.0%})</font> · '
            f'<font color="#b8860b">Neutral: {neu} ({neu/total:.0%})</font> · '
            f'<font color="{BRAND_RED.hexval()}">Negative: {neg} ({neg/total:.0%})</font>',
            styles["ReportBody"],
        ))
        story.append(Spacer(1, 8))

        # Sort within concept by rating desc
        concept_rows.sort(key=lambda r: r["expected_rating"], reverse=True)

        for i, row in enumerate(concept_rows):
            card = _response_card_table(row, styles, show_reasoning=True)
            story.append(KeepTogether([card, Spacer(1, 6)]))

        if cid != concept_ids_in_order[-1]:
            story.append(PageBreak())

    # Build
    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    buf.seek(0)
    return buf.getvalue()


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate SSR PDF reports")
    parser.add_argument("--data-dir", required=True, help="Path to run output directory")
    parser.add_argument("--mode", choices=["summary", "responses"], default="summary")
    parser.add_argument("--output", help="Output PDF path (default: auto-named)")
    parser.add_argument("--sample-size", type=int, default=3,
                        help="Responses per sentiment band in summary mode")
    args = parser.parse_args()

    data_path = Path(args.data_dir)
    with open(data_path / "results.json") as f:
        results = json.load(f)
    with open(data_path / "personas.json") as f:
        personas = json.load(f)

    insights = None
    insights_path = data_path / "insights.json"
    if insights_path.exists():
        with open(insights_path) as f:
            insights = json.load(f)

    if args.mode == "summary":
        pdf_bytes = generate_summary_pdf(results, personas, insights, args.sample_size)
        default_name = "ssr_summary_report.pdf"
    else:
        pdf_bytes = generate_responses_pdf(results, personas)
        default_name = "ssr_full_responses.pdf"

    out_path = args.output or str(data_path / default_name)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Written: {out_path} ({len(pdf_bytes):,} bytes)")
