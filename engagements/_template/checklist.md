# Pre-Run Checklist

Complete before launching this engagement. Every unchecked box will trigger a warning at run start (see `run_pipeline.py --skip-checklist` to bypass for throwaway experiments only).

Source spec: `planned_features/engagement_tuning_checklist_spec.md`.

**Engagement:** <fill in>
**Analyst:** <fill in>
**Date:** <YYYY-MM-DD>

---

## Step 1 — Category identification

- [ ] Product category identified explicitly (not "consumer good" — specify: ingestible/supplement, apparel, hard good/electronics, beverage, personal care, pet, OTC, etc.). **Category:** <fill in>
- [ ] Category checked against `docs/reference/domain_suitability_checklist.md`. Confidence: <high / medium / experimental — flag>
- [ ] Category is NOT aspirational/luxury/identity-signaling (bags, premium apparel, etc.). If it IS, flag as high-risk (Halden/Hearth precedent) in engagement notes.

## Step 2 — Stimulus construction

- [ ] Concept card is image-based OR neutral factual copy only. No marketing-register adjectives ("adaptogenic," "artisanal," "ethically sourced," "premium," "revolutionary," etc.).
- [ ] Price (if included) is a plain factual figure, isolated from marketing-register language (see Section 5 of spec).
- [ ] Re-read every concept description out loud: reads as a spec sheet, not an ad.

## Step 3 — Question/prompt category-compatibility audit (the "fit" bug gate)

- [ ] Read the elicitation question line by line against this category. **Elicitation question:** <paste it here>
- [ ] Read the reasoning follow-up question line by line against this category. **Reasoning question:** <paste it here>
- [ ] Read any secondary questions (concept relevance, etc.) line by line against this category.
- [ ] Every category-flavored word or phrase (fit, wear, taste, install, use daily, dosage, ingredients, durability, setup, sizing, flavor, etc.) has been confirmed as semantically valid for this specific product.
- [ ] Cross-checked against `config/category_trap_words.yaml` — no trap words for this category leak through.
- [ ] If this config was copied from a prior engagement: full diff read of every prompt field against the new category. Do not assume unchanged fields are safe by default.

## Step 4 — Persona tier and framing

- [ ] Tier 1 vs Tier 2 choice is intentional. **Chosen:** <Tier 1 / Tier 2>. **Why:** <fill in>
- [ ] If Tier 2: lifestyle attribute weightings appropriate for the target audience (not left at US-general-population priors) if the audience is niche.
- [ ] If audience is a known niche (specific creator fanbase, gaming subculture, etc.): engagement metadata explicitly flags this run as **unvalidated for niche calibration** until an A/B against generic-panel results has been run.

## Step 5 — Cross-category check

- [ ] All concepts in this engagement are within the same category. If they span categories, either split into separate engagements OR apply calibration-ladder protocol (category-matched anchor concepts with known outcomes) before comparing.

## Step 6 — Reporting setup

- [ ] Deliverable will lead with ranking / pos:neg ratio / Top-2-Box, NOT absolute mean PI.
- [ ] Limitations disclosure will be included: small-N validation history, marketing-language sensitivity, demographic-transfer assumptions, category-validation status.
- [ ] If novel category or niche audience: deliverable will explicitly note this run is a data point toward validation, not a validated claim.

## Step 7 — Final sign-off

- [ ] All boxes above checked and reviewed.
- [ ] This checklist is committed alongside the engagement config so future engagements copying this config inherit the audit trail.

**Signed off by:** <initials>  **Date:** <YYYY-MM-DD>

---

## Post-run notes

Filled in after the run for the accumulating evidence base. Fine to leave blank at run time.

- **Ranking held vs. expected?** <yes / no / mixed / no expectation>
- **Raw-price observations (if applicable):** <log in `docs/reference/raw_price_validation_log.md`>
- **Category-mismatch surprises (topic analysis reporting nonsense for this category)?** <list any>
- **Anything for the next engagement in this category to know?** <fill in>
