# Pipeline Validation Handoff

**Date:** April 30, 2026
**Status:** Pilot validation complete (1 of N studies)
**Author:** Initial validation pilot

---

## 1. What this document is

A consolidated record of the first human-vs-synthetic validation study run against the SSR pipeline. Captures: methodology, results, tuning experiments, conclusions, and open questions. Intended as the working reference for future validation rounds and for any client-facing claims about pipeline accuracy.

If you're picking this up cold, read sections 2 (TL;DR), 5 (key findings), and 8 (recommended methodology) first.

---

## 2. TL;DR

- Ran 5 product concepts through the pipeline and surveyed 33 real humans (22-26, young professionals/students) on the same concepts.
- **Best configuration achieved ρ = 1.0 ranking agreement** with humans. Best and worst concept identified correctly.
- **All configurations show ~+1.0 Likert positivity bias** (synthetic mean PI is consistently higher than human mean PI). This appears to be structural to LLM-as-respondent, not a tuning artifact.
- Tuning experiments tried (per-set reweighting, Tier 2 personas, image+text stimulus) did **not** reliably reduce bias, and image+text actually broke ranking.
- **Defensible claim:** ranking is reliable, absolute scores are biased upward, methodology is appropriate for **directional** concept comparison, not absolute PI prediction.
- **Not defensible:** quoting a specific correlation %, claiming bias-free synthetic data, generalizing this single pilot's results.

---

## 3. Study design

### Concepts (5 total)

Designed for spread across appeal, category, and price tier. All AI-generated images with invented brand names (no real-brand contamination).

| Concept | Category | Price | Designed Role |
|---|---|---|---|
| Kindling | Cold brew concentrate | $18 | Safe-bet winner |
| Hearth | Adaptogenic sparkling tonic | $6.50/can | Polarizing premium |
| DailyOne | Multivitamin | $22.99 | Deliberately boring |
| Graze | Savory protein ice cream | $8.99 | Weird/novel |
| Halden | Linen work shirt | $148 | Aspirational lifestyle |

### Human survey

- Google Forms, 33 respondents (target was 50, 30 floor)
- Demographic skew: 32/33 in 22-26 range; 25/33 working full-time
- Recruitment: convenience sample (friends/Instagram followers)
- Per concept: 5-point Likert PI question + open-text reasoning
- Anonymity: contact info collected separately for $50 gift card raffle (not linked to responses)
- Likert label mapping: "Definitely would not buy"=1 → "Definitely would buy"=5

### Synthetic pipeline runs

- 5 separate engagements (one per concept) for clean isolation
- 100 personas per run, demographically matched to human respondents
- Default config: GPT-4o, T_LLM=0.5, T_SSR=0.5, ε=0.0, all 6 reference sets averaged
- Tier 1 personas (paper-validated baseline) unless noted
- Image stimulus: AI-generated product photo (initially image-only, later image+text tested)

---

## 4. Headline results

### Image-only stimulus, Tier 1 personas (chosen configuration)

| Concept | Human Mean | Synth Mean | Δ | Human T2B | Synth T2B |
|---|---|---|---|---|---|
| Graze | 3.06 | 3.81 | +0.75 | 39% | 66% |
| Hearth | 2.15 | 3.49 | +1.34 | 18% | 55% |
| Kindling | 2.73 | 3.68 | +0.95 | 30% | 61% |
| DailyOne | 2.64 | 3.54 | +0.91 | 21% | 56% |
| Halden | 2.36 | 3.53 | +1.17 | 18% | 54% |

**Ranking agreement (Spearman ρ): +1.00**
- Human ranking: Graze > Kindling > DailyOne > Halden > Hearth
- Synthetic ranking: identical
- Best-concept and worst-concept agreement: ✓ both correct

**Average mean PI bias: +1.02 Likert points** (synthetic systematically higher)

---

## 5. Key findings

### 5.1 Ranking signal is robust; absolute calibration is not

The pipeline's relative ordering is reliable at 5 concepts. The absolute PI numbers are inflated by ~1 Likert point. **For client work, this means:**
- Ranking concepts is supported by validation evidence
- Quoting specific PI numbers (e.g., "your concept scored 3.8/5") is overclaiming without correction
- Top-2-box percentages are similarly inflated and should not be quoted absolutely

### 5.2 Positivity bias is structural, not tunable (within the current paper-faithful methodology)

We tested four hypotheses for reducing the +1.0 bias. None worked meaningfully:

| Experiment | Result | Conclusion |
|---|---|---|
| Per-set bias analysis & drop-one simulation | Spread of 0.53 across 6 sets; dropping worst set reduced bias by only 0.03 | Set-level pruning is a dead end |
| Tier 2 personas (Hearth) | +0.18 PI vs Tier 1 (worse) | Richer personas → more enthusiastic LLM, not more skeptical |
| Image+text stimulus (all 5) | Bias dropped on 4/5 concepts BUT ranking broke (ρ = −0.10) | Pipeline becomes hyper-sensitive to marketing register of description text |
| Reference set tuning (informal) | Marginal | Not worth the overfitting risk on this small a dataset |

The remaining untested levers — model swap (Claude/Gemini), lower LLM temperature, adversarial system prompts — are individually plausible but not collectively expected to close a +1.0 gap. **Treat the bias as a known offset, not a bug to fix.**

### 5.3 The pipeline reacts to marketing language differently than humans do

The image+text experiment surfaced this. When concept descriptions contained wellness-marketing language ("adaptogenic," "calm focus," "ethically sourced"), synthetic responses became more positive while human responses (in this demographic) became more skeptical. Hearth — the most marketing-dense concept — was the one that didn't drop in the image+text run; it actually went up.

**This is the most important methodological finding for client work.** Description style is now a known confound. Two concepts with identical underlying products but different marketing registers will receive different synthetic scores. Mitigation options:

- **Standardize descriptions** before ingestion (factual specs only, strip marketing copy)
- **Run dual ablation** (with and without marketing copy) and report the range
- **Document the limitation** in client deliverables

### 5.4 Demographics matter more than they appear to

The pipeline is producing responses that resemble *generic positive consumer reactions*, not 22-26 young professional skepticism. Real responses included:
- "Seems holistic / fake" (Hearth)
- "Not my style and it's expensive" (Halden)
- "Don't drink coffee" (Kindling)
- "Don't use multivitamins" (DailyOne)

These are **identity-based and price-based rejections** that the LLM-as-respondent does not naturally produce, even with matched demographic personas. This is a known limitation of LLM survey synthesis for narrow/younger demographics — the paper validated against a representative US panel, where this issue is averaged out across diverse respondents.

---

## 6. What the data does NOT support

To prevent overclaiming in future client work, here are claims that **cannot** be made from this pilot:

| Claim | Why it's not supported |
|---|---|
| "Our pipeline achieves 90% correlation with humans" | Maier paper computed ρ=90% across ~30 surveys. Our pilot has 5 concepts. ρ on n=5 has CI ≈ ±0.5. |
| "Validated against real consumer data" | 33 friend/follower convenience sample is not a consumer panel |
| "Bias-free synthetic survey results" | +1.0 Likert positivity bias confirmed across all configurations |
| "Works for any product category" | Validated against 5 lifestyle products in one demographic. Generalization untested. |
| "Replaces traditional concept testing" | Should be positioned as a directional pre-screen, not a replacement |

**Defensible claims:**

- "Methodology based on peer-reviewed research (Maier et al.)"
- "Reliable ordinal ranking of concepts within an engagement"
- "Pilot validation against 33 real consumers showed perfect 5-of-5 ranking agreement"
- "Synthetic scores show systematic positivity bias; we report relative comparisons rather than absolute PI"

---

## 7. Tuning experiments — full record

For future iteration, here's what was tried and what happened. Don't repeat these on this dataset; pick them up only if a future validation surfaces the same problem.

### Per-set bias analysis (no re-runs needed; uses cached PMFs)
- Reference set 6 (`personal_fit`) had lowest bias (+0.66 avg vs +1.0+ for others)
- Most pronounced advantage on identity-rejection concepts (Hearth, Halden)
- Drop-one simulation: removing any single set changes avg bias by ≤0.07 points
- **Decision:** keep all 6 sets averaged. No reweighting until a multi-study pattern emerges.

### Tier 2 personas (re-run on Hearth only)
- Mean PI went **up** by +0.18, not down
- Hypothesis (richer personas → more identity-based rejection) failed
- Likely mechanism: Tier 2 lifestyle attributes are LLM-generated caricatures (e.g., "wellness-oriented" personas built by an LLM are uniformly enthusiastic), missing real-person ambivalence
- **Decision:** Tier 1 remains default for scoring. Tier 2 is still useful for qualitative reasoning generation (different goal).

### Image+text stimulus (re-ran all 5 concepts)
- Hypothesis: humans saw price/description, synthetics didn't, so adding text would close the gap
- Result: 4/5 concepts dropped (good), but Hearth rose (+0.13) and ranking inverted (ρ=−0.10)
- Halden dropped most (−0.31) — consistent with finally seeing the $148 price
- Hearth rose because text contained marketing-dense language the LLM finds appealing
- **Decision:** revert to image-only as default. Document marketing-language sensitivity as known confound.

### Not yet tested (potential future experiments)
- Model swap (Claude Sonnet 4.6, Gemini 2.5 Flash) — different RLHF baseline positivity
- Lower LLM temperature (0.3 instead of 0.5) — less enthusiastic free-text
- Adversarial system prompt ("you are skeptical by default")
- Description normalization (strip marketing language before ingestion)
- Custom reference sets for younger demographics

---

## 8. Recommended methodology going forward

### For the next validation pilot

1. **Different category, similar rigor.** Don't re-validate on the same 5 concepts. Pick a different product category and ideally a different demographic to test generalization.
2. **Same configuration as this pilot:** GPT-4o, Tier 1 personas, image-only stimulus, T_LLM=0.5, T_SSR=0.5, ε=0.0, all 6 reference sets.
3. **Run both configurations** (image-only AND image+text) on the next pilot to settle the stimulus question.
4. **Aim for 50+ human respondents.** 33 was workable for ranking but tight for distribution analysis.
5. **Pick concepts with deliberately wide appeal spread.** Watch for compressed human distributions (this pilot's full range was only 2.15-3.06, which made middle-rankings statistically tied).
6. **Log per-concept bias.** Across ~5 pilots you'll have a stable estimate of typical offset for calibration.

### For client engagements (now)

1. **Default config:** Tier 1 personas, image-only stimulus, GPT-4o, paper defaults.
2. **Report rankings, not absolute PI.** Show "concept A ranked 1st of 5" or "concept A scored 0.6 points higher than concept B."
3. **Standardize concept descriptions** when ingesting client materials. Strip marketing copy down to factual specs to reduce style-sensitivity confound.
4. **Frame as directional pre-screen**, not as a replacement for human research. Recommended language: "synthetic concept screening to identify likely winners/losers before committing to full human research."
5. **Disclose limitations** in deliverables: small-N validation history, marketing-language sensitivity, demographic boundaries.

### What to NOT do

- Do not claim a specific correlation coefficient until 20+ concepts of validation data are accumulated
- Do not present absolute PI scores as predictive of human PI
- Do not over-tune the pipeline against any single validation dataset (overfitting risk is real)
- Do not test new tuning hypotheses on the existing 5 concepts — fresh data only

---

## 9. Open questions for future work

1. **Does the +1.0 bias generalize across categories?** Test on a B2B/utility category (e.g., software, household goods) where human responses may be less identity-driven.
2. **Does ranking hold on a more representative sample?** Recruit a paid panel (e.g., Prolific, n=100, demographically diverse US) for the next pilot.
3. **Can description normalization remove the marketing-language confound?** Run an A/B with marketing-rich vs factual descriptions across the same concepts.
4. **Model-level positivity differences.** Run the same concepts through Claude Sonnet 4.6 and Gemini 2.5 Flash. Document which model best matches human ground truth for the working demographic.
5. **Calibration layer.** After 3+ pilots, build a simple offset-correction step: subtract the empirically-measured per-category bias from synthetic outputs before reporting.
6. **Hybrid persona scoring (mentioned in original handoff).** Tier 1 for SSR scoring, Tier 2 for reasoning generation. Worth implementing once the scoring methodology is locked in.

---

## 10. Files and artifacts

| File | Purpose |
|---|---|
| `validate.py` | Main validation script. Ingests human CSV + synthetic results.json files, generates PDF report. Two modes: human-only and full validation. |
| `analyze_set_bias.py` | Per-set bias decomposition. Uses cached PMFs from results.json — no API calls. Generates separate PDF report. |
| `human_responses.csv` | Google Forms export, 33 respondents, 5 concepts |
| `runs/` | Per-concept synthetic results (5 subdirs, each with results.json) |
| `validation_report.pdf` | Output of validate.py — top-line, ranking, per-concept distributions |
| `set_bias_report.pdf` | Output of analyze_set_bias.py — per-set bias breakdown |

### Reproducing the pilot

```bash
# Human-only baseline
python validate.py --human human_responses.csv --output report_human.pdf

# Full validation (after 5 pipeline runs)
python validate.py \
    --human human_responses.csv \
    --synthetic-dir runs/ \
    --output validation_report.pdf

# Per-set bias decomposition
python analyze_set_bias.py \
    --human human_responses.csv \
    --synthetic-dir runs/ \
    --output set_bias_report.pdf
```

---

## 11. Honest framing for the project

The pipeline does what it claims to do at the level the validation supports: it produces a **directional, ordinal signal** about which concepts will perform better than others. It does **not** produce calibrated absolute predictions of human PI, and pretending otherwise is the failure mode that would hurt the product most.

The right product positioning is something like: *"AI-powered concept screening to rank-order ideas before committing to traditional research."* That's defensible, valuable to clients, and matches the actual evidence. Stretching beyond that — quoting accuracy percentages, claiming replacement of human research, reporting absolute PI as predictive — outruns the data.

The next 2-3 validation pilots will determine whether this scope can credibly expand. Until then, the current methodology is the methodology.
