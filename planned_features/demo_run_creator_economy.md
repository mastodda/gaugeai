# Demo Run Spec — Creator-Campaign Creative Screening

**Purpose:** Build one illustrative SSR run for a discovery call with an Insights & Analytics Manager in the creator economy (HardScope). Not a CPG buyer — the run reframes the validated monadic concept test as **pre-launch creative-angle screening**, the one decision his world actually makes but can't test cheaply.

**Scope guardrail:** This is a config-only task. Create ONE new engagement JSON and verify it runs. Do NOT modify scoring math, reference sets, prompt templates, persona generator, or output schemas. If something seems to require touching those, stop and ask.

---

## What to build

1. A new engagement file: `config/demo_creator_campaign.json`
2. Activate **Tier 2** personas (place/symlink `lifestyle_attributes.json` next to it, per existing Tier 2 convention).
3. Dry-run, then a real run, then confirm it loads in the Streamlit explorer.

---

## The scenario (for context, not code)

A brand is launching a creator-led sponsored campaign for a fictional energy drink, **VOLT**. Marketing has 4 competing creative angles and wants a directional read on which resonates with the target audience *before* committing creator/media budget. SSR ranks the angles and surfaces the qualitative "why."

Energy drink chosen deliberately: heavy creator-marketing category, Gen-Z/young-millennial audience, clear angle differentiation.

---

## Concepts (4 angles, same product)

Use these as the `concepts` array. Same product, different positioning/hook — this is what makes it a clean monadic test.

```json
"concepts": [
  {
    "concept_id": "angle_performance",
    "name": "VOLT — Performance / Grind",
    "description": "VOLT is the fuel for people who outwork everyone. Clean caffeine, B-vitamins, zero sugar — engineered for the early mornings and late nights when you're building something. No gimmicks, just energy that performs when you do. The campaign features creators showing their real grind: 5am workouts, side hustles, all-nighters. Tagline: 'Earn it.'",
    "image_path": null
  },
  {
    "concept_id": "angle_community",
    "name": "VOLT — Community / Belonging",
    "description": "VOLT is what brings the crew together. Whether it's a gaming session, a group ride, or a late study night, VOLT is the shared spark that keeps the energy up for everyone. Clean caffeine, zero sugar. The campaign features creators with their communities — squads, servers, group chats. Tagline: 'Better together, fully charged.'",
    "image_path": null
  },
  {
    "concept_id": "angle_rebellion",
    "name": "VOLT — Rebellion / Anti-Establishment",
    "description": "VOLT isn't for people who follow the rules. It's for the ones doing it their own way — ignoring the playbook, building outside the system, refusing the 9-to-5 script. Clean caffeine, zero sugar, zero apologies. The campaign features creators who walked away from the expected path. Tagline: 'Run your own program.'",
    "image_path": null
  },
  {
    "concept_id": "angle_wellness",
    "name": "VOLT — Wellness / Balance",
    "description": "VOLT gives you clean energy without the crash or the jitters. Natural caffeine from green tea, adaptogens, B-vitamins, zero sugar — energy that fits a balanced life, not one that runs you into the ground. The campaign features creators with calm, intentional routines: mindful mornings, focused work blocks, real rest. Tagline: 'Energy, in balance.'",
    "image_path": null
  }
]
```

---

## Survey question (the one reframe)

The validated default is "How likely would you be to purchase this product?" For creative screening, intent-to-engage reads more honestly than purchase intent, but **the reference sets are calibrated to purchase-intent phrasing.** To stay on the validated path, keep `type: "purchase_intent"` and the default reference sets, but adjust the surface wording to present the angle as an ad concept:

```json
"survey_question": {
  "type": "purchase_intent",
  "text": "Imagine you saw this campaign from a creator you follow. How likely would you be to buy this product?",
  "reference_sets_file": "reference_sets.json"
}
```

> ⚠️ Note for Miles: keep scoring on purchase_intent + default reference sets. Do NOT swap in a new "appeal" anchor gradient for a demo — that's an unvalidated change. The ranking across angles is the deliverable; absolute PI is offset (known +1.0 positivity bias), so present rankings, not absolute scores.

---

## Audience panel (target consumer, not US-general)

Skew young and media-influenced — this is the creator-economy audience.

```json
"demographics": {
  "panel_size": 80,
  "age_range": [18, 34],
  "gender_distribution": { "woman": 0.48, "man": 0.50, "nonbinary": 0.02 },
  "region_distribution": { "Midwest": 0.21, "Northeast": 0.17, "South": 0.38, "West": 0.24 },
  "income_distribution": { "low": 0.30, "moderate": 0.45, "upper-moderate": 0.20, "high": 0.05 },
  "ethnicity_distribution": null
}
```

If the persona generator rejects `nonbinary` (not in the validated gender set), drop it and renormalize woman/man — do not patch the generator.

---

## Pipeline block

Same defaults as the example engagement. Keep `gpt-4o`, seed 42.

```json
"pipeline": {
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "llm_temperature": 0.5,
  "llm_top_p": 0.9,
  "reasoning_temperature": 1.0,
  "samples_per_persona": 2,
  "embedding_model": "text-embedding-3-small",
  "ssr_epsilon": 0.0,
  "ssr_temperature": 1.0,
  "seed": 42
}
```

`_meta` block: label clearly as illustrative/synthetic.

```json
"_meta": {
  "engagement": "Demo: VOLT Creator Campaign — Creative Angle Screening",
  "client": "Illustrative (HardScope discovery call)",
  "date": "2026-06-21",
  "analyst": "Miles",
  "notes": "Demo run. 4 creative angles for one fictional energy drink, screened against a young, media-influenced panel. Tier 2 personas. Present RANKINGS not absolute PI. Synthetic/illustrative — not a real client study."
}
```

---

## Steps for the Claude Code session

1. Assemble the four blocks above into `config/demo_creator_campaign.json`.
2. Ensure `lifestyle_attributes.json` is alongside it (Tier 2 trigger). Confirm the existing Tier 2 path/convention rather than inventing one.
3. Dry run — validate config + cost estimate, no API calls:
   ```bash
   python run_pipeline.py --engagement config/demo_creator_campaign.json --dry-run
   ```
4. If clean, full run:
   ```bash
   python run_pipeline.py --engagement config/demo_creator_campaign.json --seed 42
   ```
5. Generate insights if not auto-run, then load in the explorer:
   ```bash
   streamlit run explorer/app.py -- --data-dir output/<run_dir>
   ```
6. Report back: the concept ranking table, and whether the four angles separated cleanly (if 3+ angles tie, the demo is weak — flag it).

---

## Demo-day focus (for Miles, not the agent)

- Lead the call with **discovery questions**, not this. Hold the demo unless he asks.
- When shown: open on **Tab 2 (Insights)** and **Tab 5 (Responses)** — the qualitative "why angle X lands, why Y flops" with quotes is what reads as *insight* to someone in his seat. The PI math is secondary.
- Framing line: "Ranking-based directional read, ~a day, synthetic panel — not a replacement for a YouGov study, a cheap filter before one."
- Do NOT cite the 90% correlation figure — that's Maier's, not your data.
