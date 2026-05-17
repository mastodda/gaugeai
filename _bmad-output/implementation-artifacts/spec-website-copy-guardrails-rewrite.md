---
title: 'Website Copy — Guardrails Rewrite'
type: 'chore'
created: '2026-05-17'
status: 'done'
baseline_commit: 'af208c64b716d699212705289c005f6b16c4de78'
context:
  - '{project-root}/WEBSITE_UPDATE_PLAN.md'
  - '{project-root}/docs/VALIDATION_HANDOFF.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `website/index.html` contains overclaiming copy that presents Maier et al.'s research statistics as Miles Stoddart's own results, implies absolute purchase-intent prediction the validation data does not support, and positions the service as a replacement for human research rather than a directional pre-screen.

**Approach:** Replace all overclaiming copy with defensible alternatives per `WEBSITE_UPDATE_PLAN.md`, insert a new "Where we are" transparency section between Best Fit and CTA, and restructure the Best Fit section. Visual design, layout, and animations are untouched.

## Boundaries & Constraints

**Always:**
- Every claim must be grounded in `VALIDATION_HANDOFF.md` or `PROJECT_HANDOFF.md`
- Brand name: "Miles Stoddart" for the site; "our service" or "our pipeline" when referring to the pipeline
- Maier et al. (2024) must be cited by name with explicit attribution wherever the methodology is referenced
- Visual design, color palette, typography, animations, nav, footer links, email addresses — leave entirely alone
- Verbatim copy blocks specified in the plan must be used exactly as written (adapted only for brand name)

**Ask First:**
- Any copy not explicitly covered by the plan that appears to need updating
- Any structural or layout change beyond what is specified

**Never:**
- Invent statistics or claim percentages not in `VALIDATION_HANDOFF.md`
- Use "SynthPanel" or "Miles Stoddart Consulting" anywhere
- Apply "calibrated" to describe our output
- Quote a specific correlation % as our own result (the 90% figure belongs to the Maier paper)
- Add sections, change email addresses, or touch the comparison table beyond the two specified rows

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior |
|----------|--------------|---------------------------|
| Stat block stat 1 | `90%` / "Correlation with human panel data" | `5/5` / "Concepts correctly ranked in our pilot validation against 33 consumers" |
| Stat block stat 3 | `~90%` / "Cost reduction vs. traditional survey panels" | `<$500` / "Per-concept cost vs. $15K–$30K for traditional panels" |
| Method callout | References 90% SSR correlation as ours | Attributes it to Maier et al. (2024) + cites our own 5/5 pilot result |
| "Where we are" section | Absent | Present between Best Fit and CTA, using `bg-gray` + `section reveal` CSS classes |

</frozen-after-approval>

## Code Map

- `website/index.html` — sole file; all changes are copy-only except one new HTML section insertion

## Tasks & Acceptance

**Execution:**
- [x] `website/index.html` — **Hero H1**: replace `Test your concepts<br><span class="accent">before you test<br>your budget</span>` with `Rank-order your concepts<br><span class="accent">before you commit<br>your research budget</span>` — removes implication of replacement for traditional research
- [x] `website/index.html` — **Hero subhead**: replace `AI-generated consumer panels that deliver purchase intent scores, Likert distributions, and rich qualitative feedback in 24 hours.` with `AI-generated consumer panels that rank-order your concepts and surface qualitative drivers and barriers — in 24 hours, not 3 weeks.` — removes "purchase intent scores" (implies absolute PI prediction)
- [x] `website/index.html` — **Stat 1**: change `stat-number` from `90%` to `5/5`; change `stat-label` to `Concepts correctly ranked in our pilot<br>validation against 33 consumers` — replaces paper's stat with our own pilot result
- [x] `website/index.html` — **Stat 3**: change `stat-number` from `~90%` to `<$500`; change `stat-label` to `Per-concept cost vs.<br>$15K–$30K for traditional panels` — replaces false-precision percentage with concrete defensible number
- [x] `website/index.html` — **How it works intro** (`section-intro` paragraph): replace with `Our pipeline implements peer-reviewed methodology (Maier et al., 2024) for converting LLM free-text responses into Likert distributions. Every concept is run through 100+ demographically-targeted synthetic respondents and scored against six independent reference sets.` — removes "real statistical rigor" overclaim
- [x] `website/index.html` — **Step 03 body**: replace `Each synthetic respondent reacts in their own words. Responses are scored into calibrated Likert distributions using semantic similarity.` with `Each synthetic respondent reacts in their own words. Responses are scored into Likert distributions using semantic similarity to anchor statements — never asking the LLM to pick a number, which produces center-clustered, low-signal results.` — removes "calibrated"
- [x] `website/index.html` — **Method callout body**: replace `Our scoring method (Semantic Similarity Rating) achieves 90% of the maximum correlation ceiling set by human test-retest reliability — validated with real consumer panel benchmarks.` with `Our scoring method (Semantic Similarity Rating) is based on peer-reviewed research by Maier et al. (2024), which validated the approach across 57 consumer concept surveys against real human panels. Our own pilot validation against 33 consumers correctly ranked all 5 tested concepts in agreement with human respondents.` — attributes paper stat to paper; adds our own defensible result
- [x] `website/index.html` — **Comparison table — Iteration speed**: change `Test 5 variants in a day` to `Iterate same-day on multiple variants` — removes undemonstrated end-to-end claim
- [x] `website/index.html` — **Comparison table — Niche demographics**: change `Any demographic mix on demand` to `Demographics matched to your target on demand (subject to category and demographic suitability — we'll flag mismatches upfront)` — removes "any" overclaim flagged in validation
- [x] `website/index.html` — **Brand & Innovation Teams card**: replace `Screen 10 concepts before committing budget to validate the top 2 with a traditional panel. Cut your concept mortality rate in half.` with `Screen 10 concepts to identify the top 2–3 worth committing real research budget to. Use our service for ranking; use traditional panels for absolute calibration.` — removes unsupported mortality claim
- [x] `website/index.html` — **Best Fit section body**: remove the `.categories-list` div and `.caveat` paragraph; replace with two bold-lead paragraphs: `<p><strong>Where the methodology applies:</strong> Everyday consumer products that someone can meaningfully evaluate from a description, image, or short video — food & beverage, personal care, household goods, OTC health, pet products, DTC apparel and accessories.</p>` and `<p class="caveat"><strong>Where it's still being validated:</strong> Higher-consideration purchases (luxury, financial products, B2B), highly novel categories where consumer mental models don't yet exist, and narrow demographic targets (e.g., niche subcultures). We'll tell you on the intake call if your concept is outside the validated zone — and what that means for confidence in the read.</p>` — removes per-category confidence implied by tag list
- [x] `website/index.html` — **Insert "Where we are" section** between closing `</div>` of Best Fit and the `<!-- CTA -->` comment. Use `bg-white` wrapper + `section reveal`. Section label: `Where we are`. H2: `Honest about what this is — and isn't`. Body: verbatim copy from `WEBSITE_UPDATE_PLAN.md` §2, with "SynthPanel" replaced by "Our service". Render the three bullet points as a `<ul>` with `<strong>` leads. Plain prose, no icons, no decorative boxes.
- [x] `website/index.html` — **CTA H2**: replace `See it on your concept for free` with `See it on your concept — pilot program` — aligns with validation-building strategy
- [x] `website/index.html` — **CTA body paragraph**: replace `Send us your real concept. We'll run it through our full pipeline and deliver a polished report. No cost, no commitment.` with `Send us 1–3 real concepts. We'll run them through the full pipeline and deliver a polished report at no cost. In exchange, we ask for permission to use the anonymized results as part of our ongoing methodology validation.` — frames as pilot exchange

**Acceptance Criteria:**
- Given the file is opened in a browser, when inspecting the stats block, then it shows `5/5`, `24hr`, and `<$500` — no `%` stat remains
- Given a grep of the file, when searching for `90%`, then zero matches are found
- Given a grep of the file, when searching for `calibrated`, then zero matches are found
- Given a grep of the file, when searching for `Any demographic mix`, then zero matches are found
- Given a grep of the file, when searching for `Maier`, then at least two matches are found (callout + "Where we are" section)
- Given the page is loaded, when scrolling between Best Fit and the CTA, then the "Honest about what this is — and isn't" section is visible
- Given a mobile viewport, when the page is loaded, then no layout breaks from copy-length changes

## Design Notes

The "Where we are" section uses the same alternating background rhythm as adjacent sections — Best Fit is `bg-white`, so this new section uses `bg-white` as well (CTA is already dark/black, so it acts as the natural terminator). The body copy renders as: one opening paragraph, one short lead-in sentence, a `<ul>` with three `<li>` items using `<strong>` for the bold leads, then a closing paragraph. No `.method-callout` box — the unadorned prose tone is intentional.

## Verification

**Commands:**
- `grep -c "90%" website/index.html` — expected: `0`
- `grep -c "calibrated Likert\|calibrated for\|calibrated output" website/index.html` — expected: `0` (the phrase "not yet calibrated for absolute prediction" in the transparency section is permitted — it acknowledges a limitation, not an overclaim)
- `grep -c "Maier" website/index.html` — expected: `2` or more

**Manual checks:**
- Open `website/index.html` in browser; verify stats block shows `5/5 / 24hr / <$500`
- Verify "Honest about what this is — and isn't" section appears between Best Fit and CTA
- Resize to mobile width; confirm no text overflow or broken grid layouts

## Suggested Review Order

**Stats block — the three headline claims**

- Pilot-result `5/5` replaces paper's `90%`; `<$500` replaces false-precision `~90%`
  [`index.html:575`](../../website/index.html#L575)

**Hero — positioning shift from absolute PI to ranking**

- H1 and subhead reframed from "purchase intent scores" to rank-ordering/pre-screen
  [`index.html:545`](../../website/index.html#L545)

**Method callout — attribution correction**

- 90% attributed to Maier et al. (2025), replaced by our own 5/5 pilot result
  [`index.html:625`](../../website/index.html#L625)

**New "Where we are" section — transparency insert**

- Core credibility section; verbatim pilot disclosure between Best Fit and CTA
  [`index.html:703`](../../website/index.html#L703)

**How it works — copy accuracy**

- Section intro now cites Maier et al. (2025) explicitly with methodology detail
  [`index.html:598`](../../website/index.html#L598)
- Step 03 removes "calibrated"; explains semantic similarity approach
  [`index.html:613`](../../website/index.html#L613)

**Comparison table — two overclaiming rows**

- Iteration speed and niche demographics rows tightened
  [`index.html:648`](../../website/index.html#L648)

**Best Fit section — restructured from tag cloud to prose**

- Category list replaced with applies/still-validating two-paragraph structure
  [`index.html:695`](../../website/index.html#L695)

**CTA — pilot exchange framing**

- H2 and body reframed as pilot program with validation exchange ask
  [`index.html:720`](../../website/index.html#L720)

**CSS additions**

- `.prose-lead`, `.prose-list`, `.prose-close` classes for "Where we are" section
  [`index.html:481`](../../website/index.html#L481)
- `overflow-wrap: break-word` added to `.comparison td` for long demographics cell
  [`index.html:360`](../../website/index.html#L360)

## Spec Change Log

- **Review loop 1 patches applied (2026-05-17):** (1) Citation year corrected 2024→2025 per CLAUDE.md/PROJECT_HANDOFF.md — plan had wrong year. (2) "Where we are" wrapper changed bg-white→bg-gray to maintain alternating visual rhythm. (3) Verbatim "not yet calibrated for absolute prediction" restored — spec verification criterion was too broad; the word is permissible when acknowledging a limitation. Verification criterion updated to target overclaiming patterns only. (4) Inline styles replaced with .prose-lead/.prose-list/.prose-close CSS classes for mobile responsiveness. (5) Added overflow-wrap/word-break to .comparison td for long demographics cell. Deferred: pre-existing "Creating Agencies" typo, reveal+JS-disabled (affects all sections), dead .categories-list CSS.
