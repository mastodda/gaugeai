#!/usr/bin/env python3
"""
validate.py — Compare human survey responses to synthetic SSR pipeline results.

Pilot validation tool. Designed for n=5 concepts with ~30+ human respondents.
Produces a PDF report with per-concept comparison, ranking agreement, and
distribution overlap.

Usage:
    # Human-only mode (works without synthetic runs)
    python validate.py --human human_responses.csv --output report.pdf

    # Full validation mode (with synthetic pipeline results)
    python validate.py --human human_responses.csv \
        --synthetic-dir runs/ \
        --output report.pdf

Synthetic results dir layout expected:
    runs/
      kindling/results.json
      hearth/results.json
      dailyone/results.json
      graze/results.json
      halden/results.json
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
    KeepTogether,
)


# ---------------------------------------------------------------------------
# Configuration: concept order + Likert mapping
# ---------------------------------------------------------------------------

# Order of concepts as they appear in the Google Forms CSV columns.
# (PI col, reasoning col) pairs follow this order.
HUMAN_CSV_CONCEPT_ORDER = ["Graze", "Hearth", "Kindling", "DailyOne", "Halden"]

# Map synthetic results.json directory names to concept display names.
# Filenames are normalized lowercase; display names match HUMAN_CSV_CONCEPT_ORDER.
SYNTHETIC_DIR_TO_NAME = {
    "graze": "Graze",
    "hearth": "Hearth",
    "kindling": "Kindling",
    "dailyone": "DailyOne",
    "halden": "Halden",
}

LIKERT_MAP = {
    "Definitely would not buy": 1,
    "Probably would not buy": 2,
    "Might or might not buy": 3,
    "Probably would buy": 4,
    "Definitely would buy": 5,
}


# ---------------------------------------------------------------------------
# Human data loading
# ---------------------------------------------------------------------------

def load_human_responses(csv_path: Path) -> dict:
    """
    Parse the Google Forms CSV.

    Returns a dict shaped like:
      {
        "concept_name": {
          "ratings": [int, ...],          # 1-5 Likert values
          "reasoning": [str, ...],         # free-text responses (filtered)
        },
        ...
      }
    Plus a "_meta" key with respondent count and demographic breakdown.
    """
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.reader(f))

    header, *data = rows
    n_concepts = len(HUMAN_CSV_CONCEPT_ORDER)

    # Forms layout: timestamp | (PI, reasoning) x N concepts | age | status | contact
    # PI columns: 1, 3, 5, 7, 9 ; reasoning columns: 2, 4, 6, 8, 10
    pi_cols = [1 + 2 * i for i in range(n_concepts)]
    reasoning_cols = [2 + 2 * i for i in range(n_concepts)]
    age_col = 1 + 2 * n_concepts          # = 11
    status_col = age_col + 1              # = 12

    out = {name: {"ratings": [], "reasoning": []} for name in HUMAN_CSV_CONCEPT_ORDER}
    ages = []
    statuses = []
    dropped = 0

    for row in data:
        if not row or not row[0].strip():
            continue
        # Robustness: skip rows with missing PI for any concept
        row_ratings = []
        valid = True
        for col in pi_cols:
            label = (row[col] or "").strip() if col < len(row) else ""
            if label not in LIKERT_MAP:
                valid = False
                break
            row_ratings.append(LIKERT_MAP[label])
        if not valid:
            dropped += 1
            continue

        for i, name in enumerate(HUMAN_CSV_CONCEPT_ORDER):
            out[name]["ratings"].append(row_ratings[i])
            txt = (row[reasoning_cols[i]] or "").strip()
            if txt:
                out[name]["reasoning"].append(txt)

        if age_col < len(row):
            a = (row[age_col] or "").strip()
            if a:
                ages.append(a)
        if status_col < len(row):
            s = (row[status_col] or "").strip()
            if s:
                statuses.append(s)

    out["_meta"] = {
        "n_respondents": len(out[HUMAN_CSV_CONCEPT_ORDER[0]]["ratings"]),
        "n_dropped": dropped,
        "age_breakdown": dict(Counter(ages)),
        "status_breakdown": dict(Counter(statuses)),
    }
    return out


# ---------------------------------------------------------------------------
# Synthetic data loading
# ---------------------------------------------------------------------------

def load_synthetic_results(synthetic_dir: Path) -> dict:
    """
    Load the 5 results.json files from synthetic_dir.

    Returns dict shaped like:
      {
        "concept_name": {
          "ratings": [float, ...],   # expected ratings (E[r]) per persona
          "pmf": {1: float, ...},    # aggregated PMF
          "mean": float,             # survey mean PI
          "n_respondents": int,
          "reasoning": [str, ...],
        },
        ...
      }
    """
    out = {}
    for subdir in synthetic_dir.iterdir():
        if not subdir.is_dir():
            continue
        results_path = subdir / "results.json"
        if not results_path.exists():
            continue
        key = subdir.name.lower()
        if key not in SYNTHETIC_DIR_TO_NAME:
            print(f"  warning: unknown synthetic dir '{subdir.name}', skipping", file=sys.stderr)
            continue
        concept_name = SYNTHETIC_DIR_TO_NAME[key]

        with open(results_path) as f:
            data = json.load(f)

        # Engagement may have multiple concepts in one results file — we expect 1.
        # Take the first concept regardless of its concept_id.
        concepts = data.get("concepts", {})
        if not concepts:
            print(f"  warning: no concepts found in {results_path}", file=sys.stderr)
            continue
        first_concept_key = next(iter(concepts))
        c = concepts[first_concept_key]

        ratings = [r["expected_rating"] for r in c["respondents"]]
        reasoning = [r.get("reasoning_response", "") for r in c["respondents"]]
        reasoning = [r for r in reasoning if r and r.strip()]

        # Aggregate PMF: average across all per-respondent averaged_pmfs.
        agg_pmf = {i: 0.0 for i in range(1, 6)}
        for r in c["respondents"]:
            for k, v in r["averaged_pmf"].items():
                agg_pmf[int(k)] += v
        n = len(c["respondents"])
        for k in agg_pmf:
            agg_pmf[k] /= n

        out[concept_name] = {
            "ratings": ratings,
            "pmf": agg_pmf,
            "mean": sum(ratings) / n if n > 0 else 0,
            "n_respondents": n,
            "reasoning": reasoning,
        }

    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def likert_distribution(ratings: list) -> dict:
    """Return PMF over 1-5 for a list of integer ratings."""
    counts = Counter(int(round(r)) for r in ratings)
    n = len(ratings)
    return {i: counts.get(i, 0) / n if n > 0 else 0 for i in range(1, 6)}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0


def std(xs):
    if len(xs) < 2:
        return 0
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def top_box(ratings, threshold=4):
    """% of ratings >= threshold (top-2-box if threshold=4)."""
    if not ratings:
        return 0
    return sum(1 for r in ratings if r >= threshold) / len(ratings)


def bottom_box(ratings, threshold=2):
    """% of ratings <= threshold (bottom-2-box if threshold=2)."""
    if not ratings:
        return 0
    return sum(1 for r in ratings if r <= threshold) / len(ratings)


def spearman_rank_correlation(x: list, y: list) -> float:
    """Spearman ρ for two lists of equal length."""
    if len(x) != len(y) or len(x) < 2:
        return float("nan")

    def ranks(vals):
        sorted_idx = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0] * len(vals)
        for rank, idx in enumerate(sorted_idx, 1):
            r[idx] = rank
        return r

    rx, ry = ranks(x), ranks(y)
    n = len(x)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - (6 * d2) / (n * (n ** 2 - 1))


def ks_distance(pmf_a: dict, pmf_b: dict) -> float:
    """Max absolute difference between cumulative distributions (lower is better)."""
    cum_a, cum_b = 0, 0
    max_diff = 0
    for k in range(1, 6):
        cum_a += pmf_a.get(k, 0)
        cum_b += pmf_b.get(k, 0)
        max_diff = max(max_diff, abs(cum_a - cum_b))
    return max_diff


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_distribution_overlay(human_pmf, synth_pmf, concept_name, out_path):
    """Side-by-side bar chart of human vs. synthetic Likert distribution."""
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = np.arange(1, 6)
    width = 0.38
    h = [human_pmf.get(i, 0) * 100 for i in x]
    ax.bar(x - width / 2, h, width, label="Human", color="#2C3E50", alpha=0.85)
    if synth_pmf is not None:
        s = [synth_pmf.get(i, 0) * 100 for i in x]
        ax.bar(x + width / 2, s, width, label="Synthetic", color="#E67E22", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(["1\nDef. not", "2\nProb. not", "3\nMaybe", "4\nProb. yes", "5\nDef. yes"], fontsize=8)
    ax.set_ylabel("% of respondents")
    ax.set_title(f"{concept_name}: Likert distribution", fontsize=11)
    ax.legend(fontsize=9, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_mean_comparison(concepts, human_means, synth_means, out_path):
    """Bar chart of mean PI per concept, human vs synthetic."""
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(concepts))
    width = 0.38
    ax.bar(x - width / 2, human_means, width, label="Human", color="#2C3E50", alpha=0.85)
    if synth_means is not None:
        ax.bar(x + width / 2, synth_means, width, label="Synthetic", color="#E67E22", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(concepts, fontsize=9)
    ax.set_ylabel("Mean Purchase Intent (1-5)")
    ax.set_ylim(1, 5)
    ax.axhline(3, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.set_title("Mean Purchase Intent by Concept", fontsize=11)
    ax.legend(fontsize=9, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_human_distribution(human_pmf, concept_name, out_path):
    """Single-series human-only Likert distribution."""
    fig, ax = plt.subplots(figsize=(5.5, 2.8))
    x = np.arange(1, 6)
    h = [human_pmf.get(i, 0) * 100 for i in x]
    ax.bar(x, h, color="#2C3E50", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(["1\nDef. not", "2\nProb. not", "3\nMaybe", "4\nProb. yes", "5\nDef. yes"], fontsize=8)
    ax.set_ylabel("% of respondents")
    ax.set_title(f"{concept_name}", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

def build_pdf_report(human, synthetic, output_path):
    """
    Build the PDF. If `synthetic` is None, generates a human-only report.
    """
    full_validation = synthetic is not None and len(synthetic) > 0

    # Working directory for chart PNGs
    plot_dir = Path(output_path).parent / "_plots"
    plot_dir.mkdir(exist_ok=True)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=8, spaceBefore=12)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=11, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    quote = ParagraphStyle("quote", parent=styles["BodyText"], fontSize=9, leading=12,
                           leftIndent=18, rightIndent=10, textColor=colors.HexColor("#444444"),
                           spaceAfter=4, italic=True)
    note = ParagraphStyle("note", parent=styles["BodyText"], fontSize=9, leading=12,
                          textColor=colors.HexColor("#666666"), spaceAfter=8)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75 * inch, leftMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    story = []

    # ----------------------------------------------------------------- Cover
    title = "Pilot Validation Report" if full_validation else "Human Survey Results"
    story.append(Paragraph(title, h1))
    subtitle = (
        "Synthetic SSR Pipeline vs. Real Human Responses"
        if full_validation
        else "Human Likert ratings — pre-validation summary"
    )
    story.append(Paragraph(subtitle, body))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y')}", note
    ))

    meta = human["_meta"]
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Sample</b>", h3))
    sample_lines = [
        f"Human respondents: <b>{meta['n_respondents']}</b>",
    ]
    if meta["n_dropped"]:
        sample_lines.append(f"Dropped (incomplete): {meta['n_dropped']}")
    age_str = ", ".join(f"{k}: {v}" for k, v in sorted(meta["age_breakdown"].items()))
    status_str = ", ".join(f"{k}: {v}" for k, v in sorted(meta["status_breakdown"].items()))
    if age_str:
        sample_lines.append(f"Age: {age_str}")
    if status_str:
        sample_lines.append(f"Status: {status_str}")
    if full_validation:
        synth_n = next(iter(synthetic.values()))["n_respondents"]
        sample_lines.append(f"Synthetic personas per concept: <b>{synth_n}</b>")
    for line in sample_lines:
        story.append(Paragraph(line, body))

    # ----------------------------------------------------- Caveats / methodology
    story.append(Paragraph("<b>What this report can and cannot tell you</b>", h3))
    if full_validation:
        story.append(Paragraph(
            "This is a <b>pilot validation</b>. With 5 concepts, statistical correlations have wide "
            "confidence intervals and should not be reported as precise figures. Read the ranking "
            "agreement and mean-tracking comparisons as directional evidence — they show whether the "
            "pipeline is broadly tracking human responses, not whether it has a specific accuracy %. "
            "Distributional and ranking concordance on this small N is a sanity check, not a benchmark.",
            body))
    else:
        story.append(Paragraph(
            "This is the human-only baseline. Synthetic pipeline results have not yet been compared. "
            "Use this report to inspect distribution shape, identify outlier concepts, and check that "
            "the spread of responses is wide enough to support a meaningful validation.",
            body))

    story.append(PageBreak())

    # ------------------------------------------------ Section: Top-line summary
    story.append(Paragraph("Top-line summary", h2))

    concepts = HUMAN_CSV_CONCEPT_ORDER
    human_means = [mean(human[c]["ratings"]) for c in concepts]
    human_stds = [std(human[c]["ratings"]) for c in concepts]
    human_pmfs = {c: likert_distribution(human[c]["ratings"]) for c in concepts}

    if full_validation:
        synth_means = [synthetic[c]["mean"] for c in concepts]
        synth_pmfs = {c: synthetic[c]["pmf"] for c in concepts}
    else:
        synth_means = None
        synth_pmfs = None

    # Mean comparison plot
    chart_path = plot_dir / "mean_comparison.png"
    plot_mean_comparison(concepts, human_means, synth_means, chart_path)
    story.append(RLImage(str(chart_path), width=6.8 * inch, height=3.5 * inch))

    # Summary table
    if full_validation:
        head = ["Concept", "Human Mean", "Synth Mean", "Δ", "Human Top-2-Box", "Synth Top-2-Box"]
        rows = []
        for c in concepts:
            h_mean = mean(human[c]["ratings"])
            s_mean = synthetic[c]["mean"]
            h_t2b = top_box(human[c]["ratings"]) * 100
            # synth top-2-box from PMF (since ratings are E[r] floats, use PMF directly)
            s_t2b = (synthetic[c]["pmf"][4] + synthetic[c]["pmf"][5]) * 100
            rows.append([
                c,
                f"{h_mean:.2f}",
                f"{s_mean:.2f}",
                f"{s_mean - h_mean:+.2f}",
                f"{h_t2b:.0f}%",
                f"{s_t2b:.0f}%",
            ])
    else:
        head = ["Concept", "Mean PI", "Std", "Top-2-Box", "Bottom-2-Box", "n"]
        rows = []
        for c in concepts:
            ratings = human[c]["ratings"]
            rows.append([
                c,
                f"{mean(ratings):.2f}",
                f"{std(ratings):.2f}",
                f"{top_box(ratings) * 100:.0f}%",
                f"{bottom_box(ratings) * 100:.0f}%",
                str(len(ratings)),
            ])

    tbl = Table([head] + rows, hAlign="LEFT", repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#2C3E50")),
    ]))
    story.append(Spacer(1, 8))
    story.append(tbl)

    # -------------------------------------------- Ranking agreement
    if full_validation:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Ranking agreement", h3))

        # Sort concepts by human mean (descending) and by synth mean
        h_rank_order = sorted(concepts, key=lambda c: -mean(human[c]["ratings"]))
        s_rank_order = sorted(concepts, key=lambda c: -synthetic[c]["mean"])
        spearman = spearman_rank_correlation(human_means, synth_means)

        story.append(Paragraph(
            f"Human ranking (best → worst): <b>{' &gt; '.join(h_rank_order)}</b>", body))
        story.append(Paragraph(
            f"Synthetic ranking (best → worst): <b>{' &gt; '.join(s_rank_order)}</b>", body))
        story.append(Paragraph(
            f"Spearman rank correlation: <b>ρ = {spearman:+.2f}</b>", body))

        # Top/bottom box agreement
        h_best = h_rank_order[0]
        s_best = s_rank_order[0]
        h_worst = h_rank_order[-1]
        s_worst = s_rank_order[-1]
        story.append(Paragraph(
            f"Best-concept agreement: human picked <b>{h_best}</b>, synthetic picked <b>{s_best}</b> "
            f"{'✓' if h_best == s_best else '✗'}",
            body))
        story.append(Paragraph(
            f"Worst-concept agreement: human picked <b>{h_worst}</b>, synthetic picked <b>{s_worst}</b> "
            f"{'✓' if h_worst == s_worst else '✗'}",
            body))

        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Spearman ρ = +1.0 means perfect ranking agreement; 0 means random; -1.0 means inverted. "
            "With n=5 concepts, ρ ≥ 0.80 is a strong directional signal but the confidence interval is wide.",
            note))

    story.append(PageBreak())

    # ---------------------------------------- Section: Per-concept breakdown
    for c in concepts:
        story.append(Paragraph(f"{c}", h2))

        # Distribution plot
        chart_path = plot_dir / f"dist_{c.lower()}.png"
        if full_validation:
            plot_distribution_overlay(human_pmfs[c], synth_pmfs[c], c, chart_path)
        else:
            plot_human_distribution(human_pmfs[c], c, chart_path)

        # Stats table
        if full_validation:
            ks = ks_distance(human_pmfs[c], synth_pmfs[c])
            stats_rows = [
                ["Metric", "Human", "Synthetic"],
                ["Mean PI", f"{mean(human[c]['ratings']):.2f}", f"{synthetic[c]['mean']:.2f}"],
                ["Std", f"{std(human[c]['ratings']):.2f}", f"{std(synthetic[c]['ratings']):.2f}"],
                ["Top-2-Box %", f"{top_box(human[c]['ratings']) * 100:.0f}%",
                 f"{(synth_pmfs[c][4] + synth_pmfs[c][5]) * 100:.0f}%"],
                ["Bottom-2-Box %", f"{bottom_box(human[c]['ratings']) * 100:.0f}%",
                 f"{(synth_pmfs[c][1] + synth_pmfs[c][2]) * 100:.0f}%"],
                ["KS distance", "—", f"{ks:.3f}"],
                ["n", str(len(human[c]["ratings"])), str(synthetic[c]["n_respondents"])],
            ]
        else:
            stats_rows = [
                ["Metric", "Value"],
                ["Mean PI", f"{mean(human[c]['ratings']):.2f}"],
                ["Std", f"{std(human[c]['ratings']):.2f}"],
                ["Top-2-Box %", f"{top_box(human[c]['ratings']) * 100:.0f}%"],
                ["Bottom-2-Box %", f"{bottom_box(human[c]['ratings']) * 100:.0f}%"],
                ["n", str(len(human[c]["ratings"]))],
            ]

        stats_tbl = Table(stats_rows, hAlign="LEFT", colWidths=[1.6 * inch] + [1.2 * inch] * (len(stats_rows[0]) - 1))
        stats_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
        ]))

        # Side-by-side: chart + stats
        chart_img = RLImage(str(chart_path), width=4.0 * inch, height=2.3 * inch)
        side_by_side = Table([[chart_img, stats_tbl]], colWidths=[4.2 * inch, 2.7 * inch])
        side_by_side.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(side_by_side)
        story.append(Spacer(1, 8))

        # Sample human reasoning quotes (up to 3)
        story.append(Paragraph("<b>Sample human responses</b>", h3))
        rsp = human[c]["reasoning"]
        sample = rsp[:3] if len(rsp) <= 3 else _pick_diverse_quotes(human[c]["ratings"], rsp, 3)
        for q in sample:
            # Clean up quotes — strip newlines, escape angle brackets for reportlab
            q_clean = q.replace("\n", " ").replace("\r", " ").strip()
            q_clean = q_clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f"&ldquo;{q_clean}&rdquo;", quote))

        if full_validation and synthetic[c]["reasoning"]:
            story.append(Spacer(1, 4))
            story.append(Paragraph("<b>Sample synthetic reasoning</b>", h3))
            for q in synthetic[c]["reasoning"][:3]:
                q_clean = q.replace("\n", " ").replace("\r", " ").strip()[:400]
                q_clean = q_clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(f"&ldquo;{q_clean}&rdquo;", quote))

        story.append(PageBreak())

    # ----------------------------------------------- Methodology footnote
    story.append(Paragraph("Methodology notes", h2))
    story.append(Paragraph(
        f"Likert ratings collected via Google Forms ({meta['n_respondents']} respondents). "
        f"Concept order in the form: {', '.join(HUMAN_CSV_CONCEPT_ORDER)}. "
        f"Likert label mapping: 'Definitely would not buy' = 1 through 'Definitely would buy' = 5.",
        body))
    if full_validation:
        story.append(Paragraph(
            "Synthetic results from the SSR pipeline. Per-respondent expected ratings (E[r]) computed by "
            "averaging PMFs across 6 reference sets. Per-concept aggregate PMFs computed by averaging "
            "individual PMFs. KS distance is the max absolute difference between cumulative distributions "
            "(0 = identical, 1 = no overlap).",
            body))
    story.append(Paragraph(
        "Limitations: small concept sample (n=5) makes precise correlation statistics unreliable. "
        "Ranking agreement and directional mean tracking are the primary signals. "
        "Human respondents were a friend/follower convenience sample — not a representative consumer panel.",
        note))

    doc.build(story)
    print(f"Wrote {output_path}")


def _pick_diverse_quotes(ratings, reasonings, n=3):
    """Pick quotes spanning low / mid / high Likert ratings."""
    paired = list(zip(ratings, reasonings))
    paired.sort(key=lambda p: p[0])
    if len(paired) <= n:
        return [p[1] for p in paired]
    idxs = [0, len(paired) // 2, len(paired) - 1]
    return [paired[i][1] for i in idxs]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Validate SSR pipeline against human survey data.")
    p.add_argument("--human", required=True, help="Path to Google Forms CSV export")
    p.add_argument("--synthetic-dir", default=None,
                   help="Directory containing per-concept synthetic results subdirs (optional)")
    p.add_argument("--output", default="validation_report.pdf", help="Output PDF path")
    args = p.parse_args()

    human_path = Path(args.human)
    if not human_path.exists():
        sys.exit(f"Error: human CSV not found at {human_path}")

    print(f"Loading human responses from {human_path}...")
    human = load_human_responses(human_path)
    print(f"  {human['_meta']['n_respondents']} respondents loaded "
          f"({human['_meta']['n_dropped']} dropped)")

    synthetic = None
    if args.synthetic_dir:
        synth_path = Path(args.synthetic_dir)
        if not synth_path.exists():
            sys.exit(f"Error: synthetic dir not found at {synth_path}")
        print(f"Loading synthetic results from {synth_path}...")
        synthetic = load_synthetic_results(synth_path)
        if len(synthetic) != len(HUMAN_CSV_CONCEPT_ORDER):
            print(f"  warning: expected {len(HUMAN_CSV_CONCEPT_ORDER)} concepts, "
                  f"found {len(synthetic)} ({list(synthetic.keys())})", file=sys.stderr)
        for c in synthetic:
            print(f"  {c}: {synthetic[c]['n_respondents']} personas, mean={synthetic[c]['mean']:.2f}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_pdf_report(human, synthetic, output_path)


if __name__ == "__main__":
    main()
