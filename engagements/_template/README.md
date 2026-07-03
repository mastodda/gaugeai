# Engagement Template

Starter for a new engagement. To create one:

```bash
cp -r engagements/_template engagements/<your_engagement_name>
```

Then edit `engagement.json` and `notes.md`.

## Folder layout

```
<your_engagement_name>/
├── engagement.json     # config (panel, concepts, pipeline settings)
├── notes.md            # stakeholder context, decisions, deliverable focus
├── concepts/           # optional: concept stimulus images, long descriptions
└── runs/               # pipeline output goes here (gitignored)
```

## Universal config (inherited from root `config/`)

Three files are resolved with layered fallback — engagement folder first, then root `config/`:

- `prompt_templates.json` — persona system prompt + elicitation/reasoning question text
- `reference_sets.json` — semantic anchors for SSR scoring
- `lifestyle_attributes.json` — Tier 2 psychographic dimensions (presence enables Tier 2)

**Default behavior:** drop nothing extra into the engagement folder. The pipeline uses the root `config/` versions automatically.

**To override for one engagement:** drop a same-named file into the engagement folder. Useful when a domain needs custom semantic anchors (e.g., B2B SaaS instead of CPG) or custom persona narrative prompts.

**To opt out of Tier 2 for one engagement:** add `"pipeline.lifestyle_config": "nonexistent.json"` to engagement.json — the lookup will fail and personas fall back to Tier 1. Or set `"mode": "paper"`.

## Running

```bash
# Dry-run (validate, estimate cost, no API calls)
python run_pipeline.py engagements/<name>/engagement.json --dry-run

# Real run — output lands in engagements/<name>/runs/run_TIMESTAMP/
python run_pipeline.py engagements/<name>/engagement.json --seed 42

# Explore results
streamlit run explorer/app.py -- --data-dir engagements/<name>/runs/<run_dir>
```
