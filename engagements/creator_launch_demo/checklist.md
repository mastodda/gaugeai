# Pre-Run Checklist

**Engagement:** Creator Launch Screening — Which Product Should JasonTheWeen Launch? (Demo)
**Analyst:** Miles
**Date:** 2026-07-10

> This is an illustrative demo, not a client study. Several boxes below are deliberately checked "no" or "flagged" — this engagement knowingly steps outside the paper-validated envelope (cross-category comparison + real-creator context). Those deviations are documented here as known risks, not oversights.

---

## Step 1 — Category identification

- [x] Product category identified explicitly. **Category:** CROSS-category creator merch — audio (headset), peripherals (keyboard), functional beverage (energy drink), apparel (hoodie), ingestibles (collagen peptides).
- [!] Category checked against `docs/reference/domain_suitability_checklist.md`. Each individual category is in/near the CPG-confidence zone, but **comparing across them is not**. See Step 5.
- [!] Category is NOT aspirational/identity-signaling. **FLAG:** creator merch is *inherently* identity-signaling — the whole premise is "would this creator's audience buy this because it's from him." This is intentional for the demo (we're measuring creator-audience fit), but it is outside the neutral-CPG comfort zone.

## Step 2 — Stimulus construction

- [x] Concept copy is neutral factual spec-sheet register (no marketing hype). Re-read each: reads as a spec, not an ad.
- [x] Price is a plain factual figure in each concept ($99 / $129 / $30 per 12-pack / $65 / $34). Not injected via marketing language.
- [x] Creator context is injected NEUTRALLY via the elicitation question only ("If JasonTheWeen — a Twitch streamer known for his IRL and gaming streams — launched this product…"). Factual identity, no hype. This is a deliberate extension to avoid relying on stale model memory of the creator.

## Step 3 — Question/prompt category-compatibility audit (the "fit" bug gate)

- [x] Elicitation question read against every category. Generic purchase-intent phrasing + neutral creator framing — no category-specific trap words.
- [!] Reasoning follow-up: default from `config/prompt_templates.json`. Because concepts span 5 categories, audit insights output against `config/category_trap_words.yaml` for ALL of: ingestibles (taste, flavor, dosage, serving, ingredients), apparel (fit, sizing), electronics (latency, build quality). The `discover_topics` LLM pre-pass should handle this, but verify no single category's vocabulary dominates the cross-category topic list.
- [x] Not copied from a prior engagement (built fresh for this demo).

## Step 4 — Persona tier and framing

- [x] Tier 1 vs Tier 2 choice intentional. **Chosen:** Tier 2 (full mode). **Why:** the qualitative "why they would / wouldn't buy" is the demo's headline, not the PI number.
- [x] **Tier 2 lifestyle weights appropriate for the audience.** `engagements/creator_launch_demo/lifestyle_attributes.json` overrides root: social_media_influenced 0.80, primarily_online 0.78, impulse 0.30, early_adopter 0.32, and — deliberately — fitness/performance kept LOW at 0.20 (variety/IRL audience, not a training audience). Conditional overrides removed (file scoped to the 18-26 audience). Directional, not measured.
- [!] Audience is a known niche (one creator's fandom). Flagged as **unvalidated for niche calibration** — narrow seeding risks stereotype collapse / reduced effective sample size (κ). Treat as a data point, not a validated read.

## Step 5 — Cross-category check

- [!] **DELIBERATELY VIOLATED.** The 5 concepts are NOT in the same category. Raw cross-category mean-PI comparison is not paper-supported: absolute PI is not comparable across categories (a cheap consumable will out-score a considered durable on price/commitment alone), so **do not report a raw PI horse race.** Report as an audience-FIT / odds-of-landing ranking + qualitative why. For a real engagement, add calibration anchors = the client's own past launches with known outcomes, one per category, and read each concept relative to its category anchor.

## Step 6 — Reporting setup

- [x] Deliverable leads with fit ranking + qualitative reasoning, NOT absolute mean PI.
- [x] Limitations disclosure included (cross-category unvalidated; niche audience; synthetic/illustrative; creator context injected).
- [x] Framed as hypotheses to validate against the client's real launch data, not as validated predictions.

## Step 7 — Final sign-off

- [x] All boxes reviewed. Open flags (Steps 1, 3, 4, 5) are **known, intentional deviations** for a demo that showcases a cross-category use case, not defects to fix before running.
- [x] Model: gpt-4o primary (most reliable scorer in prior peptide testing; flash-lite was unstable, ρ disagreement). Optional flash-lite cross-check run to detect soft rankings.
- [x] Checklist committed alongside the engagement config.

**Signed off by:** Miles  **Date:** 2026-07-10

---

## Post-run notes (fill after running)

- **Fit ranking held vs. expectation?** Expectation: hoodie + energy drink strongest (core streamer merch), peripherals mid, **collagen the deliberate stretch / likely laggard**. If collagen out-ranks the hoodie or headset, treat as an incoherence signal and do NOT send — same failure mode as the peptide run.
- **Cross-category sanity:** did a cheap consumable win purely on price? If so, that's the un-anchored cross-category artifact this checklist warns about — note it and lead with the qualitative fit read instead.
- **For the calibrated version:** request from the client, per category, at least one past launch with a known outcome (units per exposure, not raw sales) to serve as an anchor, plus first-party audience data to seed personas.
