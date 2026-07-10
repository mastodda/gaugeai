# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

The **SSR (Synthetic Survey Research) Toolkit** generates synthetic consumer survey data using LLMs instead of human survey panels. The core innovation is **Semantic Similarity Rating (SSR)**: instead of asking LLMs to pick Likert numbers (which produces poor center-clustered distributions), the system:

1. Elicits open-ended free-text responses from LLM-based personas
2. Embeds those responses alongside reference anchor statements
3. Computes cosine similarity with amplification to produce realistic Likert distributions

Based on Maier et al. (2025) — achieves ~90% correlation with human test-retest reliability.

## Commands

### Install dependencies
```bash
pip install numpy openai google-generativeai anthropic python-dotenv
cd explorer && pip install -r requirements.txt && npm install
```

### Run the pipeline (Streamlit Launcher — recommended)
```bash
streamlit run launcher.py
```
Browser UI: mode dropdown, LLM provider/model selection, concept entry with image upload,
demographic customisation sliders, live progress display, one-click explorer launch.
Saves the generated engagement JSON to config/_launcher_{timestamp}.json.

### Run the pipeline (CLI)
```bash
# Dry-run (validate config, no API calls)
python run_pipeline.py engagements/example_sparkling_water/engagement.json --dry-run

# Full run (default mode: Tier 2 personas, Stage 2, insights)
# Output lands in engagements/<name>/runs/run_TIMESTAMP/ by default
python run_pipeline.py engagements/example_sparkling_water/engagement.json --seed 42

# Paper mode: strict Maier et al. methodology (Tier 1 only, no Stage 2, no insights)
python run_pipeline.py engagements/example_sparkling_water/engagement.json --mode paper

# With custom output dir
python run_pipeline.py engagements/example_sparkling_water/engagement.json --output output/my_run --seed 42

# Generate insights for an existing run
python -m core.insights_generator engagements/<name>/runs/<run_dir>/results.json
```

### Run the Streamlit explorer
```bash
# With mock data (development)
python explorer/generate_mock_data.py --output-dir explorer/mock_data
streamlit run explorer/app.py

# With real pipeline output
streamlit run explorer/app.py -- --data-dir output/<run_dir>
```

### Run tests
```bash
# Unit tests
python -m pytest core/test_ssr_scoring.py -v
python -m pytest core/test_persona_generator.py -v

# Full integration test (requires API keys)
python -m pytest test_integration.py -v

# Explorer data loading validation
python explorer/test_explorer.py
```

## Architecture

### Pipeline Flow

`run_pipeline.py` → `core/pipeline.py` (5-step orchestrator):

1. **LLM Client Init** — load API credentials, initialize provider
2. **Persona Panel Generation** — create synthetic consumer personas
   - *Tier 1 (basic)*: sample demographics → template-based prompts (no API calls)
   - *Tier 2 (rich)*: demographics + lifestyle → LLM generates narrative (1 call/persona)
3. **Embedding Infrastructure** — embed 30 reference anchor statements (6 sets × 5 anchors), cached to disk
4. **Elicitation + Scoring** — for each concept × each persona:
   - *Stage 1 (Scoring)*: LLM free-text response → embed → cosine similarity → Likert pmf (done 2× per persona, averaged)
   - *Stage 2 (Reasoning)*: LLM follow-up "what makes you feel this way?" → qualitative text only, not scored
5. **Output Aggregation** — write `results.json`, `summary.json`, `personas.json`, `insights.json`

Post-pipeline: `core/insights_generator.py` runs GPT-4o-mini to synthesize comparative insights with pre-computed statistics.

### Key Modules

| Module | Role |
|--------|------|
| `core/pipeline.py` | End-to-end orchestrator |
| `core/ssr_scoring.py` | SSR math: embeddings → cosine similarity → Likert distribution |
| `core/llm_client.py` | Multi-provider LLM interface (OpenAI / Gemini / Claude) |
| `core/embedding_client.py` | OpenAI embeddings with persistent disk cache |
| `core/persona_generator.py` | Synthetic persona creation (Tier 1 & Tier 2) |
| `core/insights_generator.py` | LLM-synthesized comparative insights |
| `explorer/app.py` | Streamlit results explorer (~850 lines) |

### Configuration

**Universal config** lives in `config/` and is shared across all engagements:

- **`reference_sets.json`** — 6 semantic anchor sets for purchase intent scoring (e.g. "I'd probably buy this" → 5-point scale)
- **`prompt_templates.json`** — persona system prompt template + elicitation/reasoning question text
- **`lifestyle_attributes.json`** — 6 psychographic dimensions for Tier 2 personas (shopping mindset, health orientation, media influence, etc.) with age/income conditional overrides

**Engagement config** lives in `engagements/<name>/engagement.json` — one folder per client/project. See `engagements/_template/` for the starter layout and `engagements/example_sparkling_water/` for a worked example.

**Layered resolution:** `prompt_templates.json`, `reference_sets.json`, and `lifestyle_attributes.json` are looked up in the engagement folder first, then fall back to root `config/`. Drop a same-named file into an engagement folder to override universally (e.g., custom semantic anchors for a B2B SaaS engagement). Don't override unless you have to.

### Pre-Run Checklist Gate (required)

Every real engagement must have a completed `checklist.md` alongside its `engagement.json`. `run_pipeline.py` scans it at run start and prints a visible warning for any unchecked boxes. Pass `--skip-checklist` only for throwaway experiments.

- **Full spec:** `planned_features/engagement_tuning_checklist_spec.md` — read before first-time authoring or when the checklist itself needs updating.
- **Template:** `engagements/_template/checklist.md` — copied into every new engagement folder.
- **Trap-word glossary** (Step 3 audit reference): `config/category_trap_words.yaml`. Extend when new categories are tested.
- **Raw-price validation log** (Section 5 evidence base): `docs/reference/raw_price_validation_log.md`. Add a row for every engagement using raw price figures.

The failure mode this exists to prevent: category-specific language (e.g., an apparel "fit" question) silently persisting across engagements into categories where it produces plausible-looking but nonsensical output (e.g., "fit/sizing" appearing as a topic in a supplement study). Do not skip the checklist for real client work.

### Output Structure

Each pipeline run produces a timestamped directory under the engagement's `runs/` folder (gitignored):
```
engagements/<name>/runs/run_YYYYMMDD_HHMMSS/
├── results.json       # Full respondent-level SSR data
├── summary.json       # Aggregated Likert distributions by concept
├── personas.json      # Panel demographics & lifestyle attributes
├── insights.json      # LLM-synthesized comparative insights
└── .cache/embeddings/ # Cached embedding vectors (reused across runs)
```

(Older runs invoked with `--output output/...` still write to the legacy global `output/` location.)

### LLM Provider Notes

- **Gemini-3.1-flash-lite** is the default. Chosen to sidestep thinking-mode latency issues in the deprecated `google.generativeai` SDK. Paper validation was on Gemini-2.0-flash (ρ=92.4%); the lite variant is a different tier and has not been independently re-validated.
- **GPT-4o** achieves best KS distributional similarity (0.88)
- **Insights generation** always uses GPT-4o-mini regardless of main provider
- API keys are loaded from `.env` (`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`)

### Domain Suitability

SSR works best for **consumer product categories** (CPG, personal care, household goods, pet products, OTC health). See `docs/reference/domain_suitability_checklist.md` before running on new domains. Age and income are well-replicated by LLMs; gender, region, and ethnicity are less reliable.
