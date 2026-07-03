# Differences from Maier et al. (2025)

This document tracks where the current pipeline implementation deviates from the validated methodology in the paper: *"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"* (Maier et al., 2025).

---

## Summary

| Component | Paper | Current Implementation | Status |
|---|---|---|---|
| SSR formula (equations 7–9) | Min-subtraction + temperature scaling | Exact match | Faithful |
| ε default | 0.0 | 0.0 | Faithful |
| T (SSR temperature) default | 1.0 | 1.0 | Faithful |
| LLM temperature | 0.5 | 0.5 | Faithful |
| Samples per persona | n=2 | n=2 | Faithful |
| Embedding model | text-embedding-3-small | text-embedding-3-small | Faithful |
| Persona type | Tier 1 (demographic template) | Tier 2 (LLM narrative) by default | **Deviation** |
| Reference sets | Optimized for 57 personal care surveys | 6 custom sets (different wording) | **Deviation** |
| Stage 2 reasoning | Not in paper | Added qualitative follow-up | **Extension** |
| Image support | Text-only validated | Multimodal supported | **Extension** |
| Insights generation | Not in paper | GPT-4o-mini synthesis layer | **Extension** |
| Effective sample size (κ) | Second paper introduces it | Not implemented | **Gap** |
| Absolute PI calibration | 3.5–3.8 synthetic vs 4.0 human | 3.3–3.7 (Tier 2 drift) | **Gap** |

---

## Deviations

### 1. Tier 2 personas are not paper-validated

The paper tested **Tier 1 personas**: simple template-based demographic prompts ("You are a 34-year-old woman living in the Midwest with moderate household income"). No extra API calls.

The toolkit defaults to **Tier 2**: an LLM generates a 2-3 paragraph narrative per persona incorporating 6 psychographic dimensions (shopping mindset, health orientation, brand adoption style, household composition, primary shopping channel, media influence).

**Measured impact**: Tier 2 produces ~0.5 lower absolute mean PI vs Tier 1. Concept *ranking* is preserved, but absolute scores deviate from the paper's calibrated baseline. A hybrid mode (Tier 1 for Stage 1 scoring, Tier 2 for Stage 2 reasoning) would preserve paper-validated PI scores while retaining rich qualitative output — but this is not yet implemented. See `core/persona_generator.py`.

### 2. Reference sets use custom wording, not the paper's originals

The paper's reference sets were "manually optimized for 57 personal care surveys." The toolkit's 6 sets cover the same semantic gradient but use different framings:

1. Direct likelihood
2. Purchase decision
3. Interest/consideration
4. Spending/money
5. Try/give-it-a-go
6. Personal fit/need

Performance parity is assumed based on the real test runs documented in `PROJECT_HANDOFF.md`, but the anchor texts have not been independently validated against the paper's original set. See `config/reference_sets.json`.

---

## Extensions (additions beyond the paper)

### 3. Stage 2 reasoning question

The paper's methodology ends at purchase intent scoring. The toolkit adds a second LLM call per persona per concept: *"What specifically about this product makes you feel that way? What would make you more or less likely to buy it?"*

This response is stored as qualitative text and never scored, so it does not affect SSR math. It is a product layer added for client-facing qualitative insight.

### 4. Image support

The paper found image stimulus slightly outperformed text-only. The toolkit extends this to all three providers (OpenAI, Gemini, Claude) with automatic fallback to text if an image file is missing. The paper did not validate multimodal handling across providers or the fallback behavior.

### 5. Insights generation

The `core/insights_generator.py` GPT-4o-mini call that synthesizes comparative insights has no counterpart in the paper. It is a product layer on top of the validated methodology.

---

## Gaps (paper findings not yet implemented)

### 6. Effective sample size (κ) is not computed

The companion paper ("How Many Survey Respondents is an LLM Worth?") introduces κ — the effective human-equivalent sample size per LLM (e.g., GPT-4o ≈ 58 people for social opinions). Running 500 synthetic respondents does not produce 500 independent data points.

The current pipeline reports raw counts with no correction for population diversity and no confidence intervals. This statistical layer is deferred until human baseline data is available for calibration.

### 7. Absolute PI scores run lower than paper baseline

The paper's synthetic data averaged **3.5–3.8** vs human panels at **4.0**. With Tier 2 personas as the default, real test runs show **3.3–3.7** — an additional ~0.2–0.5 downward drift attributable to richer personas being harder to satisfy. The paper's calibration benchmarks apply to Tier 1 only. Present distribution shape and pos:neg ratios rather than absolute mean PI when reporting results.

---

## LLM model versions

The paper benchmarked models available at time of writing. The current defaults — **Gemini-2.0-flash** and **GPT-4o** — may reference different model snapshots than those tested. The ρ=92.4% SSR correlation figure for Gemini and 0.88 KS similarity for GPT-4o should be treated as directional, not guaranteed for current model versions.

---

## Out-of-scope extensions

- **`config/lifestyle_attributes_b2b.json`**: B2B persona dimensions have no paper backing. The domain checklist marks B2B as unsuitable for SSR. This file exists but is untested.
- **Multi-question support**: The current system only supports purchase intent. The paper's SSR method is general-purpose; swapping reference sets per question type (purchase intent vs. relevance vs. appeal) is planned but not implemented.
