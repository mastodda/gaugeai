# SSR Toolkit — Consolidated Project Document

*Last updated: May 2026*

---

## What This Project Is

A synthetic survey research (SSR) toolkit that generates synthetic consumer survey data using LLMs. Instead of paying for human survey panels, clients can test product concepts against synthetic consumer panels that produce Likert-scale purchase intent distributions and rich qualitative feedback.

The methodology is based on two research papers (both in project files):
1. **Maier et al.** — "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"
2. **"How Many Survey Respondents is an LLM Worth?"** — introduces effective sample size (κ) for LLM surveys

---

## Core Methodology: How SSR Works

The pipeline does NOT ask LLMs to pick a number on a Likert scale (that produces terrible, center-clustered distributions). Instead:

1. **Persona creation** — System prompt tells LLM to impersonate a consumer with specific demographics and lifestyle attributes.

2. **Free-text elicitation** — Show the persona a product concept (text description or image), then ask "How likely would you be to purchase this product?" Let the LLM respond freely. No number, no constraint.

3. **Embedding** — Embed the free-text response using text-embedding-3-small. Also embed 5 reference anchor statements per set (pre-computed, cached).

4. **SSR scoring** — Compute cosine similarity between the response embedding and each of 5 anchors. Subtract the minimum similarity to amplify the signal, then normalize into a probability mass function over Likert 1-5.

5. **Ensemble averaging** — Repeat scoring across 6 reference sets (same gradient, different phrasing) and average the PMFs.

6. **Stage 2 reasoning** — Follow up with "What specifically about this product makes you feel that way? What would make you more or less likely to buy it?" This response is stored but never scored — it's qualitative-only.

7. **Aggregation** — Average individual respondent PMFs into survey-level Likert distributions. Compute mean PI, std, demographic and lifestyle breakdowns.

8. **Insight generation** — One GPT-4o-mini call per run synthesizes pre-computed segment metrics and response themes into a comparative insights report.

---

## Architecture & Directory Structure

```
ssr-toolkit/
├── run_pipeline.py                  # CLI entry point (--dry-run, --seed, --mode)
├── launcher.py                      # Streamlit UI launcher (recommended)
├── test_integration.py              # Full pipeline test with mock clients
├── core/
│   ├── pipeline.py                  # End-to-end orchestrator (5 steps)
│   ├── ssr_scoring.py               # SSR math engine
│   ├── embedding_client.py          # OpenAI embedding API with disk caching
│   ├── llm_client.py                # Multi-provider LLM client (OpenAI/Gemini/Claude)
│   ├── persona_generator.py         # Tier 1/Tier 2 panel generation
│   ├── insights_generator.py        # LLM-synthesized comparative insights
│   ├── test_ssr_scoring.py          # Unit tests for SSR math
│   └── test_persona_generator.py    # Unit tests for persona generation
├── explorer/
│   ├── app.py                       # Streamlit Results Explorer (~850 lines)
│   ├── reviews_component.py         # React reviews UI (embedded via HTML)
│   ├── generate_mock_data.py        # Mock data generator for development
│   ├── test_explorer.py             # Data loading validation tests
│   └── requirements.txt             # streamlit, altair, pandas
├── config/
│   ├── reference_sets.json          # 6 reference statement sets
│   ├── pipeline_config.json         # Model defaults and SSR parameters
│   ├── prompt_templates.json        # Persona prompts and elicitation questions
│   ├── lifestyle_attributes.json    # 6 psychographic dimensions for Tier 2
│   ├── example_engagement.json      # Example: sparkling water concept test
│   └── example_engagement2.json     # Example: dress shirts concept test
├── docs/
│   ├── domain_suitability_checklist.md
│   ├── methodology_differences.md   # Deviations from Maier et al. (2025)
│   └── PROJECT_HANDOFF.md           # This file
└── output/                          # Pipeline run outputs
    └── <run_dir>/
        ├── results.json             # Full respondent data
        ├── summary.json             # Quick-look without individual data
        ├── personas.json            # Panel demographics and lifestyle
        └── insights.json            # LLM-synthesized comparative insights
```

---

## Pipeline Modes

Set `"mode"` in the `pipeline` section of the engagement JSON, or override at runtime with `--mode`:

| Feature | `"full"` (default) | `"paper"` |
|---|---|---|
| Personas | Tier 2 (LLM narrative + psychographics) | Tier 1 (demographic template) |
| Stage 2 reasoning | Enabled | Disabled |
| Insights generation | Enabled | Disabled |
| SSR scoring | Identical | Identical |

`"paper"` mode replicates the strict Maier et al. (2025) methodology. Use it for validation runs, cost-sensitive jobs, or establishing a calibrated baseline before running `"full"`.

---

## Pipeline Steps

The pipeline runs in 5 steps (plus insight generation):

1. **LLM client init** — needed early because Tier 2 persona gen requires LLM calls
2. **Persona generation** — sample demographics + lifestyle, optionally generate narrative via LLM (skipped in paper mode; Tier 1 only)
3. **Embedding client + reference sets** — pre-compute anchor embeddings (cached to disk)
4. **Elicitation + scoring** — for each persona × concept × sample: Stage 1 (PI response → embed → SSR score), then Stage 2 if enabled (reasoning follow-up; disabled in paper mode)
5. **Write output** — results.json, summary.json, personas.json
6. **Insight generation** (non-blocking) — one GPT-4o-mini call synthesizing all responses into comparative insights.json (skipped in paper mode)

### Running

```bash
# Dry run — validate config, estimate costs, no API calls
python run_pipeline.py config/example_engagement.json --dry-run

# Full run (default: Tier 2 personas, Stage 2 reasoning, insights)
python run_pipeline.py config/example_engagement.json --seed 42

# Paper mode — strict Maier et al. methodology (Tier 1, no Stage 2, no insights)
python run_pipeline.py config/example_engagement.json --mode paper

# Generate insights for an existing run
python -m core.insights_generator output/<run_dir>/results.json
```

---

## Two-Stage Elicitation

For each persona × concept:

**Stage 1 (scoring)**: Ask purchase intent question. Get short response. Embed it. Score via SSR. Uses `persona.system_prompt`. Temperature: `llm_temperature` (default 0.5). This is the only stage that touches SSR math.

**Stage 2 (reasoning)**: Follow up with "What specifically about this product makes you feel that way? What would make you more or less likely to buy it?" Uses `persona.reasoning_prompt`. Temperature: `reasoning_temperature` (default 1.0). Response stored as `reasoning_response` — never embedded, never scored. Max tokens: 400.

The reasoning question was designed to start open-ended, nudge toward actionable insight (barriers and drivers), and read as one natural thought.

---

## Persona System: Tier 1 vs Tier 2

### Tier 1 (basic)
Template-based prompts: "You are a 34-year-old woman living in the Midwest with moderate household income." No extra API calls. Paper-validated.

### Tier 2 (rich)
Activated by placing `lifestyle_attributes.json` next to the engagement JSON. For each persona:
1. Sample demographics (same as Tier 1)
2. Sample 6 lifestyle dimensions with conditional overrides
3. One LLM call generates a 2-3 paragraph persona narrative
4. Narrative used in both system_prompt and reasoning_prompt (with different framing)

**6 psychographic dimensions:**

| Dimension | Values |
|-----------|--------|
| Household composition | single, couple, family w/ young kids, family w/ teens, single parent, empty nester, roommates |
| Shopping mindset | deal hunter, convenience first, quality/ingredient focused, brand loyal, impulse/spontaneous |
| Health orientation | highly health-conscious, moderately health-aware, health-indifferent, fitness/performance |
| Brand adoption style | early adopter, early majority, late majority, skeptic (Rogers' curve) |
| Primary shopping channel | mainstream grocery, warehouse club, discount/value, natural/specialty, online |
| Media influence | social media, research-driven, word-of-mouth, in-store discovery, ad-responsive |

Each dimension has conditional overrides — distributions shift based on age and income. Example: low-income personas are 50% deal hunters (vs 30% baseline).

### Impact on Scores

Tier 2 produces ~0.5 lower absolute mean PI vs Tier 1. Concept ranking is preserved. The qualitative reasoning is dramatically better. We use Tier 2 by default.

**Hybrid option (not yet implemented)**: Use Tier 1 prompts for Stage 1 scoring, Tier 2 for Stage 2 reasoning. Would preserve paper-validated PI scores while getting rich qualitative data.

---

## Image Support

Concepts support three input modes: text only, image only, or both together. Set `image_path` and/or `description` in the engagement JSON:

```json
{
  "concept_id": "concept_a",
  "name": "Product Name",
  "description": "Text description",
  "image_path": "concept_a.png"
}
```

| `description` | `image_path` | What gets sent to the LLM |
|---|---|---|
| provided | valid file | Both image and text description |
| provided | null / missing | Text only |
| null | valid file | Image only |
| null | null / missing | Error — pipeline halts |

Place image files next to the engagement JSON. The pipeline resolves relative paths and validates each file exists; a missing image falls back gracefully (text-only or error if no text either). All three providers (OpenAI, Gemini, Claude) support combined image + text input.

The paper found image stimulus slightly outperformed text-only. Sending both gives the LLM the visual stimulus plus any additional context the image alone may not convey (e.g., brand name, ingredients, price tier).

Images are displayed in the Streamlit Overview tab above each concept's metrics.

---

## Results Explorer (Streamlit)

### Running

```bash
# With mock data
python explorer/generate_mock_data.py --output-dir explorer/mock_data
streamlit run explorer/app.py

# With real pipeline output
streamlit run explorer/app.py -- --data-dir output/<run_dir>
```

### Tab Layout

**Tab 1: Overview** — Per-concept summary cards (with concept images if available), Likert distribution chart, concept ranking table, head-to-head lift metrics.

**Tab 2: Insights** — LLM-synthesized comparative analysis. Headline verdict, concept comparison (winner + margin), per-concept strengths/weaknesses/best audience, segment-level findings with pre-computed data tables, topic analysis with real keyword frequencies, prioritized recommended actions. All statistics are pre-computed in Python before the LLM call — the model synthesizes patterns, it doesn't invent numbers. Framed as "hypotheses to test."

**Tab 3: Compare** — Head-to-head with distribution overlay, metrics comparison, demographic comparison chart, representative quotes by sentiment band.

**Tab 4: Demographics** — Segment selector (age, income, gender, region), reliability warnings for unreliable axes, mean PI by segment, distribution faceted by segment.

**Tab 5: Responses** — Amazon-style reviews UI (React component embedded via iframe). Features:
- Sentiment band distribution bars (Strong intent 4.0-5.0, Leaning positive 3.5-4.0, Neutral 2.8-3.5, Leaning negative 2.2-2.8, Low intent <2.2) — clickable to filter
- Demographic filter badges (gender, age band, region, income)
- Sort by highest/lowest rated, text search
- Each review card shows: persona demographics, star rating, sentiment label, PI score badge, full free-text response (expandable), expandable "Why they feel this way" reasoning section
- Concept tabs to switch between concepts

**Tab 6: Metadata** — Pipeline config, engagement info, panel summary, reliability indicators, methodological notes.

---

## Insights Generator

### Architecture

The insights system avoids the trap of one LLM summarizing what another LLM said with generic platitudes. Instead:

1. **Pre-compute** (Python, no LLM): segment-level mean PI for every demographic and lifestyle dimension, keyword frequency counts, cross-concept deltas per segment, sampled verbatims by sentiment band
2. **One LLM call** (GPT-4o-mini): receives all pre-computed data with instructions to use exact numbers. Produces comparative analysis, segment findings, topic analysis, and recommendations
3. **Output**: structured JSON with pre-computed data attached so the Streamlit tab can render both the LLM synthesis and the raw numbers

### Key Design Decisions

- **Comparative, not per-concept**: one call analyzes all concepts together, focused on "which wins and why"
- **Pre-computed frequencies**: real counts, not hallucinated percentages
- **Segment-specific**: slices by shopping mindset, brand adoption style, income, age — not just overall
- **Framed as hypotheses**: explicitly labeled as "hypotheses to test with real consumers"
- **Non-blocking**: if insight generation fails, the pipeline still completes

### Cost

~$0.05-0.10 per run using GPT-4o-mini. Negligible relative to the $0.75-1.25 main pipeline cost.

---

## Key Findings from the Papers

### SSR Paper (Maier et al.)
- SSR achieves ~90% correlation attainment with human test-retest reliability
- KS distributional similarity: 0.88 (GPT-4o), 0.80 (Gemini)
- Direct Likert elicitation produces terrible results (regression to 3). Free-text + SSR is essential.
- Demographics: age and income replicate well. Gender, region, ethnicity are unreliable.
- LLM temperature (0.5 vs 1.5) made minimal difference
- Reference sets were manually optimized for 57 personal care surveys
- Synthetic responses are LESS positively biased than human surveys — expect lower absolute PI values

### Sample Size Paper
- Each LLM has a "hidden population size" κ — the effective number of real humans it represents
- GPT-4o ≈ 58 people for social opinions, DeepSeek-V3 ≈ 45
- 500 synthetic respondents ≠ 500 independent data points
- κ varies dramatically by domain
- Different LLMs are best for different domains — no single best model

---

## Real Test Results

| Test | Concept | Mean PI | Positive (4+5) | Negative (1+2) | Ratio |
|------|---------|---------|----------------|----------------|-------|
| Sparkling Water | A (basic) | 3.42 | 53.9% | 23.8% | 2.3:1 |
| Sparkling Water | B (vitamin) | 3.33 | 49.2% | 25.6% | 1.9:1 |
| Dress Shirts | A (intro offer) | 3.64 | 60.3% | 16.8% | 3.6:1 |
| Dress Shirts | B ($200 off) | 3.48 | 53.4% | 20.5% | 2.6:1 |

### Interpretation
- Absolute PI in the 3.3-3.7 range is expected. The paper's synthetic data averaged 3.5-3.8 vs human data at 4.0.
- Mean PI alone looks lukewarm — distributions tell a clearer story. Shirts A has 3.6:1 pos:neg; Water B is only 1.9:1.
- Within-category differentiation is real but narrow (std ~0.2 across concepts is normal).
- Concept ranking (which wins) is more reliable than absolute scores.

### Presentation Strategy for Clients
- Do NOT lead with mean PI — it looks mediocre to anyone not calibrated
- Present pos:neg ratio, top 2 box, and distribution shape
- Frame as: "60% of the synthetic panel leaned toward purchase" not "mean PI of 3.64"
- Qualitative free-text responses are the primary differentiator over competitors

---

## Architecture Decisions

### Multi-model strategy
Running the same concept through multiple LLMs does NOT reliably increase effective sample size — training data overlaps too heavily. Multi-model is valuable as a **disagreement detector** and for **qualitative richness**. Recommended: primary run on one model, lighter validation run on a secondary model.

### Reference set design
Reference sets are the most sensitive component. Must be short, generic, domain-independent, and form a monotonic gradient. 6 sets averaged together are more robust than any single set.

**Reference sets (6):**
1. Direct likelihood ("I'd probably buy this")
2. Purchase decision ("I think I would purchase this")
3. Interest/consideration ("This product seems interesting to me")
4. Spending/money ("I'd consider spending money on this")
5. Try/give-it-a-go ("I'd probably give this a try")
6. Personal fit/need ("I think this product would work well for me")

### Domain suitability
High-confidence categories: personal care, food & beverage CPG, household cleaning, consumer electronics accessories, pet products, OTC health. Avoid for MVP: B2B, luxury, financial products, novel tech categories.

---

## Cost Estimates

For a 100-persona, 2-concept run:

| Component | Tier 1 | Tier 2 |
|---|---|---|
| Persona generation | 0 LLM calls | 100 LLM calls |
| Stage 1 scoring (2 samples) | 400 LLM calls | 400 LLM calls |
| Stage 1 embeddings | 400 embed calls | 400 embed calls |
| Stage 2 reasoning | 200 LLM calls | 200 LLM calls |
| Insight generation | 1 GPT-4o-mini call | 1 GPT-4o-mini call |
| **Total LLM calls** | **601** | **701** |
| **Estimated cost (GPT-4o)** | **~$0.55-$1.05** | **~$0.80-$1.35** |

---

## Dependencies

**Core pipeline:**
- `numpy` — required for all modes
- `openai` — required for pipeline runs and insights (embeddings + GPT-4o + GPT-4o-mini)
- `python-dotenv` — loads API keys from .env file
- `google-generativeai` — optional, for Gemini provider
- `anthropic` — optional, for Claude provider

**Explorer:**
- `streamlit>=1.30.0`
- `altair>=5.0.0`
- `pandas>=2.0.0,<3.0.0`

---

## Session Summary — April 2026

### What was done

**1. Methodology audit (`docs/methodology_differences.md`)**

Performed a full comparison between the current pipeline implementation and the Maier et al. (2025) paper methodology. Findings documented in `docs/methodology_differences.md`. Key deviations identified:

- **Tier 2 personas are not paper-validated** — produce ~0.5 lower absolute mean PI vs the paper's Tier 1 baseline. Concept ranking is preserved; absolute scores are not calibrated to the paper.
- **Stage 2 reasoning is an extension** — the paper ends at SSR scoring; the reasoning follow-up is a product addition.
- **Reference sets use custom wording** — the paper's anchor texts were optimized for 57 personal care surveys; the toolkit's 6 sets are custom-authored and not independently validated.
- **Insights generation has no paper equivalent** — it is a product layer.
- **Effective sample size (κ) is not implemented** — deferred to Phase 2.
- **Absolute PI runs lower than paper baseline** (~3.3–3.7 vs the paper's 3.5–3.8) due to Tier 2 persona drift.

**2. Pipeline mode switching**

Added a `"mode"` field to engagement configs and a `--mode` CLI flag:

- `"full"` (default) — Tier 2 personas, Stage 2 reasoning, insights generation
- `"paper"` — strict Maier et al.: Tier 1 personas only, no Stage 2, no insights

Implementation: `apply_mode(config, mode)` in `core/pipeline.py` sets `lifestyle_config_path`, `skip_stage_2`, and `skip_insights` flags. The CLI flag overrides the engagement config. Mode is recorded in `results.json` metadata.

Usage:
```bash
python run_pipeline.py config/my_engagement.json --mode paper
python run_pipeline.py config/my_engagement.json --mode full
```

Or set `"mode": "paper"` in the `pipeline` section of the engagement JSON.

**3. Streamlit launcher (`launcher.py`)**

A browser-based UI for configuring and running the pipeline without editing JSON files.

```bash
streamlit run launcher.py
```

Features:
- **Sidebar**: mode selector, LLM provider/model dropdowns, temperature slider, samples per persona, seed
- **Concepts tab**: dynamic add/remove concept cards with name, description textarea, and drag-and-drop image uploader with live preview
- **Demographics tab**: panel size, age range slider, gender split, region and income number inputs with real-time sum validation
- **Run**: spawns `run_pipeline.py` as a subprocess, streams stdout live, saves the generated engagement JSON to `config/_launcher_{timestamp}.json`
- **Done**: shows output directory, one-click "Launch Explorer" button that opens the results explorer in a new process

### Files changed

| File | Change |
|---|---|
| `core/pipeline.py` | Added `mode`, `skip_stage_2`, `skip_insights` to `PipelineConfig`; added `apply_mode()`; gated Stage 2 and insights on flags; added `mode` to output metadata |
| `run_pipeline.py` | Added `--mode` CLI flag; imports and calls `apply_mode()` as override; updated dry-run cost estimate to show Stage 1/Stage 2 breakdown |
| `config/example_engagement.json` | Added `"mode": "full"` to pipeline section |
| `launcher.py` | New file — Streamlit launcher UI |
| `docs/methodology_differences.md` | New file — full audit of deviations from paper |
| `README.md` | Added launcher usage, Pipeline Modes section, updated Persona Tiers section |
| `CLAUDE.md` | Added launcher and `--mode` to commands |
| `docs/PROJECT_HANDOFF.md` | Updated directory structure, pipeline steps, running instructions |

---

## Session Summary — May 2026

### What was done

**Multi-modal concept input (`core/llm_client.py`)**

Previously each provider used an `if/elif` pattern — image took priority and text was silently dropped if both were provided. Updated all three providers (OpenAI, Gemini, Anthropic) to support sending both image and text together when both are present, while preserving existing single-modal behavior.

- **Both present**: image block + text description sent in the same user message
- **Image only**: image + generic intro text (unchanged behavior)
- **Text only**: plain text message (unchanged behavior)
- **Neither**: raises `ValueError` (unchanged behavior)

The pipeline and engagement JSON schema required no changes — `concept.get("description")` and `concept.get("image_path")` were already being passed through; the fix was entirely in the provider message-building logic.

### Files changed

| File | Change |
|---|---|
| `core/llm_client.py` | Replaced `if/elif` concept blocks with `has_image`/`has_text` flags in all three providers; updated abstract base class docstring |

---

## Open Questions & Next Steps

- **Validate Tier 2 against more concepts**: Build confidence in scoring differences across categories.
- **Hybrid scoring/reasoning prompts**: If Tier 2 PI drift becomes a concern, use Tier 1 for scoring and Tier 2 for reasoning. The fields are already separate in `PipelineConfig` (`system_prompt` vs `reasoning_prompt`). Not yet implemented.
- **Lifestyle attribute tuning**: Weights are population-approximate, not precision-sourced. Could tighten with Pew/NielsenIQ data.
- **Phase 2 — Statistical Layer**: Effective sample size (κ), confidence intervals. Deferred until human baseline data is available.
- **Multi-question support**: Swap reference sets per question type (purchase intent vs. relevance vs. appeal).
- **Reference set tuning workflow**: Systematic way to optimize ε and T parameters.
- **Domain expansion**: Validate beyond personal care into food, tech, fashion, household goods.
- **Launcher: add dry-run support**: Let users estimate cost before committing to a full run from the UI.
- **Launcher: persist form state across sessions**: Currently resets on browser refresh.
