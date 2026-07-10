# Pre-Run Checklist

Filled in retroactively 2026-07-10 after the 2026-07-08 run. Serves as worked example for future engagements.

**Engagement:** Peptide & Collagen Supplements — Concept Test (CoD Viewer Panel)
**Analyst:** Miles
**Date:** 2026-07-08 (run) / 2026-07-10 (checklist retro)

---

## Step 1 — Category identification

- [x] Product category identified explicitly (not "consumer good" — specify). **Category:** ingestibles / dietary supplements (collagen peptides + citrulline)
- [x] Category checked against `docs/reference/domain_suitability_checklist.md`. Confidence: **high** (supplements/OTC health is in the validated CPG zone)
- [x] Category is NOT aspirational/luxury/identity-signaling.

## Step 2 — Stimulus construction

- [x] Concept card is image-based OR neutral factual copy only. **Images used exclusively after 2026-07-10 revert** — description_file entries in engagement.json are analyst reference only, not sent to LLM.
- [x] Price (where present in the images) is a plain factual figure on the product listing itself. Not injected via marketing text.
- [x] Re-read every concept description out loud: reads as a spec sheet, not an ad. **Note:** description_file contents are still analyst-facing and remain a spec-sheet register even though the pipeline doesn't send them.

## Step 3 — Question/prompt category-compatibility audit (the "fit" bug gate)

- [x] Read the elicitation question line by line against this category. **Elicitation question:** "How likely would you be to purchase this product?" — generic, category-safe.
- [x] Read the reasoning follow-up question line by line against this category. **Reasoning question:** default from `config/prompt_templates.json` — verify this against the trap-word glossary for ingestibles.
- [x] Read any secondary questions line by line against this category.
- [x] Every category-flavored word or phrase confirmed as semantically valid.
- [x] **Cross-checked against `config/category_trap_words.yaml` — no trap words for this category leak through.** ✅ **RESOLVED 2026-07-10:** The v1 insights output produced "fit/sizing" as a topic at 99% mention rate because `core/insights_generator.py` had a hardcoded apparel-centric `keyword_groups` dict. Fixed by replacing hardcoded groups with a per-engagement `discover_topics` LLM pre-pass. Re-run on same results.json produced ingestible-appropriate topics (ingredients, health benefits, price, etc.) with zero apparel vocabulary. Buggy v1 preserved as `runs/run_20260708_094958/insights_v1_buggy.json.bak` for reference.
- [x] Not copied from a prior engagement (started from template).

## Step 4 — Persona tier and framing

- [x] Tier 1 vs Tier 2 choice is intentional. **Chosen:** Tier 2. **Why:** qualitative "why" is central to the deliverable; richer personas produce more usable reasoning quotes.
- [x] **If Tier 2: lifestyle attribute weightings appropriate for the target audience.** ✅ **RESOLVED 2026-07-10:** dropped `engagements/peptide_supplements/lifestyle_attributes.json` overriding the root file via layered config. Retuned for CoD-viewer audience: social_media_influenced ~75%, primarily_online ~75%, children ~0%, impulse/spontaneous ~25%, early_adopter ~35%, fitness/performance oriented ~30%. Conditional overrides removed (whole file scoped to 18-28 audience). Caveat: `primary_shopping_channel` taxonomy is grocery-CPG shaped and doesn't cleanly fit supplements — "primarily online" used as best proxy for the Amazon/GNC/DTC pattern. This is still an unvalidated extension (Tier 2 itself is our extension of the paper, which used demographics-only Tier 1) — see notes.md for framing.
- [x] Audience is a known niche (CoD content viewers). This run is flagged as **unvalidated for niche calibration** in these notes.

## Step 5 — Cross-category check

- [x] All 5 concepts are within the same category (collagen/citrulline supplements). Ranking directly against each other is valid.

## Step 6 — Reporting setup

- [x] Deliverable will lead with ranking / pos:neg ratio / Top-2-Box, NOT absolute mean PI.
- [x] Limitations disclosure will be included.
- [x] Novel niche audience (CoD viewers) — noted as data point toward validation, not validated claim.

## Step 7 — Final sign-off

- [x] **All boxes above checked and reviewed.** Both previously-open items resolved 2026-07-10: Step 3 by systemic fix in `core/insights_generator.py` (topic discovery replaces hardcoded groups); Step 4 by per-engagement `lifestyle_attributes.json` override in this folder. Full re-run of the pipeline (not just insights re-gen) would exercise the new lifestyle weights; only insights.json has been regenerated so far.
- [x] This checklist is committed alongside the engagement config.

**Signed off by:** Miles  **Date:** 2026-07-10 (retroactive)

---

## Post-run notes

- **Ranking held vs. expected?** No baseline available. Result: top 4 concepts within 0.05 PI of each other (essentially tied), Vitauthority laggard at −0.25 PI. Signal is directional at best.
- **Raw-price observations:** logged in `docs/reference/raw_price_validation_log.md`.
- **Category-mismatch surprises:** originally YES — v1 insights reported "fit/sizing" as a top topic at 99%. Root cause was hardcoded apparel-centric `keyword_groups` in `core/insights_generator.py`. Fixed 2026-07-10 by replacing with per-engagement `discover_topics` LLM pre-pass. v2 insights (current `insights.json`) show ingestible-appropriate topics only. v1 preserved at `insights_v1_buggy.json.bak`. Same fix also addressed the "2 of 5 concepts compared" bug — v2 covers all 5 concepts with deterministic tie-group ranking.
- **For the next engagement in this category to know:**
  - Ingestibles trap words (`config/category_trap_words.yaml`): taste, flavor, dosage, dose, serving, ingredients, capsule, aftertaste, texture — audit prompts and insights topic schema against these.
  - If tuning lifestyle attribute weights for a CoD-viewer or similar creator-fandom niche, priors should skew: media_influence high, brand_adoption early/social, shopping_mindset impulse-tilted.
