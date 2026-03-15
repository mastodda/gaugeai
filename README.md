# SSR Toolkit

A synthetic survey research platform that generates consumer survey data using LLMs instead of human panels. Test product concepts against synthetic consumer panels to get Likert-scale purchase intent distributions and rich qualitative feedback.

Based on two peer-reviewed papers:
- Maier et al. (2025) — *"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"*
- *"How Many Survey Respondents is an LLM Worth?"* — introduces effective sample size (κ) for LLM surveys

---

## How It Works

The system does **not** ask LLMs to pick a number on a Likert scale (which produces center-clustered, unusable distributions). Instead:

1. **Persona creation** — LLM is prompted to impersonate a consumer with specific demographics and lifestyle attributes
2. **Free-text elicitation** — Persona is shown a product concept and asked "How likely would you be to purchase this product?" — no number, no constraint
3. **SSR scoring** — Response is embedded, then cosine-similarity-compared against 5 reference anchor statements per set; similarities are normalized into a Likert 1–5 probability distribution
4. **Ensemble averaging** — Repeated across 6 reference sets (same gradient, different phrasing) and averaged
5. **Reasoning follow-up** — Persona is asked what drives or inhibits their purchase intent; stored as qualitative text only, never scored
6. **Aggregation + insights** — Individual PMFs aggregated into survey-level distributions; one GPT-4o-mini call synthesizes pre-computed segment metrics into a comparative insights report

**Validated performance:** ~90% correlation attainment with human test-retest reliability; KS distributional similarity of 0.88 (GPT-4o).

---

## Setup

```bash
# Core pipeline
pip install numpy openai google-generativeai anthropic python-dotenv

# Results Explorer (Streamlit UI)
cd explorer && pip install -r requirements.txt && npm install
```

Create a `.env` file with your API keys:
```
OPENAI_API_KEY=...
GOOGLE_API_KEY=...       # optional, for Gemini
ANTHROPIC_API_KEY=...    # optional, for Claude
```

---

## Running the Pipeline

```bash
# Validate config, estimate costs — no API calls
python run_pipeline.py config/example_engagement.json --dry-run

# Full run
python run_pipeline.py config/example_engagement.json --seed 42

# Generate insights for an existing run
python -m core.insights_generator output/<run_dir>/results.json
```

Output is written to a timestamped directory under `output/`:
```
output/run_YYYYMMDD_HHMMSS/
├── results.json     # Full respondent-level SSR data
├── summary.json     # Aggregated Likert distributions by concept
├── personas.json    # Panel demographics & lifestyle attributes
└── insights.json    # LLM-synthesized comparative insights
```

---

## Results Explorer

```bash
# With mock data (development)
python explorer/generate_mock_data.py --output-dir explorer/mock_data
streamlit run explorer/app.py

# With real pipeline output
streamlit run explorer/app.py -- --data-dir output/<run_dir>
```

The Explorer has six tabs: **Overview** (concept summary cards, Likert distributions, head-to-head lift), **Insights** (LLM-synthesized comparative analysis with pre-computed statistics), **Compare** (head-to-head with demographic breakdowns), **Demographics** (segment-level mean PI and distributions), **Responses** (Amazon-style reviews UI with filtering by sentiment, demographic, and concept), and **Metadata** (pipeline config and methodological notes).

---

## Tests

```bash
python -m pytest core/test_ssr_scoring.py -v
python -m pytest core/test_persona_generator.py -v
python -m pytest test_integration.py -v          # requires API keys
python explorer/test_explorer.py
```

---

## Engagement Config

Each pipeline run is driven by an engagement JSON file. See `config/example_engagement.json` for a full example. Key fields:

```json
{
  "panel_size": 100,
  "persona_tier": "tier2",
  "concepts": [
    {
      "concept_id": "concept_a",
      "name": "Product Name",
      "description": "Text description shown to personas",
      "image_path": "concept_a.png"
    }
  ]
}
```

Images are optional — place them next to the engagement JSON. All three LLM providers support vision input. The pipeline falls back to text if the image file is missing.

---

## Persona Tiers

**Tier 1 (basic):** Template-based prompts from sampled demographics only. No extra API calls. Paper-validated.

**Tier 2 (rich):** Demographics + 6 psychographic dimensions (shopping mindset, health orientation, brand adoption style, primary shopping channel, media influence, household composition). One LLM call generates a narrative per persona. Produces richer qualitative reasoning at ~0.5 lower absolute mean PI vs Tier 1. Concept ranking is preserved.

---

## Interpreting Results

- **Absolute mean PI** in the 3.3–3.7 range is expected and normal — synthetic data runs lower than human panels due to reduced positivity bias
- **Lead with distributions**, not mean PI: a 3.6:1 positive-to-negative ratio tells a clearer story than a 3.64 mean
- **Concept ranking** (which wins) is more reliable than absolute scores
- **Age and income** demographic segments replicate well; gender, region, and ethnicity are unreliable axes

---

## Cost Estimates (100 personas, 2 concepts)

| | Tier 1 | Tier 2 |
|---|---|---|
| LLM calls | 601 | 701 |
| Estimated cost (GPT-4o) | ~$0.55–$1.05 | ~$0.80–$1.35 |
| Insight generation | ~$0.05–$0.10 | ~$0.05–$0.10 |

Default LLM is **Gemini-2.0-flash** (best SSR correlation, lower cost). See `config/pipeline_config.json` to change providers.
