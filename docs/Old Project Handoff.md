# SSR Toolkit — Project Handoff & Context Document

## What This Project Is

A synthetic survey research (SSR) toolkit that generates synthetic consumer survey data using LLMs. Instead of paying for human survey panels, clients can test product concepts against synthetic consumer panels that produce Likert-scale purchase intent distributions and rich qualitative feedback.

The methodology is based on two research papers (both in project files):
1. **Maier et al.** — "LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings"
2. **"How Many Survey Respondents is an LLM Worth?"** — introduces effective sample size (κ) for LLM surveys

---

## Core Methodology: How SSR Works

The pipeline does NOT ask LLMs to pick a number on a Likert scale (that produces terrible, center-clustered distributions). Instead:

1. **Persona creation** — System prompt tells LLM to impersonate a consumer with specific demographics (age, gender, income, region). Example: "You are a 34-year-old woman living in the Midwest with moderate household income. Reply briefly to any questions posed to you."

2. **Free-text elicitation** — Show the persona a product concept, then ask "How likely would you be to purchase this product?" Let the LLM respond freely in natural language. No number, no constraint.

3. **Embedding** — Embed the free-text response using text-embedding-3-small. Also embed 5 reference anchor statements per set (pre-computed, cached).

4. **SSR scoring** — Compute cosine similarity between the response embedding and each of 5 anchors. The critical trick: raw cosine similarities are very close together (e.g., 0.957 to 0.986), so you subtract the minimum similarity to amplify the signal, then normalize into a probability mass function over Likert 1-5.

5. **Ensemble averaging** — Repeat scoring across 6 different reference sets (same gradient, different phrasing) and average the PMFs. This makes results robust to any single set's quirks.

6. **Aggregation** — Average individual respondent PMFs into a survey-level Likert distribution. Compute mean PI, std, demographic breakdowns.

---

## What's Built (Phases 0-1 Complete)

The toolkit lives in the `ssr-toolkit/` directory with this structure:

```
ssr-toolkit/
├── run_pipeline.py                  # CLI entry point (--dry-run, --seed)
├── test_integration.py              # Full pipeline test with mock clients
├── README.md
├── config/
│   ├── reference_sets.json          # 6 reference statement sets
│   ├── pipeline_config.json         # Model defaults and SSR parameters
│   ├── prompt_templates.json        # Persona prompts and elicitation questions
│   └── example_engagement.json      # Example client engagement config
├── core/
│   ├── ssr_scoring.py               # SSR math engine
│   ├── embedding_client.py          # OpenAI embedding API with disk caching
│   ├── llm_client.py                # Multi-provider LLM client (OpenAI/Gemini/Claude)
│   ├── persona_generator.py         # Demographic-based panel generation
│   ├── pipeline.py                  # End-to-end orchestrator
│   ├── test_ssr_scoring.py          # Unit tests for SSR math
│   └── test_persona_generator.py    # Unit tests for persona generation
└── docs/
    └── domain_suitability_checklist.md
```

### Key capabilities:
- CLI with `--dry-run` (validates config, estimates costs, no API calls) and `--seed` (random by default, logged for reproducibility)
- Multi-provider LLM support: OpenAI (GPT-4o), Google (Gemini-2.0-flash), Anthropic (Claude)
- Disk caching for reference set embeddings (computed once, never again)
- 2 samples per persona averaged for stability
- Output: results.json (full respondent data), summary.json (quick-look), personas.json

### Reference sets (6 sets, user-provided):
1. Direct likelihood ("I'd probably buy this")
2. Purchase decision ("I think I would purchase this")
3. Interest/consideration ("This product seems interesting to me")
4. Spending/money ("I'd consider spending money on this")
5. Try/give-it-a-go ("I'd probably give this a try")
6. Personal fit/need ("I think this product would work well for me")

---

## What's Deferred

### Phase 2 — Statistical Layer (deferred until human baseline data is available)
- Effective sample size (κ) from paper 2 — GPT-4o ≈ 58 equivalent humans for social opinions
- Confidence intervals require human calibration data or conservative heuristics
- KS similarity computation for distributional fit metrics
- Will implement when/if human survey data becomes available for cross-referencing

### Phase 5 — Hardening
- Multi-question support (swap reference sets per question type)
- Multi-model validation runs
- Reference set tuning workflow
- Cost estimation per run

---

## Key Findings from the Papers

### SSR Paper (Maier et al.)
- SSR achieves ~90% correlation attainment with human test-retest reliability
- KS distributional similarity: 0.88 (GPT-4o), 0.80 (Gemini)
- Direct Likert elicitation produces terrible results (regression to 3). Free-text + SSR is essential.
- Demographics: age and income replicate well. Gender, region, ethnicity are unreliable.
- LLM temperature (0.5 vs 1.5) made minimal difference
- Reference sets were manually optimized for 57 personal care surveys — generalization to other domains is unproven
- The method works because personal care products have abundant consumer discussion in LLM training data
- Synthetic responses are LESS positively biased than human surveys — expect lower absolute PI values
- T=1.0 for post-elicitation temperature is a reasonable default, with optimization potential

### Sample Size Paper
- Each LLM has a "hidden population size" κ — the effective number of real humans it represents
- GPT-4o ≈ 58 people for social opinions, DeepSeek-V3 ≈ 45
- 500 synthetic respondents ≠ 500 independent data points
- κ varies dramatically by domain (social opinions vs. math questions)
- Different LLMs are best for different domains — no single best model
- Tested: Claude 3.5 Haiku, DeepSeek V3, GPT-3.5 Turbo, GPT-4o mini, GPT-4o, GPT-5 mini, Llama 3.3 70B, Mistral 7B

---

## Architecture Decisions & Rationale

### Multi-model strategy
Running the same concept through multiple LLMs does NOT reliably increase effective sample size because training data overlaps heavily. The κ values likely don't add up. Multi-model is valuable as a **disagreement detector** (if models diverge, confidence is lower) and for **qualitative richness** (different models highlight different product concerns). Recommended approach: primary run on one model, lighter validation run on a secondary model.

### Reference set design
Reference sets are the most sensitive component. They must be short, generic, domain-independent, and form a monotonic gradient. Multiple sets averaged together are more robust than any single "best" set. Sets 3 (interest) and 6 (personal fit) frame intent more indirectly than sets 1-2 and 4-5 — this diversity is intentional and helps the ensemble.

### Domain suitability
The method's validity is bounded by consumer discussion in LLM training data. High-confidence categories: personal care, food & beverage CPG, household cleaning, consumer electronics accessories, pet products, OTC health. Avoid for MVP: B2B, luxury, financial products, novel tech categories. A pre-flight check (generate 10-20 responses, inspect for specificity) is built into the docs.

### Persona approach
Current personas are demographic coordinates only (age, gender, income, region). The paper validated this approach — adding psychographic backstories would mean using an LLM to generate the persona that another LLM call inhabits, adding synthetic-on-synthetic risk without proven benefit. The seed is randomized by default so every run samples a fresh panel, with the seed logged for reproducibility.

---

## Real Test Results & Interpretation

Four real pipeline runs have been completed:

| Test | Concept | Mean PI | Positive (4+5) | Negative (1+2) | Ratio |
|------|---------|---------|----------------|----------------|-------|
| Sparkling Water | A (basic) | 3.42 | 53.9% | 23.8% | 2.3:1 |
| Sparkling Water | B (vitamin) | 3.33 | 49.2% | 25.6% | 1.9:1 |
| Dress Shirts | A | 3.64 | 60.3% | 16.8% | 3.6:1 |
| Dress Shirts | B | 3.48 | 53.4% | 20.5% | 2.6:1 |

### Key interpretation points:
- **Absolute PI values in the 3.3-3.7 range are expected and correct.** The paper's synthetic data averaged 3.5-3.8 vs human data at 4.0. LLMs lack the positivity bias of human survey respondents.
- **Mean PI alone looks lukewarm, but distributions tell a clearer story.** Shirts A has 3.6x more positive than negative sentiment; Water B is only 1.9:1. Those are meaningfully different profiles.
- **Within-category differentiation is real but narrow.** The paper's entire 57-concept human dataset had std of only 0.2 across mean PIs. Narrow spread is normal in consumer research.
- **Between-category differences make sense.** Shirts scored higher when targeted at higher-income men — the LLM captured audience-concept fit.

### Presentation strategy for clients:
- Do NOT lead with mean PI in isolation — it looks mediocre to anyone not calibrated to the method
- Present positive/negative ratio, "top 2 box" (% rating 4+5), and distribution shape
- Concept ranking (which is better) is more reliable than absolute scores
- Qualitative free-text responses are the primary differentiator over competitors
- Frame as: "60% of the synthetic panel leaned toward purchase" not "mean PI of 3.64"

---

## Phase 3 Spec: Results Explorer (Next to Build)

A Streamlit app for interactively exploring pipeline output. Core views:

1. **Likert distribution histograms** — Side-by-side concept comparison with bar charts. Show distribution shape, not just means. Include top-2-box and positive/negative ratio.

2. **Demographic breakdowns** — Slice distributions by age bands, income levels, gender, region. Flag unreliable demographic axes (gender, region, ethnicity) per the paper's findings.

3. **Individual response browser** — Searchable/filterable table of free-text responses with their SSR scores. Filter by concept, demographic segment, sentiment level. This is the qualitative gold mine.

4. **Concept comparison dashboard** — Head-to-head view: two concepts side by side with distribution overlay, demographic breakdown comparison, and representative quotes from each sentiment band.

5. **Reliability indicators** — Flag which demographic segments have enough representation to be meaningful. Show run metadata (seed, model, panel size, reference sets used).

Input: the results.json and personas.json files from a pipeline run.

---

## Dependencies

Current (Phase 0-1):
- `numpy` — required for all modes
- `openai` — required for real pipeline runs (embeddings + GPT-4o)
- `google-generativeai` — optional, for Gemini provider
- `anthropic` — optional, for Claude provider

Phase 3 will add:
- `streamlit` — for the Results Explorer app
- `plotly` or `altair` — for interactive charts