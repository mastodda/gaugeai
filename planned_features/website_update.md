# Website Update Plan — `websiteonepager.html`

**Audience:** Claude Code / BMAD agents
**Goal:** Rewrite the public-facing one-pager so every claim is defensible against the current state of the product and validation evidence. Keep visual design, page structure, and brand voice; replace overclaiming copy with accurate copy that still sells.

**Hard rule:** If a claim is not directly supported by `VALIDATION_HANDOFF.md` or `PROJECT_HANDOFF.md`, it does not ship. No invented statistics. No paper-statistics presented as our statistics.

---

## 0. Source-of-truth reading order

Read these before making any changes:

1. **`VALIDATION_HANDOFF.md`** — the highest-authority document. Defines what we *can* and *cannot* claim. Sections 2 (TL;DR), 5 (Key findings), 6 (What the data does NOT support), 8 (Recommended methodology) are the binding ones.
2. **`PROJECT_HANDOFF.md`** — what the product actually does technically. Used for the "How it works" section accuracy check.
3. **`websiteonepager.html`** — the file being edited.

If the agents need to confirm something about the Maier paper, the source is `LLMs_Reproduce_Human_purchase_intent_via_Semantic_Similarity_Elicitation_of_Likert_Ratings.pdf`. Do not cite it for our results — only for methodology lineage.

---

## 1. Guardrails — claims that must be removed or rewritten

These are the specific overclaims currently on the page. Each one has the reason it's a problem and a defensible substitute. The agent should not negotiate these — fix all of them.

| Current claim | Location (line) | Why it's wrong | Allowed substitute |
|---|---|---|---|
| **"90%" big stat — "Correlation with human panel data (peer-reviewed methodology)"** | line 360–361 | That's the Maier paper's number across ~30 surveys with a representative US panel. Our pilot had 5 concepts and a 33-person convenience sample. Correlation on n=5 has CI ≈ ±0.5. Presenting the paper's number as ours fails any sophisticated buyer's first sniff test. | Replace the stat with **"5/5"** and the label **"Concepts correctly ranked in our pilot validation against 33 consumers."** Keep the same visual treatment. |
| **"~98% Cost reduction vs. traditional survey panels"** | line 368–369 | Directionally true, but the precision implies measurement we haven't done. Reads as marketing puffery next to the other stats. | Replace with **"<$500"** as the stat and label **"Per-concept cost vs. $15K–$30K for traditional panels"** — keeps the cost story, removes the false-precision percentage. (This number is already used downstream in the comparison table.) |
| **Method-note paragraph: "Our scoring method (Semantic Similarity Rating) achieves 90% of the maximum correlation ceiling set by human test-retest reliability — validated across multiple product categories with real consumer panel benchmarks."** | line 402–404 | Conflates the published research with our work. "Validated across multiple product categories" is true of the paper, not of us. | Replace with: **"Our scoring method (Semantic Similarity Rating) is based on peer-reviewed research by Maier et al. (2024), which validated the approach across 57 consumer concept surveys against real human panels. Our own pilot validation against 33 consumers correctly ranked all 5 tested concepts in agreement with human respondents."** |
| **Footer tagline: "Synthetic consumer research backed by peer-reviewed methodology."** | line 498 | This one is fine — keep it. (Listed here so the agent doesn't second-guess it.) | No change. |
| **Hero subhead: "AI-generated consumer panels that deliver purchase intent scores, Likert distributions, and rich qualitative feedback — in 24 hours, not 3 weeks."** | line 354 | "Purchase intent scores" implies absolute predictive PI, which the validation explicitly does not support. Subtle but matters. | Rewrite: **"AI-generated consumer panels that rank-order your concepts and surface qualitative drivers and barriers — in 24 hours, not 3 weeks."** |
| **Hero H1: "Test your product concepts before you test your budget"** | line 353 | Implies replacement of human research. Conflicts with our positioning as a directional pre-screen. | Rewrite: **"Rank-order your concepts before you commit your research budget"** — same emotional pull, accurate positioning. |
| **"How it works" intro: "Our pipeline is built on published academic research in LLM-based consumer simulation. No shortcuts — real statistical rigor, real distributions, real insight."** | line 377 | "Real statistical rigor" overstates current state — we don't yet have confidence intervals, effective sample size (κ), or multi-pilot validation. | Rewrite: **"Our pipeline implements peer-reviewed methodology (Maier et al., 2024) for converting LLM free-text responses into Likert distributions. Every concept is run through 100+ demographically-targeted synthetic respondents and scored against six independent reference sets."** — accurate, more concrete, still credible. |
| **"How it works" Step 03 copy: "Responses are scored into calibrated Likert distributions using semantic similarity — not forced numerical ratings."** | line 393 | "Calibrated" is the loaded word — implies absolute calibration we haven't demonstrated (in fact, the +1.0 positivity bias is the opposite of calibrated). | Rewrite: **"Responses are scored into Likert distributions using semantic similarity to anchor statements — never asking the LLM to pick a number, which produces center-clustered, low-signal results."** |
| **CTA section: "See it on your concept — free / Send us one real concept. We'll run it through our full pipeline and deliver a polished report. No cost, no commitment — just data."** | line 491–492 | Fine in spirit, but should be reframed as a pilot exchange to align with strategy of building validation data through pilots. | Rewrite: **"See it on your concept — pilot program."** And subhead: **"Send us 1–3 real concepts. We'll run them through the full pipeline and deliver a polished report at no cost. In exchange, we ask for permission to use the anonymized results as part of our ongoing methodology validation."** |

---

## 2. New section to add: "Where we are in our validation journey"

Insert a new section between "Best fit categories" (ends ~line 487) and the CTA (starts ~line 489). This section is the single biggest credibility lever — buyers will trust transparency far more than they'll trust polished claims.

**Section label:** `Where we are`
**Heading:** `Honest about what this is — and isn't`
**Use the same visual treatment as other rule-divided sections.**

Body copy (drop in verbatim, agent should not rewrite for "punchier" tone):

> SynthPanel is built on peer-reviewed academic methodology (Maier et al., 2024) and has completed its first internal validation pilot: 5 product concepts, 33 real consumers, perfect 5-of-5 ranking agreement with human respondents.
>
> What that means in practice:
>
> - **What we're confident about:** Rank-ordering concepts within an engagement. If concept A scores higher than concept B in our pipeline, that ordering held up in our pilot.
> - **What we're still validating:** Absolute purchase-intent scores. Our synthetic responses skew positive vs. human responses by a consistent margin — useful for relative comparison, not yet calibrated for absolute prediction.
> - **What we're upfront about:** One pilot is one data point. We're actively building our validation library across more categories and demographics. Pilot clients get the same rigor we used internally, plus a methodology + limitations doc with every engagement.
>
> If you're looking for a tool that ranks concepts faster and cheaper than full panels, this is ready. If you're looking for a drop-in replacement for traditional research, it isn't — and we'll tell you that on the intake call.

**Visual treatment:** plain prose, no decorative boxes, no icons. The unadorned tone *is* the signal. Use the same `.section-rule` and `.reveal` classes as adjacent sections so it inherits the page rhythm.

---

## 3. Comparison table — accuracy pass

Current table (line 412–452) is largely fine, but two rows need adjustment:

| Row | Issue | Fix |
|---|---|---|
| **"Iteration speed: Test 5 variants in a day"** | We tested 5 concepts but in 5 separate runs. "5 variants in a day" implies a workflow we haven't actually demonstrated end-to-end with a client. | Change to: **"Iterate same-day on multiple variants"** — accurate, still differentiating. |
| **"Niche demographics: Any demographic mix on demand"** | "Any" is an overclaim — the validation specifically flagged that narrower/younger demographics are a known limitation. | Change to: **"Demographics matched to your target on demand (subject to category and demographic suitability — we'll flag mismatches upfront)"** — wordier but honest. |

All other rows can stay as written.

---

## 4. Use cases — keep, but tighten one

The three personas (Brand & Innovation Teams, Startup Founders, Research Consultants) are all reasonable.

**Tighten the "Brand & Innovation Teams" copy.** Current: *"Screen 10 concepts before committing budget to validate the top 2 with a traditional panel. Cut your concept mortality rate in half."*

The "cut concept mortality in half" claim is unsupported. Change to: *"Screen 10 concepts to identify the top 2–3 worth committing real research budget to. Use SynthPanel for ranking; use traditional panels for absolute calibration."*

The other two use-cases are fine.

---

## 5. Best-fit section — reorder for honesty

Current section (line 477–487) lists `Food & beverage, personal care, household products, OTC health, pet products, consumer electronics accessories, DTC brands` as "high confidence."

Issue: our validation pilot covered 5 concepts in 5 *different* categories (cold brew, sparkling tonic, multivitamin, ice cream, linen shirt). That gives us *one data point per category*, not category-level confidence. We've been more thoroughly tested *across* categories than *within* any single one.

Rewrite as:

> **Where the methodology applies:** Everyday consumer products that someone can meaningfully evaluate from a description, image, or short video — food & beverage, personal care, household goods, OTC health, pet products, DTC apparel and accessories.
>
> **Where it's still being validated:** Higher-consideration purchases (luxury, financial products, B2B), highly novel categories where consumer mental models don't yet exist, and narrow demographic targets (e.g., niche subcultures). We'll tell you on the intake call if your concept is outside the validated zone — and what that means for confidence in the read.

Drop the "high confidence" / "not yet validated" headers since they imply more granular per-category validation than we have.

---

## 6. Stats block — final state

After the changes, the three-stat block reads:

| Stat | Label |
|---|---|
| **5/5** | Concepts correctly ranked in our pilot validation against 33 consumers |
| **24hr** | Turnaround from brief to delivered report |
| **<$500** | Per-concept cost vs. $15K–$30K for traditional panels |

This swaps one paper-stat (90%) for a real-pilot-stat (5/5), and one false-precision stat (~98%) for a concrete dollar number that's directly defensible.

---

## 7. What NOT to change

- Visual design, color palette, typography, layout, animations — leave alone
- Logo, navigation, footer — leave alone
- The four-step "How it works" structure — only copy changes inside the steps
- The brand voice (warm, confident, not corporate) — preserve it; the rewrites above were drafted to match
- The CTA email address `hello@synthpanel.com`
- The use-case structure (three cards) — only the Brand & Innovation copy changes

---

## 8. Acceptance checklist

Before considering this done, verify:

- [ ] No instance of "90%" remains anywhere on the page in any context that implies it's our number
- [ ] No instance of "~98%" remains
- [ ] No instance of the word "calibrated" applied to our output
- [ ] No instance of "validated across multiple product categories" or similar language that conflates the paper's validation with ours
- [ ] The Maier et al. citation appears at least once with explicit attribution
- [ ] The new "Where we are" section is present between Best Fit and CTA
- [ ] The hero H1 and subhead reflect ranking/pre-screening positioning, not absolute-PI prediction
- [ ] The CTA explicitly mentions the pilot exchange (anonymized validation use)
- [ ] The page still renders cleanly on mobile (no broken layouts from copy length changes)
- [ ] The page reads as confident and credible — not apologetic. Honesty is the asset; don't tip into self-flagellation.

---

## 9. Out of scope for this task

These are intentionally not part of this change set:

- Methodology + limitations one-pager (separate handoff)
- Adding a logo/branding refresh
- Adding case studies (we don't have any yet — the pilot is internal, not client-facing)
- Adding a pricing page (positioning is "free pilot → managed service quote" for now)
- Adding analytics, forms, or any backend changes
- Renaming the product (SynthPanel stays as the working name)

If the agent finds itself wanting to expand scope, stop and flag it instead.
