# SSR Toolkit — Session Handoff: Phase 3 Explorer + Persona Enrichment

## Session Summary

This session covered two major workstreams:
1. **Phase 3: Streamlit Results Explorer** — built from scratch
2. **Two-stage elicitation + Tier 2 rich personas** — designed and implemented

---

## Phase 3: Results Explorer

### What It Is

A Streamlit app (`explorer/app.py`) for analyzing SSR pipeline output. Single-file, tabbed UI with 5 views. Uses Altair for charts, Pandas for data transformation.

### Directory Structure

```
explorer/
├── app.py                    # Main Streamlit app (~700 lines)
├── generate_mock_data.py     # Mock data generator for development
├── test_explorer.py          # Data loading validation tests
├── requirements.txt          # streamlit>=1.30.0, altair>=5.0.0, pandas>=2.0.0,<3.0.0
└── mock_data/                # Generated test data
    ├── results.json
    └── personas.json
```

### Running It

```bash
# Generate mock data for development
python explorer/generate_mock_data.py --output-dir explorer/mock_data --panel-size 100

# Run with mock data
streamlit run explorer/app.py

# Run with real pipeline output
streamlit run explorer/app.py -- --data-dir output/run_20260215_143000
```

### Tab Layout

**Tab 1: Overview** (order: Summaries → Distribution → Ranking → Head-to-Head Lift)
- Per-concept metric cards: Mean PI, Top 2 Box, +/− Ratio
- Likert distribution chart (Altair, side-by-side by concept)
- Concept Ranking section: side-by-side table across 5 metrics (Mean PI, Top 2 Box, +/− Ratio, Bottom 2 Box, Consensus/Std) with "Winner" column per row, overall winner banner, tie detection
- Head-to-Head Lift (2-concept case): absolute deltas and relative lift (e.g., "1.15× Top 2 Box")

**Tab 2: Demographics**
- Segment selector (age_band/income/gender/region)
- Reliability warnings for unreliable axes (gender/region/ethnicity per paper)
- Mean PI by segment chart, distribution faceted by segment, segment size table

**Tab 3: Responses**
- Searchable/filterable table of all free-text responses AND reasoning responses
- Filters: concept, sentiment, text search (searches both free_text and reasoning)
- Columns include reasoning column when data is available

**Tab 4: Compare**
- Head-to-head concept comparison with distribution overlay
- Metrics comparison, demographic comparison chart
- Representative quotes by sentiment band, includes reasoning with "Why:" labels

**Tab 5: Metadata**
- Pipeline config, engagement info, panel summary
- Reliability indicators, methodological notes

### Key Metrics Explained

- **Top 2 Box**: Proportion of distribution in ratings 4+5. Standard market research metric.
- **+/− Ratio**: Top-2-box ÷ bottom-2-box. Above 2:1 = solid positive lean. Exists because mean PI alone looks lukewarm due to narrow clustering.
- **Concept ranking is more reliable than absolute PI values** — this is reinforced throughout the UI.

### Issues Resolved During Development

1. **Path resolution**: Streamlit working directory differs from project root. Fixed with `.resolve()`.
2. **Pandas version**: Streamlit requires pandas<3. Pinned in requirements.txt.
3. **Deprecation warnings**: `use_container_width` → `width="stretch"` (6 occurrences). Added `observed=False` to all `groupby()` calls. Cast config dict values to `str()` for Arrow serialization.

---

## Two-Stage Elicitation

### Architecture

For each persona × concept, the pipeline now runs two stages:

1. **Stage 1 (scoring)**: Ask purchase intent question. Get short response. Embed it. Score via SSR. Uses `persona.system_prompt`. Temperature: `llm_temperature` (default 0.5). **This is the only stage that touches SSR math.**

2. **Stage 2 (reasoning)**: Follow up with "What specifically about this product makes you feel that way? What would make you more or less likely to buy it?" Uses `persona.reasoning_prompt`. Temperature: `reasoning_temperature` (default 1.0). Response stored as `reasoning_response` — never embedded, never scored.

### Reasoning Question Design

The question was chosen to:
- Start open-ended (doesn't lead toward positive or negative)
- Nudge toward actionable insight (barriers and drivers)
- Read as one natural thought despite being two questions
- Avoid being too structured (we want natural language, not bullet points)

### Files Changed

- **`prompt_templates.json`** — Added `reasoning_followup` under `elicitation_prompt`, updated assembly order
- **`ssr_scoring.py`** — Added `reasoning_response: str | None = None` to `SSRResult` dataclass, updated `result_to_dict` to conditionally include it
- **`pipeline.py`** — Added `reasoning_question` and `reasoning_temperature` to `PipelineConfig`, makes stage 2 LLM call after scoring (once per persona per concept, `max_tokens=400`)
- **`example_engagement.json`** — Added `reasoning_temperature: 1.0`

---

## Tier 2 Rich Personas

### Problem

With basic template prompts ("You are a 34-year-old woman in the Midwest..."), stage 1 PI responses were highly repetitive. Almost all positive responses used similar language ("I am quite likely", "the significant discount"). This undermined qualitative credibility, especially for stage 2 reasoning.

### Solution: Structured Lifestyle Attributes + LLM Narrative Generation

**`lifestyle_attributes.json`** defines 6 psychographic dimensions with population-approximate distributions:

1. **Household composition** — single, couple, family with young kids, family with teenagers, single parent, empty nester, roommates
2. **Shopping mindset** — deal hunter, convenience first, quality/ingredient focused, brand loyal, impulse/spontaneous
3. **Health orientation** — highly health-conscious, moderately health-aware, health-indifferent, fitness/performance oriented
4. **Brand adoption style** — early adopter, early majority, late majority, skeptic (Rogers' diffusion curve)
5. **Primary shopping channel** — mainstream grocery, warehouse club, discount/value, natural/specialty, primarily online
6. **Media influence** — social media, research-driven, word-of-mouth, in-store discovery, ad-responsive

Each dimension has **conditional overrides** — distributions shift based on age and income. Example: low-income personas are 50% deal hunters (vs 30% baseline), young adults are 50% social-media-influenced (vs 25% baseline).

### Two-Tier System

**Tier 1 (basic)**: No `lifestyle_attributes.json` present. Template-based prompts, no extra API calls. Paper-validated.

**Tier 2 (rich)**: `lifestyle_attributes.json` present in config dir. For each persona:
1. Sample demographics (same as before)
2. Sample 6 lifestyle dimensions with conditional overrides
3. Make one LLM call to generate a 2-3 paragraph persona narrative
4. Use narrative in both system_prompt and reasoning_prompt (with different framing instructions)

**Activation is zero-config**: drop `lifestyle_attributes.json` next to your engagement JSON to enable. Remove it to revert.

### Persona Generator Changes

`persona_generator.py` now has:
- `Persona` dataclass with `lifestyle`, `reasoning_prompt`, and `persona_narrative` fields
- `_resolve_distribution()` and `_eval_condition()` for conditional override logic
- `_sample_lifestyle()` for sampling all dimensions
- `generate_persona_narrative()` for LLM narrative generation
- `_render_rich_prompts()` for creating separate scoring and reasoning system prompts
- `generate_panel()` accepts optional `lifestyle_config_path` and `llm_client` — backward compatible
- `persona_to_dict()` conditionally includes lifestyle, narrative, and reasoning_prompt
- `panel_summary()` includes lifestyle dimension breakdowns for Tier 2

### Pipeline Changes

- LLM client initializes first (step 1/5) since Tier 2 persona gen needs it
- `generate_panel()` receives `lifestyle_config_path` and `llm_client`
- Step numbering: 1) LLM init, 2) persona gen, 3) embeddings/references, 4) elicitation+scoring, 5) write output
- `PipelineConfig` has `reasoning_temperature` (default 1.0) and `lifestyle_config_path`
- Pipeline auto-detects `lifestyle_attributes.json` in the engagement config directory

### Impact on SSR Scores

**Tier 2 rich personas produce lower absolute mean PI scores (~0.5 drop) compared to Tier 1.** Concept ranking is preserved — the same concept wins.

Why this likely happens: rich personas respond more critically and specifically. A persona with established brand preferences and shopping context is harder to impress than a blank-slate survey taker. The simple prompts happen to correlate with human survey data, but human surveys themselves have well-documented acquiescence (positive) bias.

**We decided to move forward with Tier 2** because:
- Concept ranking (the most reliable metric) is preserved
- The qualitative reasoning is dramatically better
- Lower absolute PI may actually be more realistic
- The paper's validation only proves Tier 1 works, not that it's optimal

**To revert**: see `revert_personas.txt`. Short version: remove `lifestyle_attributes.json` from config dir.

**Hybrid option (not yet implemented)**: Use Tier 1 prompts for stage 1 scoring, Tier 2 prompts for stage 2 reasoning only. Would preserve paper-validated PI scores while still getting rich qualitative data. The `persona.system_prompt` and `persona.reasoning_prompt` are already separate fields — implementation would be a small change in `persona_generator.py`.

---

## Cost Estimates

For a 100-persona, 2-concept run:

| Component | Tier 1 | Tier 2 |
|---|---|---|
| Persona generation | 0 LLM calls | 100 LLM calls |
| Stage 1 scoring (2 samples) | 400 LLM calls | 400 LLM calls |
| Stage 1 embeddings | 400 embed calls | 400 embed calls |
| Stage 2 reasoning | 200 LLM calls | 200 LLM calls |
| **Total LLM calls** | **600** | **700** |
| Estimated cost (GPT-4o) | ~$0.50-$1.00 | ~$0.75-$1.25 |

---

## Files Delivered This Session

```
explorer/
├── app.py
├── generate_mock_data.py
├── test_explorer.py
├── requirements.txt
└── mock_data/
    ├── results.json
    └── personas.json

pipeline.py                  # Updated with stage 2, Tier 2, split temperatures
ssr_scoring.py               # Updated with reasoning_response field
persona_generator.py         # Rewritten with Tier 1/Tier 2 system
prompt_templates.json        # Updated with reasoning_followup question
lifestyle_attributes.json    # New: 6 psychographic dimensions
example_engagement.json      # Updated with reasoning_temperature
revert_personas.txt          # How to switch between Tier 1 and Tier 2
```

---

## Open Questions and Next Steps

- **Validate Tier 2 against more concepts**: Run several engagements both ways to build confidence in the scoring differences.
- **Hybrid scoring/reasoning prompts**: Implement if Tier 2 PI drift becomes a concern.
- **Lifestyle attribute tuning**: Weights are population-approximate, not precision-sourced. Could tighten with Pew/NielsenIQ data.
- **Explorer improvements**: Could add reasoning-specific views (e.g., theme extraction, word clouds by segment).
- **Domain suitability**: The paper validated on personal care products. Other domains (tech, food, fashion) are untested territory.
- **Phase 2 (Statistical Layer)**: Effective sample size (κ), confidence intervals — deferred until human baseline data is available.