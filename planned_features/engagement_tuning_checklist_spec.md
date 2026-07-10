# SSR Toolkit — Engagement Parameter Tuning Spec

**Purpose of this document:** This is a handoff spec for a new Claude session. Use it to build a comprehensive, runnable checklist/tool that gets applied every time a new engagement is configured — before any pipeline run. The goal is to systematically separate what must stay fixed (protected core, paper-validated) from what must be re-tuned per engagement (population/category-specific), and to catch category-mismatch bugs before they reach a client (e.g., a "fit" question written for apparel silently reused for a supplement engagement).

Read `/mnt/project/PROJECT_HANDOFF.md` and `/mnt/project/VALIDATION_HANDOFF.md` for full pipeline context before building on this spec.

---

## 1. The Core Failure Mode This Document Exists to Prevent

Engagement configs get copied/adapted from prior engagements. Category-specific language (question phrasing, reference sets, persona framing, reasoning prompts) can silently persist across categories where it no longer makes sense — e.g., asking a supplement panel about "fit," a phrase meaningful for apparel and meaningless (or misleading) for ingestibles. These bugs don't crash the pipeline. They produce plausible-looking, silently wrong data. The checklist below exists to catch this class of error at config time, not after the client has the deck.

---

## 2. Protected Core — Must NOT Change Between Engagements

These are validated by the Maier et al. paper and/or your own pilot. Changing any of these per-engagement is not "tuning," it's abandoning the method. If diagnostics ever suggest one of these needs to change, treat that as evidence of a deeper problem (see Section 6), not a parameter to adjust.

- **Two-stage elicitation structure.** Free-text first, no numeric scale shown to the LLM, ever.
- **SSR scoring math.** Embedding → cosine similarity → min-subtraction → PMF normalization. Domain-agnostic. Do not touch `ssr_scoring.py` per engagement.
- **Ensemble averaging across all 6 reference sets.** Generic, domain-independent phrasing is a deliberate feature. Do not swap in category-specific reference sets without a full re-validation cycle.
- **Stimulus fidelity discipline.** Image-only or neutral factual concept cards. Never marketing-register copy. Raw price figures are permitted but currently unvalidated in isolation (see Section 5) — track outcomes closely.
- **Reporting discipline.** Concept ranking is the deliverable. Never present absolute PI or Top-2-Box as predictive/absolute to a client.
- **Reference statement anchors themselves.** The 6 sets' actual wording stays generic across all categories — this genericness is what makes ranking transferable in the first place.

---

## 3. Adaptable Parameters — Must Be Re-Tuned Per Engagement

- **Demographic sampling distributions** (age/income center) — shift to match the actual target audience. Reliability of age/income as signal is *assumed* to transfer from general population validation, not proven for niche audiences — flag this as an open assumption in engagement notes.
- **Tier 2 lifestyle-attribute distribution weights** — the six psychographic dimensions (household comp, shopping mindset, health orientation, brand adoption, shopping channel, media influence) are a valid framework, but their weightings are US-general-population priors. Re-source for niche audiences (e.g., creator-economy skews early-adopter/social-media-driven/impulse) rather than assuming baseline weights apply.
- **Category anchor concepts** (for calibration-ladder cross-category comparisons) — by design, these change every engagement. Requires at least one past-outcome-known concept per category being tested.
- **Price presentation** — raw dollar figures, isolated from marketing-register copy. Full notes in Section 5; treat as an open validation question, not a solved parameter.
- **Interpretation/reporting baselines** — what counts as a "good" pos:neg ratio or Top-2-Box differs for low-frequency/high-price categories vs. habitual CPG. Adjust client-facing interpretation, not the underlying scoring.
- **Elicitation and reasoning question phrasing — CATEGORY-COMPATIBILITY CHECK REQUIRED.** This is the fix for the "fit" bug. See Section 4, Step 3.

---

## 4. Pre-Engagement Checklist

Run this in full before launching any new engagement. Treat it as a gate, not a suggestion.

**Step 1 — Category identification**
- [ ] Identify the product category explicitly (not just "consumer good" — be specific: ingestible/supplement, apparel, hard good/electronics, beverage, etc.)
- [ ] Check category against domain suitability list (`domain_suitability_checklist.md`). Confirm high-confidence category, or flag as unvalidated/experimental and note this explicitly in the engagement brief.
- [ ] If category is aspirational/luxury/identity-signaling (e.g., bags, premium apparel) — flag as high-risk. This is a known-weak zone (Halden/Hearth precedent).

**Step 2 — Stimulus construction**
- [ ] Concept card is image-based, neutral factual copy only (no marketing-register adjectives — no "adaptogenic," "artisanal," "ethically sourced," etc.)
- [ ] Price is presented as a plain factual figure, kept isolated from marketing-register language (Section 5).
- [ ] Re-read the concept description out loud and ask: would this read as a spec sheet, or as an ad? If it reads as an ad, strip further.

**Step 3 — Question/prompt category-compatibility audit (catches the "fit" bug)**
- [ ] Read every question and prompt template scheduled for this engagement — elicitation question, reasoning follow-up, any secondary questions (e.g., "concept relevance") — line by line, in light of the actual product category.
- [ ] For each category-flavored word or phrase (e.g., "fit," "wear," "taste," "install," "use daily"), confirm it is semantically valid for this specific product. Do not assume a template inherited from a prior engagement is generic just because it was generic for its original category.
- [ ] If a prior engagement's config file is being copied as a starting point, do a full diff read of every prompt field against the new category — do not assume unchanged fields are safe by default.
- [ ] Maintain (or start) a small glossary of category-specific trap words per category (apparel: fit, wear, size; ingestibles: taste, dosage, ingredients; hard goods: durability, setup, compatibility) to check against during audits.

**Step 4 — Persona tier and framing**
- [ ] Confirm Tier 1 vs Tier 2 choice is intentional for this engagement (Tier 1 = paper-validated scoring baseline; Tier 2 = richer reasoning, ~0.5 lower PI, ranking preserved).
- [ ] If using Tier 2, confirm lifestyle attribute weightings are appropriate for the target audience, not left at default US-general-population priors, if the audience is known to be niche.
- [ ] If audience is a known niche (e.g., a specific creator's fanbase), flag this run as **unvalidated for niche calibration** in the engagement metadata until an A/B against generic-panel results has been run.

**Step 5 — Cross-category check**
- [ ] If this engagement includes multiple concepts, confirm they are within the same category. If concepts span categories, do not rank them directly against each other — either split into separate engagements or apply the calibration-ladder protocol (category-matched anchor concepts with known outcomes) before comparing.

**Step 6 — Reporting setup**
- [ ] Confirm output framing will lead with ranking/pos:neg ratio/Top-2-Box, not mean PI.
- [ ] Confirm limitations disclosure is included in the deliverable (small-N validation history, marketing-language sensitivity, demographic-transfer assumptions, category-validation status from Step 1).
- [ ] If this is a novel category or niche audience, note explicitly that this run is a data point toward validation, not a validated claim.

**Step 7 — Final sign-off**
- [ ] All boxes above checked and initialed before the pipeline is run.
- [ ] Engagement config archived with this checklist attached, so future engagements copying this config inherit the audit trail, not just the settings.

---

## 5. Pricing in Concept Stimulus (Current Approach)

**Decision:** Concept cards will include actual price figures (raw dollar amounts), not category-relative tier labels. The pipeline will rely on the LLM persona to apply appropriate category-specific price context.

**Known open risk (flag in every engagement using this approach):** The one internal data point available (image+text pilot test) showed the highest-priced concept in that run (a $148 shirt) dropped most sharply when raw price was introduced, and that same run also broke concept ranking overall (ρ = −0.10) — though that run also introduced marketing-dense text simultaneously, so price and marketing-register effects were not isolated from each other. Whether raw price alone (without marketing-dense copy) produces the same effect is untested. Treat every engagement using raw price as a live data point on this question, not a settled practice.

**Checklist for engagements using raw price:**
- [ ] Price is presented as a plain factual figure, isolated from marketing-register copy (to avoid conflating price sensitivity with the marketing-language confound already documented).
- [ ] Log whether ranking (ρ) holds and whether high-price concepts are penalized in a way that seems proportionate to real category norms, vs. over-penalized against a generic retail default.
- [ ] Accumulate results across engagements to build an actual evidence base on raw price effects — this is currently unvalidated, in either direction.

---

## 6. Reference: Failure Diagnostic Sequence (if a tuned engagement produces bad rankings)

If a properly-checklisted engagement still produces poor/inverted rankings against known outcomes, do not immediately re-tune. Run in order:
1. Check response variance (collapse vs. healthy spread — stereotype-collapse signal).
2. Read raw free-text responses — do they sound like the target audience? Do scores match the text?
3. Check whether failure is uniform across concepts or concentrated in 2-3.
4. Decompose ground truth — was the outcome preference-driven or distribution/timing-driven? Only preference-driven outcomes are a fair test of this method.
5. Only after 1–4, consider touching adaptable parameters (Section 3) — with a fresh holdout, never the same dataset used to diagnose.

---

## 7. Instruction to the Building Session

Using the sections above, build out:
- A structured, fillable checklist artifact (config file, form, or script) that enforces Section 4 before an engagement can be launched.
- A category trap-word glossary (starter list in Step 3) as an extensible config file, not hardcoded logic, so it can grow as new categories are tested.
- A simple log/tracker for the raw-price validation question (Section 5) — capturing, per engagement, whether ranking held and whether price-sensitive concepts behaved proportionately — so this becomes an evidence base rather than a one-off judgment call.
