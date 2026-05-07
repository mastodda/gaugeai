#!/usr/bin/env python3
"""
analyze_set_bias.py — Decompose synthetic mean PI by SSR reference set.

For each (concept, reference_set) pair, computes the synthetic mean PI
implied by that single set in isolation. Compares each set's mean against
the human ground truth to identify which sets contribute most positivity bias.

This helps answer: "Are some reference sets systematically overshooting human
PI more than others? If so, can we drop or down-weight them?"

Usage:
    python analyze_set_bias.py \
        --human human_responses.csv \
        --synthetic-dir runs/ \
        --output set_bias_report.pdf

Output:
    - PDF report with per-set bias breakdown
    - Console summary of per-set offsets vs. human ground truth

Notes:
    - Reads `per_set_pmfs` from each respondent in results.json
    - Per-set mean PI = E[r] computed from that set's PMF only (no averaging)
    - Per-set bias for concept C, set S = mean(synthetic_S, C) - mean(human, C)
"""

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak,
)

# Reuse loaders from validate.py
sys.path.insert(0, str(Path(__file__).parent))
from validate import (
    load_human_responses,
    load_synthetic_results,
    HUMAN_CSV_CONCEPT_ORDER,
    SYNTHETIC_DIR_TO_NAME,
    mean as _mean,
)
import json


# ---------------------------------------------------------------------------
# Per-set aggregation
# ---------------------------------------------------------------------------

def load_per_set_pmfs(synthetic_dir: Path) -> dict:
    """
    Load per-set PMFs from each concept's results.json.

    Returns:
      {
        concept_name: {
          set_name: {
            "mean_pi": float,           # E[r] across all respondents using only this set
            "pmf": {1: p, ..., 5: p},   # avg PMF across respondents using only this set
            "n": int,
          },
          ...
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
            continue
        concept_name = SYNTHETIC_DIR_TO_NAME[key]

        with open(results_path) as f:
            data = json.load(f)

        first_concept_key = next(iter(data["concepts"]))
        respondents = data["concepts"][first_concept_key]["respondents"]
        if not respondents:
            continue

        # Discover set names from the first respondent
        set_names = list(respondents[0]["per_set_pmfs"].keys())

        per_set = {}
        for s in set_names:
            agg_pmf = {i: 0.0 for i in range(1, 6)}
            ratings = []
            for r in respondents:
                pmf = r["per_set_pmfs"][s]
                # Per-respondent expected rating from this set alone
                er = sum(int(k) * v for k, v in pmf.items())
                ratings.append(er)
                for k, v in pmf.items():
                    agg_pmf[int(k)] += v
            n = len(respondents)
            for k in agg_pmf:
                agg_pmf[k] /= n
            per_set[s] = {
                "mean_pi": sum(ratings) / n,
                "pmf": agg_pmf,
                "n": n,
            }

        out[concept_name] = per_set
    return out


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_per_set_bias(human_means_by_concept, per_set_data, out_path):
    """
    Heatmap-style chart: rows = concepts, cols = sets, values = bias (synth - human).
    Color: red = positive bias (overshooting), blue = negative.
    """
    concepts = list(human_means_by_concept.keys())
    set_names = list(next(iter(per_set_data.values())).keys())

    # Bias matrix
    M = np.zeros((len(concepts), len(set_names)))
    for i, c in enumerate(concepts):
        for j, s in enumerate(set_names):
            M[i, j] = per_set_data[c][s]["mean_pi"] - human_means_by_concept[c]

    fig, ax = plt.subplots(figsize=(9, 0.7 * len(concepts) + 1.5))
    vmax = max(abs(M.min()), abs(M.max()), 0.5)
    im = ax.imshow(M, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(set_names)))
    ax.set_xticklabels([s.replace("set_", "").replace("_", "\n") for s in set_names],
                       fontsize=8)
    ax.set_yticks(range(len(concepts)))
    ax.set_yticklabels(concepts, fontsize=9)

    # Annotate cells with bias values
    for i in range(len(concepts)):
        for j in range(len(set_names)):
            v = M[i, j]
            txt_color = "white" if abs(v) > vmax * 0.6 else "black"
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center",
                    fontsize=8, color=txt_color)

    cbar = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Bias (synth − human)", fontsize=9)
    ax.set_title("Per-Set Bias: Synthetic Mean PI Minus Human Mean PI", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_per_set_means_per_concept(human_means_by_concept, per_set_data, out_path):
    """
    Grouped bar chart: per-concept, show one bar per reference set + human ground truth.
    """
    concepts = list(human_means_by_concept.keys())
    set_names = list(next(iter(per_set_data.values())).keys())
    n_sets = len(set_names)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = np.arange(len(concepts))
    width = 0.8 / (n_sets + 1)

    # Color palette for sets — distinct per set
    colors_list = plt.cm.tab10(np.linspace(0, 1, n_sets))

    # Human ground truth bar (leftmost)
    h_vals = [human_means_by_concept[c] for c in concepts]
    ax.bar(x - 0.4 + width / 2, h_vals, width, label="Human (truth)",
           color="#2C3E50", edgecolor="black", linewidth=0.5)

    for j, s in enumerate(set_names):
        vals = [per_set_data[c][s]["mean_pi"] for c in concepts]
        offset = -0.4 + width / 2 + (j + 1) * width
        ax.bar(x + offset, vals, width,
               label=s.replace("set_", "").replace("_", " "),
               color=colors_list[j], alpha=0.9)

    ax.set_xticks(x)
    ax.set_xticklabels(concepts, fontsize=9)
    ax.set_ylabel("Mean Purchase Intent (1-5)")
    ax.set_ylim(1, 5)
    ax.axhline(3, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.set_title("Mean PI by Reference Set vs. Human Ground Truth", fontsize=11)
    ax.legend(fontsize=8, frameon=False, ncol=2, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_set_avg_bias(per_set_avg_bias, out_path):
    """Bar chart of average bias per reference set (averaged across concepts)."""
    sets = list(per_set_avg_bias.keys())
    biases = list(per_set_avg_bias.values())
    fig, ax = plt.subplots(figsize=(8, 3.5))
    bar_colors = ["#C0392B" if b > 0 else "#2980B9" for b in biases]
    ax.bar(range(len(sets)), biases, color=bar_colors, alpha=0.9)
    ax.set_xticks(range(len(sets)))
    ax.set_xticklabels([s.replace("set_", "").replace("_", "\n") for s in sets],
                       fontsize=8)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("Avg bias across concepts (Likert points)")
    ax.set_title("Average Per-Set Positivity Bias", fontsize=11)
    for i, v in enumerate(biases):
        ax.text(i, v + (0.02 if v >= 0 else -0.05), f"{v:+.2f}",
                ha="center", fontsize=9, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------

def simulate_dropping_set(per_set_data, human_means_by_concept, drop_set):
    """
    Recompute the averaged mean PI per concept if we drop `drop_set`.
    Returns dict of {concept: new_mean_pi} and overall avg bias.
    """
    new_means = {}
    for c, sets in per_set_data.items():
        kept_means = [v["mean_pi"] for s, v in sets.items() if s != drop_set]
        new_means[c] = sum(kept_means) / len(kept_means) if kept_means else 0
    avg_bias = sum(new_means[c] - human_means_by_concept[c] for c in new_means) / len(new_means)
    return new_means, avg_bias


def rank_after_dropping(per_set_data, drop_set):
    """Compute ranking of concepts using all sets except `drop_set`."""
    new_means = {}
    for c, sets in per_set_data.items():
        kept_means = [v["mean_pi"] for s, v in sets.items() if s != drop_set]
        new_means[c] = sum(kept_means) / len(kept_means) if kept_means else 0
    return sorted(new_means.keys(), key=lambda c: -new_means[c])


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

def build_pdf(human, per_set_data, output_path):
    plot_dir = Path(output_path).parent / "_plots_bias"
    plot_dir.mkdir(exist_ok=True)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=8, spaceBefore=14)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=11, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)
    note = ParagraphStyle("note", parent=styles["BodyText"], fontSize=9, leading=12,
                          textColor=colors.HexColor("#666666"), spaceAfter=8)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=letter,
        rightMargin=0.75 * inch, leftMargin=0.75 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    story = []

    # ------------------------------------------------------------------ Cover
    story.append(Paragraph("Per-Set Bias Analysis", h1))
    story.append(Paragraph(
        "Decomposing synthetic positivity bias by SSR reference set.", body))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y')}", note))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>What this report does.</b> The pipeline averages PMFs across 6 reference sets "
        "to produce its final Likert distribution. This analysis breaks that average apart "
        "and shows what each set <i>individually</i> would have produced. Sets that overshoot "
        "human ground truth more than others are candidates to drop or down-weight.", body))

    human_means = {c: _mean(human[c]["ratings"]) for c in HUMAN_CSV_CONCEPT_ORDER}
    set_names = list(next(iter(per_set_data.values())).keys())

    # -------------------------------------------------- Section 1: heatmap
    story.append(Paragraph("Bias matrix", h2))
    heatmap_path = plot_dir / "bias_heatmap.png"
    plot_per_set_bias(human_means, per_set_data, heatmap_path)
    story.append(RLImage(str(heatmap_path), width=6.8 * inch, height=3.0 * inch))
    story.append(Paragraph(
        "Cells show <b>synthetic_set_mean − human_mean</b> for each (concept, set) pair. "
        "Red = synthetic overshoots human; blue = synthetic undershoots. Larger absolute "
        "values = stronger bias.", note))

    # -------------------------------------- Section 2: grouped bars
    story.append(Paragraph("Per-set means vs. human ground truth", h2))
    grouped_path = plot_dir / "grouped_means.png"
    plot_per_set_means_per_concept(human_means, per_set_data, grouped_path)
    story.append(RLImage(str(grouped_path), width=7.0 * inch, height=3.2 * inch))

    # -------------------------------------- Section 3: avg bias per set
    story.append(PageBreak())
    story.append(Paragraph("Average bias by reference set", h2))

    per_set_avg_bias = {}
    for s in set_names:
        biases = [per_set_data[c][s]["mean_pi"] - human_means[c] for c in human_means]
        per_set_avg_bias[s] = sum(biases) / len(biases)

    avg_bias_path = plot_dir / "avg_bias.png"
    plot_set_avg_bias(per_set_avg_bias, avg_bias_path)
    story.append(RLImage(str(avg_bias_path), width=7.0 * inch, height=3.0 * inch))

    # Sort sets worst → best
    sorted_sets = sorted(per_set_avg_bias.items(), key=lambda kv: -kv[1])
    rows = [["Reference Set", "Avg Bias (Likert pts)", "Verdict"]]
    for s, b in sorted_sets:
        verdict = ("Worst overshooter" if b == sorted_sets[0][1]
                   else "Mildest" if b == sorted_sets[-1][1]
                   else "")
        rows.append([s.replace("set_", ""), f"{b:+.2f}", verdict])
    tbl = Table(rows, hAlign="LEFT", colWidths=[2.6 * inch, 1.4 * inch, 1.6 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    story.append(Spacer(1, 4))
    story.append(tbl)

    # -------------------------------------- Section 4: drop simulation
    story.append(Paragraph("Drop-one simulation", h2))
    story.append(Paragraph(
        "What happens to mean bias and ranking if we drop a single reference set "
        "and average the remaining 5?", body))

    # Baseline: avg bias using all sets
    baseline_means = {c: _mean([per_set_data[c][s]["mean_pi"] for s in set_names])
                      for c in human_means}
    baseline_bias = sum(baseline_means[c] - human_means[c] for c in human_means) / len(human_means)
    baseline_rank = sorted(human_means.keys(), key=lambda c: -baseline_means[c])
    human_rank = sorted(human_means.keys(), key=lambda c: -human_means[c])

    drop_rows = [["Dropped Set", "New Avg Bias", "Δ vs Baseline", "Ranking Preserved?"]]
    drop_rows.append(["(none — baseline)", f"{baseline_bias:+.2f}", "—",
                      "✓" if baseline_rank == human_rank else f"✗ ({' > '.join(baseline_rank)})"])
    for s, _ in sorted_sets:
        new_means, new_bias = simulate_dropping_set(per_set_data, human_means, s)
        new_rank = sorted(new_means.keys(), key=lambda c: -new_means[c])
        delta = new_bias - baseline_bias
        rank_check = "✓" if new_rank == human_rank else f"✗ ({' > '.join(new_rank)})"
        drop_rows.append([
            s.replace("set_", ""),
            f"{new_bias:+.2f}",
            f"{delta:+.2f}",
            rank_check,
        ])

    drop_tbl = Table(drop_rows, hAlign="LEFT",
                     colWidths=[2.4 * inch, 1.2 * inch, 1.2 * inch, 2.0 * inch])
    drop_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    story.append(Spacer(1, 4))
    story.append(drop_tbl)

    # -------------------------------------- Section 5: per-concept detail
    story.append(PageBreak())
    story.append(Paragraph("Per-concept detail", h2))
    for c in HUMAN_CSV_CONCEPT_ORDER:
        story.append(Paragraph(c, h3))
        h_mean = human_means[c]
        rows = [["Reference Set", "Mean PI", "Bias vs Human"]]
        rows.append(["Human (truth)", f"{h_mean:.2f}", "—"])
        for s in set_names:
            sm = per_set_data[c][s]["mean_pi"]
            rows.append([s.replace("set_", ""), f"{sm:.2f}", f"{sm - h_mean:+.2f}"])
        rows.append(["Avg of all 6 sets",
                     f"{baseline_means[c]:.2f}",
                     f"{baseline_means[c] - h_mean:+.2f}"])
        ct = Table(rows, hAlign="LEFT", colWidths=[2.6 * inch, 1.2 * inch, 1.4 * inch])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 2), (-1, -2), [colors.white, colors.HexColor("#F5F5F5")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FFF3CD")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
        ]))
        story.append(ct)
        story.append(Spacer(1, 10))

    # -------------------------------------- Section 6: recommendations
    story.append(PageBreak())
    story.append(Paragraph("Recommendations", h2))

    worst_set, worst_bias = sorted_sets[0]
    best_set, best_bias = sorted_sets[-1]
    spread = worst_bias - best_bias

    if spread < 0.15:
        rec = (f"All 6 sets show similar positivity bias (range = {spread:.2f} Likert pts). "
               "Dropping individual sets will not meaningfully reduce the offset. The bias is "
               "<b>systematic across all sets</b>, which points to model/persona-level fixes "
               "(Tier 2 personas, lower LLM temp, model swap) rather than reference-set tuning.")
    elif spread < 0.4:
        rec = (f"Moderate spread across sets ({spread:.2f} Likert pts). "
               f"<b>{worst_set.replace('set_', '')}</b> overshoots most ({worst_bias:+.2f}); "
               f"<b>{best_set.replace('set_', '')}</b> is closest to human truth ({best_bias:+.2f}). "
               "Consider down-weighting the worst offenders rather than dropping outright. "
               "The bigger lever remains Tier 2 personas.")
    else:
        rec = (f"Large spread across sets ({spread:.2f} Likert pts). "
               f"<b>{worst_set.replace('set_', '')}</b> is a clear outlier ({worst_bias:+.2f} bias). "
               "Try dropping it and re-running the average. This may meaningfully reduce "
               "positivity bias without requiring a full pipeline re-run.")
    story.append(Paragraph(rec, body))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>What this analysis can't tell you.</b> Per-set bias is computed against this single "
        "5-concept pilot. Set-level fixes that work here may not generalize to other categories "
        "or demographics. Don't permanently drop sets based on one validation run — instead, treat "
        "this as a hypothesis to test against your next validation study.", note))

    doc.build(story)

    # Console summary
    print("\n=== Per-set average bias (worst → mildest) ===")
    for s, b in sorted_sets:
        print(f"  {s:<35} {b:+.3f}")
    print(f"\nBaseline (all 6 sets) avg bias: {baseline_bias:+.3f}")
    print(f"Spread between worst and mildest: {spread:.3f} Likert pts")
    print(f"\nWrote {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--human", required=True)
    p.add_argument("--synthetic-dir", required=True)
    p.add_argument("--output", default="set_bias_report.pdf")
    args = p.parse_args()

    human = load_human_responses(Path(args.human))
    print(f"Loaded {human['_meta']['n_respondents']} human respondents.")

    per_set_data = load_per_set_pmfs(Path(args.synthetic_dir))
    if not per_set_data:
        sys.exit("Error: no synthetic data loaded.")
    print(f"Loaded per-set PMFs for {len(per_set_data)} concepts: {list(per_set_data.keys())}")
    n_sets = len(next(iter(per_set_data.values())))
    print(f"Reference sets: {n_sets}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(human, per_set_data, output_path)


if __name__ == "__main__":
    main()
