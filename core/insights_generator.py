"""
insights_generator.py — Synthesize actionable insights from SSR pipeline responses.

V2: Pre-computes real segment-level metrics before the LLM call so the model
synthesizes actual patterns rather than inventing statistics. Generates a single
comparative analysis across all concepts rather than per-concept summaries.

Architecture:
  1. Pre-compute: segment means, frequency counts, keyword extraction
  2. LLM call: one call with all pre-computed data + sampled verbatims
  3. Output: structured JSON with concept comparison, segment insights, actions

Cost: ~$0.05-0.10 total using GPT-4o-mini (one call with ~80-120K input tokens).
"""

import json
import re
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path.home() / "Documents/Projects/.env")


# ── Sentiment bands (matching reviews explorer) ────────────────────────

SENTIMENT_BANDS = [
    ("strong",   4.0, 5.01, "Strong intent (4.0-5.0)"),
    ("leaning",  3.5, 4.0,  "Leaning positive (3.5-4.0)"),
    ("neutral",  2.8, 3.5,  "Neutral (2.8-3.5)"),
    ("soft_neg", 2.2, 2.8,  "Leaning negative (2.2-2.8)"),
    ("low",      0.0, 2.2,  "Low intent (< 2.2)"),
]


def _bucket(rating: float) -> str:
    for key, lo, hi, _ in SENTIMENT_BANDS:
        if lo <= rating < hi:
            return key
    return "neutral"


def _bucket_label(key: str) -> str:
    for k, _, _, label in SENTIMENT_BANDS:
        if k == key:
            return label
    return key


# ── Pre-computation: real metrics before LLM sees anything ─────────────

def _shorten_lifestyle(val: str) -> str:
    """Strip long descriptions after em dash."""
    return val.split("\u2014")[0].strip() if "\u2014" in val else val


def _age_band(age: int) -> str:
    if age < 30: return "18-29"
    if age < 45: return "30-44"
    if age < 60: return "45-59"
    return "60+"


def _add_to_axis(axes, axis_key, axis_val, pi, band):
    if axis_key not in axes:
        axes[axis_key] = {}
    if axis_val not in axes[axis_key]:
        axes[axis_key][axis_val] = {"ratings": [], "bands": Counter()}
    axes[axis_key][axis_val]["ratings"].append(pi)
    axes[axis_key][axis_val]["bands"][band] += 1


def compute_segment_metrics(
    respondents: list[dict],
    persona_lookup: dict,
) -> dict:
    """
    Compute mean PI, count, and sentiment distribution for every
    demographic and lifestyle segment. Returns structured dict.
    """
    axes = {}

    for r in respondents:
        pid = r["persona_id"]
        p = persona_lookup.get(pid, {})
        pi = r["expected_rating"]
        band = _bucket(pi)

        for axis_key, axis_val in [
            ("income", p.get("income")),
            ("age_band", _age_band(p.get("age", 0))),
            ("region", p.get("region")),
        ]:
            if axis_val:
                _add_to_axis(axes, axis_key, axis_val, pi, band)

        lifestyle = p.get("lifestyle", {})
        for dim, val in lifestyle.items():
            short_val = _shorten_lifestyle(val)
            _add_to_axis(axes, dim, short_val, pi, band)

    result = {}
    for axis_key, segments in axes.items():
        axis_data = {}
        for seg_val, data in segments.items():
            ratings = data["ratings"]
            n = len(ratings)
            mean_pi = sum(ratings) / n if n > 0 else 0
            bands = data["bands"]
            total_bands = sum(bands.values())
            band_pcts = {b: round(c / total_bands, 2) for b, c in bands.items()} if total_bands > 0 else {}

            axis_data[seg_val] = {
                "n": n,
                "mean_pi": round(mean_pi, 2),
                "sentiment_distribution": band_pcts,
            }
        result[axis_key] = axis_data

    return result


def compute_keyword_frequencies(respondents: list[dict], keyword_groups: dict) -> dict:
    """Count mentions of product-relevant terms across all responses.

    keyword_groups is now supplied by the caller (from discover_topics for this
    engagement) rather than hardcoded, so topic labels reflect what respondents
    actually talked about in this category — not an apparel-centric prior.
    """
    counts = {group: 0 for group in keyword_groups}
    total = len(respondents)

    for r in respondents:
        text = (r.get("free_text_response", "") + " " + r.get("reasoning_response", "")).lower()
        for group, keywords in keyword_groups.items():
            if any(kw in text for kw in keywords):
                counts[group] += 1

    return {
        group: {"count": count, "pct": round(count / total * 100) if total > 0 else 0}
        for group, count in counts.items()
    }


def _sample_verbatims(respondents: list[dict], n_per_band: int = 3) -> dict:
    """Sample representative verbatims from each sentiment band."""
    bands = {}
    for r in respondents:
        band = _bucket(r["expected_rating"])
        if band not in bands:
            bands[band] = []
        bands[band].append(r)

    sampled = {}
    for band_key, resps in bands.items():
        sorted_resps = sorted(resps, key=lambda x: x["expected_rating"])
        n = len(sorted_resps)
        if n <= n_per_band:
            indices = list(range(n))
        else:
            indices = [int(i * (n - 1) / (n_per_band - 1)) for i in range(n_per_band)]

        sampled[band_key] = []
        for idx in indices:
            r = sorted_resps[idx]
            sampled[band_key].append({
                "persona_id": r["persona_id"],
                "pi": round(r["expected_rating"], 2),
                "text": r.get("free_text_response", "")[:300],
                "reasoning": (r.get("reasoning_response", "") or "")[:400],
            })

    return sampled


# ── Topic discovery (replaces hardcoded keyword groups) ────────────────

_FALLBACK_KEYWORD_GROUPS = {
    # Used ONLY when discover_topics fails or is skipped. Every entry is
    # category-agnostic — no apparel-specific terms like "fit" or "style" here.
    # If you're editing this list, you're probably fixing a bug, not tuning.
    "price/value": ["price", "cost", "expensive", "cheap", "afford", "value", "worth", "budget"],
    "quality": ["quality", "premium", "well-made", "cheap-feeling"],
    "brand/trust": ["brand", "trust", "reputation", "recommend", "review", "reviews"],
    "lifestyle_mismatch": ["don't need", "not for me", "rarely", "no occasion", "not in the market"],
    "convenience": ["shipping", "return", "delivery", "online", "easy", "convenient"],
    "comparison_shopping": ["compare", "alternative", "competitor", "similar", "instead"],
}


def _sample_for_topic_discovery(
    results: dict,
    n_per_concept_per_band: int = 3,
) -> list[dict]:
    """Stratified sample across concepts × sentiment bands for topic discovery.

    Small sample (3 × 5 bands × N concepts, cap ~50) keeps the discovery call
    cheap while covering the range of what respondents actually said.
    """
    sample = []
    for concept_id, concept_data in results["concepts"].items():
        concept_name = concept_data["concept"].get("name", concept_id)
        respondents = concept_data["respondents"]
        by_band = {}
        for r in respondents:
            band = _bucket(r["expected_rating"])
            by_band.setdefault(band, []).append(r)
        for band, rs in by_band.items():
            for r in rs[:n_per_concept_per_band]:
                text_parts = []
                if r.get("free_text_response"):
                    text_parts.append(r["free_text_response"][:300])
                if r.get("reasoning_response"):
                    text_parts.append(r["reasoning_response"][:400])
                if not text_parts:
                    continue
                sample.append({
                    "concept": concept_name,
                    "band": band,
                    "text": "\n".join(text_parts),
                })
    return sample[:60]  # hard cap on tokens


def discover_topics(
    results: dict,
    client,
    category: str | None = None,
) -> dict:
    """Ask gpt-4o-mini to identify emergent topic groups from actual responses.

    Returns {topic_name: [keyword1, keyword2, ...]} with keywords chosen to
    match what respondents said, not a category-general taxonomy. Categories
    like "fit/sizing" or "taste/flavor" only appear if respondents actually
    discussed those things.

    Falls back to a small category-agnostic set on any failure so downstream
    frequency counting still works.
    """
    sample = _sample_for_topic_discovery(results)
    if not sample:
        print("    ⚠ Topic discovery: no usable responses, using fallback groups")
        return _FALLBACK_KEYWORD_GROUPS

    sample_text = "\n\n---\n\n".join(
        f"[{s['concept']} | {s['band']}]\n{s['text']}" for s in sample
    )

    category_hint = (
        f"\nThe engagement category is: {category}. Use this only as light context — "
        "topic groups must still come from what respondents actually said, not a "
        "generic category taxonomy."
        if category else ""
    )

    system_prompt = (
        "You are a consumer research analyst identifying the topics that came up in "
        "a set of survey responses. Your job is to produce a topic taxonomy grounded "
        "in what respondents actually said — NOT a generic marketing taxonomy.\n\n"
        "Rules:\n"
        "- Return 5–8 topic groups.\n"
        "- Every topic must have appeared in AT LEAST 3 of the sampled responses. If "
        "you can't cite 3, don't include the topic.\n"
        "- Keyword lists should be words and short phrases respondents actually used "
        "or close synonyms — not aspirational marketing vocabulary.\n"
        "- Do NOT invent apparel terms (fit, sizing, style) for non-apparel products. "
        "Do NOT invent food/taste terms for non-ingestible products. Do NOT invent "
        "category-general topics that don't appear in this specific data.\n"
        "- Include at least 1 topic that acts as a barrier/objection (drives negative "
        "sentiment), if any appear in the data.\n\n"
        "Respond ONLY with valid JSON in this shape:\n"
        "{\n"
        '  "topics": [\n'
        '    {"name": "short-topic-label", "keywords": ["word1", "word2", ...]},\n'
        "    ...\n"
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"Sampled responses from a concept test (stratified across concepts and "
        f"sentiment bands):{category_hint}\n\n{sample_text}\n\n"
        "Return the JSON topic taxonomy now."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        topics = parsed.get("topics", [])
        groups = {t["name"]: [kw.lower() for kw in t["keywords"]] for t in topics if t.get("name") and t.get("keywords")}
        if not groups:
            print("    ⚠ Topic discovery returned no groups, using fallback")
            return _FALLBACK_KEYWORD_GROUPS
        print(f"    Discovered {len(groups)} topic groups: {', '.join(groups.keys())}")
        return groups
    except Exception as e:
        print(f"    ⚠ Topic discovery failed ({e}), using fallback")
        return _FALLBACK_KEYWORD_GROUPS


# ── Tie-group clustering ───────────────────────────────────────────────

def compute_tie_groups(
    concept_summaries: list[dict],
    threshold: float = 0.10,
) -> list[dict]:
    """Cluster concepts into tie groups where adjacent PI gaps ≤ threshold.

    Deterministic. Sort concepts by mean_pi descending; walk down the list; a
    new tie_group starts whenever the gap to the previous concept exceeds
    threshold. Returns the same dicts augmented with rank, tie_group, and
    delta_from_top.

    Why 0.10 as default: prior peptide-run inspection showed 4 concepts within
    0.05 PI of each other. 0.10 gives a small buffer without being so wide that
    real gaps get swallowed. Tune only after you have a real disagreement case.
    """
    sorted_concepts = sorted(concept_summaries, key=lambda c: -c["mean_pi"])
    if not sorted_concepts:
        return []

    top_pi = sorted_concepts[0]["mean_pi"]
    current_group = "A"
    prev_pi = top_pi
    ranked = []
    for i, c in enumerate(sorted_concepts):
        if i > 0 and (prev_pi - c["mean_pi"]) > threshold:
            current_group = chr(ord(current_group) + 1)
        ranked.append({
            **c,
            "rank": i + 1,
            "tie_group": current_group,
            "delta_from_top": round(top_pi - c["mean_pi"], 3),
        })
        prev_pi = c["mean_pi"]
    return ranked


# ── Prompt construction ────────────────────────────────────────────────

def _build_prompt(
    results: dict,
    persona_lookup: dict,
    keyword_groups: dict,
    ranking: list[dict],
) -> tuple[str, str]:
    """Build a single comparative prompt with all pre-computed data.

    keyword_groups: emergent topic taxonomy from discover_topics.
    ranking: pre-computed N-concept ranking with tie_group assignments.
    """
    tie_group_lookup = {r["concept_id"]: r["tie_group"] for r in ranking}
    rank_lookup = {r["concept_id"]: r["rank"] for r in ranking}
    delta_lookup = {r["concept_id"]: r["delta_from_top"] for r in ranking}

    concepts_data = []

    for concept_id, concept_data in results["concepts"].items():
        concept = concept_data["concept"]
        respondents = concept_data["respondents"]
        aggregate = concept_data["aggregate"]
        dist = aggregate.get("distribution", {})

        segment_metrics = compute_segment_metrics(respondents, persona_lookup)
        keyword_freq = compute_keyword_frequencies(respondents, keyword_groups)
        verbatims = _sample_verbatims(respondents, n_per_band=3)

        band_counts = Counter()
        for r in respondents:
            band_counts[_bucket(r["expected_rating"])] += 1

        top2 = float(dist.get("4", 0)) + float(dist.get("5", 0))
        bot2 = float(dist.get("1", 0)) + float(dist.get("2", 0))
        ratio = round(top2 / bot2, 1) if bot2 > 0 else 0

        concepts_data.append({
            "concept_id": concept_id,
            "name": concept.get("name", concept_id),
            "description": concept.get("description", ""),
            "n": aggregate.get("n_respondents", len(respondents)),
            "mean_pi": aggregate.get("mean_pi", 0),
            "std_pi": aggregate.get("std_pi", 0),
            "top2box": round(top2, 3),
            "bot2box": round(bot2, 3),
            "pos_neg_ratio": ratio,
            "band_counts": dict(band_counts),
            "segment_metrics": segment_metrics,
            "keyword_frequencies": keyword_freq,
            "verbatims": verbatims,
        })

    # Build concept sections
    concept_sections = []
    for cd in concepts_data:
        cid = cd['concept_id']
        rank_note = f"Rank {rank_lookup.get(cid, '?')} of {len(ranking)} · Tie group {tie_group_lookup.get(cid, '?')} · Δ from top: {delta_lookup.get(cid, 0):+.2f}"
        section = f"""
## Concept: {cd['name']}
{rank_note}
Description: {cd['description']}

### Aggregate Metrics (pre-computed, use these exact numbers):
- N = {cd['n']} respondents
- Mean PI: {cd['mean_pi']:.2f}, Std Dev: {cd['std_pi']:.2f}
- Top 2 Box: {cd['top2box']:.1%}, Bottom 2 Box: {cd['bot2box']:.1%}
- Pos:Neg ratio: {cd['pos_neg_ratio']}:1
- Band counts: {json.dumps(cd['band_counts'])}

### Topic Mention Frequencies (pre-computed):
"""
        for topic, freq in sorted(cd["keyword_frequencies"].items(), key=lambda x: -x[1]["pct"]):
            section += f"- {topic}: {freq['pct']}% ({freq['count']}/{cd['n']})\n"

        section += "\n### Segment-Level Mean PI (pre-computed):\n"
        for axis in ["income", "age_band", "shopping_mindset", "brand_adoption_style", "household_composition"]:
            if axis in cd["segment_metrics"]:
                section += f"\n{axis}:\n"
                for seg, data in sorted(cd["segment_metrics"][axis].items(), key=lambda x: -x[1]["mean_pi"]):
                    section += f"  {seg}: PI={data['mean_pi']:.2f} (n={data['n']})\n"

        section += "\n### Sampled Verbatims:\n"
        for band_key in ["strong", "leaning", "neutral", "soft_neg", "low"]:
            if band_key in cd["verbatims"]:
                section += f"\n{_bucket_label(band_key)}:\n"
                for v in cd["verbatims"][band_key]:
                    section += f"  [{v['persona_id']}, PI={v['pi']}]: {v['text']}\n"
                    if v["reasoning"]:
                        section += f"    WHY: {v['reasoning']}\n"

        concept_sections.append(section)

    all_concepts_text = "\n---\n".join(concept_sections)

    # Pre-computed N-concept ranking table with tie groups.
    # This is the AUTHORITATIVE ranking — SSR scoring already produced it. The
    # LLM's job is to EXPLAIN it, not reproduce it.
    ranking_header = (
        "\n## PRE-COMPUTED CONCEPT RANKING (authoritative — do not reorder):\n"
        "\nEach concept below has a `tie_group` letter. Concepts in the SAME tie_group\n"
        "are within panel noise of each other (adjacent mean-PI gap ≤ 0.10) — treat\n"
        "them as effectively tied. Concepts in DIFFERENT tie_groups are meaningfully\n"
        "separated.\n\n"
    )
    ranking_table = "| Rank | Tie Group | Concept | Mean PI | Δ from top | Top-2-Box | Pos:Neg |\n"
    ranking_table += "|------|-----------|---------|---------|------------|-----------|---------|\n"
    for r in ranking:
        ranking_table += (
            f"| {r['rank']} | {r['tie_group']} | {r['name']} | {r['mean_pi']:.2f} | "
            f"{r['delta_from_top']:+.2f} | {r['top2box']:.1%} | {r['pos_neg_ratio']}:1 |\n"
        )

    all_concepts_text = ranking_header + ranking_table + "\n---\n" + all_concepts_text

    system_prompt = """You are a senior consumer insights strategist analyzing synthetic panel data from an AI concept test.

CRITICAL RULES:
- All metrics are PRE-COMPUTED. Use the EXACT numbers provided. Do NOT invent statistics.
- The CONCEPT RANKING is pre-computed and authoritative — SSR scoring produced it. Your job is to EXPLAIN the ranking, not reorder it.
- Concepts sharing a `tie_group` are within panel noise. Do NOT invent narrative differentiation between concepts in the same tie_group — describe them as a group and note they are effectively tied. Reserve concept-vs-concept explanation for cases where tie_groups DIFFER.
- Every concept must appear in `concept_specific` (keyed by concept NAME). No concept may be skipped, including those in a tied group.
- Frame findings as HYPOTHESES TO TEST with real consumers, not proven facts.
- Recommendations must be SPECIFIC to this brand/product. No generic marketing advice.
- When citing verbatims, keep quotes under 25 words.
- Topic labels are supplied from what THIS engagement's respondents actually said. Do not import topics from other categories (e.g. no "fit/sizing" unless the topic list contains it).

Respond ONLY with valid JSON (no markdown, no backticks) matching this schema:

{
  "headline": "One sentence capturing the most actionable takeaway. If the top tie_group contains multiple concepts, do NOT anoint a single 'winner' — describe the pattern honestly.",

  "ranking_interpretation": {
    "meaningful_separations": "Which tie_group transitions in the ranking are real signal and what drives them. E.g. 'Group A (top 4) clearly separates from Group B (Vitauthority) — the ~0.25 PI gap is driven by X.'",
    "within_noise_notes": "Which concepts are effectively tied (same tie_group) and should NOT be individually differentiated in the narrative. E.g. 'Ranks 1-4 all sit in Group A, within 0.05 PI. Treat as tied.'",
    "top_pick": "The single top-ranked concept, ONLY if it is alone in its tie_group. If the top tie_group has multiple members, this field is null and you must instead describe the tied top group."
  },

  "segment_insights": [
    {
      "segment_axis": "e.g. 'income', 'brand_adoption_style', 'shopping_mindset'",
      "finding": "What the data shows — cite exact pre-computed PI values and deltas.",
      "implication": "What this means for targeting, messaging, or media strategy.",
      "evidence": "1-2 short verbatim quotes illustrating this."
    }
  ],

  "topic_analysis": [
    {
      "topic": "Topic name — MUST be one from the pre-computed keyword frequencies list.",
      "mention_rate": "Exact % from pre-computed data",
      "role": "driver | barrier | mixed",
      "detail": "How this topic functions across sentiment bands and concepts. Be specific about WHY it's a driver or barrier.",
      "concept_difference": "How it differs across concepts — but do NOT invent differences within a tie_group."
    }
  ],

  "recommended_actions": [
    {
      "action": "Specific recommendation for THIS brand.",
      "evidence": "Cite specific segments, numbers, and quotes.",
      "expected_impact": "Which metric this moves, for which segment.",
      "priority": "high | medium | low"
    }
  ],

  "concept_specific": {
    "CONCEPT_NAME": {
      "rank_context": "This concept's rank and tie_group, and one sentence on what that position means.",
      "purchase_drivers": [
        {
          "theme": "Short driver name",
          "detail": "1-2 sentence explanation grounded in response evidence.",
          "evidence": "A short verbatim quote illustrating this driver."
        }
      ],
      "pain_points": [
        {
          "theme": "Short barrier name",
          "detail": "1-2 sentence explanation of why this is a barrier, grounded in response evidence.",
          "evidence": "A short verbatim quote illustrating this pain point."
        }
      ],
      "best_audience": "Most receptive segment with PI data."
    }
  },

  "methodology_notes": [
    "2-3 honest caveats about this data. If the top tie_group is multi-member, one caveat MUST state that ranks within it are within panel noise."
  ]
}

segment_insights: 4-6 findings prioritized by actionability. Emphasize lifestyle/psychographic segments.
topic_analysis: 4-5 most important topics. At least 1-2 must be classified as "barrier". Every topic name MUST come from the pre-computed keyword frequency list — do not invent topics.
recommended_actions: 3-5 items tied to specific data.
concept_specific: one entry per concept using its CONCEPT NAME (not ID) as key. EVERY concept in the ranking must have an entry — none skipped. Include 3 purchase_drivers and 3 pain_points per concept, each with theme, detail, and evidence. Pain points should be actionable barriers, NOT restatements of aggregate metrics.
"""

    user_prompt = f"""Analyze this concept test and produce the comparative insights report.

{all_concepts_text}

Use ONLY the pre-computed numbers. Do not invent statistics."""

    return system_prompt, user_prompt


# ── Standout insights extraction ──────────────────────────────────────

def _build_standout_prompt(concept_name: str, respondents: list[dict], persona_lookup: dict) -> tuple[str, str]:
    """Build prompt to extract standout insights from reasoning responses."""

    # Collect all reasoning responses with persona context
    response_blocks = []
    for r in respondents:
        reasoning = r.get("reasoning_response", "")
        if not reasoning or len(reasoning.strip()) < 30:
            continue
        pid = r["persona_id"]
        p = persona_lookup.get(pid, {})
        pi = r.get("expected_rating", 0)
        band = _bucket(pi)

        demo = f"{p.get('age', '?')}yo {p.get('gender', '?')}, {p.get('region', '?')}, {p.get('income', '?')} income"
        lifestyle = p.get("lifestyle", {})
        if lifestyle:
            mindset = _shorten_lifestyle(lifestyle.get("shopping_mindset", ""))
            adoption = _shorten_lifestyle(lifestyle.get("brand_adoption_style", ""))
            if mindset:
                demo += f", {mindset}"
            if adoption:
                demo += f", {adoption}"

        response_blocks.append(
            f"[{pid} | PI={pi:.1f} ({band}) | {demo}]\n{reasoning[:500]}"
        )

    responses_text = "\n\n---\n\n".join(response_blocks)

    system_prompt = """You are a senior consumer insights analyst. Your job is to find the most SURPRISING, SPECIFIC, and ACTIONABLE insights buried in consumer responses.

You're looking for two types of standout insights:
1. **Specific suggestions** — concrete advice the consumer gives (e.g. "partner with influencers", "add a virtual try-on", "offer a subscription discount")
2. **Unique objections** — specific barriers that reveal something non-obvious about why consumers hesitate (e.g. "I'd never buy dress shirts online without trying them on first", "this feels like a brand my dad would wear")

DO NOT include:
- Generic positive/negative sentiment ("it looks nice", "not for me")
- Restatements of price being high or low
- Vague feedback without a concrete takeaway

For each insight, extract the KEY QUOTE (the most impactful 1-2 sentences, under 30 words) and explain WHY it matters to the brand.

Group insights by theme. Use specific, descriptive theme names (e.g. "Digital Try-On Opportunity", "Influencer Marketing Gap", "Generational Perception Risk") — NOT generic categories like "Marketing" or "Product".

Respond ONLY with valid JSON (no markdown, no backticks):

{
  "standout_insights": [
    {
      "theme": "Descriptive theme name",
      "type": "suggestion | objection",
      "quote": "The key 1-2 sentence excerpt (under 30 words)",
      "persona_context": "Brief persona description (age, mindset, sentiment band)",
      "persona_id": "resp_XXXX",
      "why_it_matters": "1 sentence on why the brand should pay attention to this.",
      "pi_score": 3.2
    }
  ]
}

Return as many insights as are genuinely interesting and actionable. Typical range: 5-15 per concept. Quality over quantity — skip anything generic."""

    user_prompt = f"""Extract standout insights from these {len(response_blocks)} consumer responses to the concept "{concept_name}":

{responses_text}"""

    return system_prompt, user_prompt


def extract_standout_insights(results: dict, personas: dict, client=None, api_key: str | None = None) -> dict:
    """
    Second LLM pass: extract standout insights from reasoning responses.
    Returns dict keyed by concept_id.
    """
    from openai import OpenAI

    if client is None:
        client = OpenAI(api_key=api_key) if api_key else OpenAI()

    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}
    all_standouts = {}

    for concept_id, concept_data in results["concepts"].items():
        concept_name = concept_data["concept"].get("name", concept_id)
        respondents = concept_data["respondents"]

        system_prompt, user_prompt = _build_standout_prompt(concept_name, respondents, persona_lookup)
        prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
        print(f"    Standout extraction for {concept_name}: ~{prompt_tokens:,} tokens")

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                cleaned = raw.strip().strip("`").lstrip("json\n")
                parsed = json.loads(cleaned)

            standouts = parsed.get("standout_insights", [])
            all_standouts[concept_id] = {
                "concept_name": concept_name,
                "insights": standouts,
                "n_extracted": len(standouts),
            }
            print(f"      → {len(standouts)} standout insights extracted")

        except Exception as e:
            print(f"      ⚠ Standout extraction failed for {concept_name}: {e}")
            all_standouts[concept_id] = {
                "concept_name": concept_name,
                "insights": [],
                "n_extracted": 0,
            }

    return all_standouts


# ── LLM call ───────────────────────────────────────────────────────────

TIE_GROUP_THRESHOLD = 0.10


def generate_insights(results: dict, personas: dict, api_key: str | None = None) -> dict:
    """Generate comparative insights.

    Flow:
      0. Pre-pass — discover per-engagement topic taxonomy from actual responses
         (replaces hardcoded apparel-flavored keyword groups).
      0. Pre-pass — compute N-concept ranking with deterministic tie groups
         (replaces the old 2-concept comparison that ignored concepts 3+).
      1. Comparative-insights LLM call with everything pre-computed.
      2. Standout-insights extraction.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}

    # Optional category context — helps discover_topics stay grounded but is
    # not required. Presence is checked in the checklist gate, not here.
    category = results.get("meta", {}).get("engagement", {}).get("category")
    if category:
        print(f"    Engagement category: {category}")

    # Pre-pass: discover topics grounded in what respondents actually said.
    print("  Discovering emergent topics from responses...")
    keyword_groups = discover_topics(results, client, category=category)

    # Pre-pass: deterministic N-concept ranking with tie groups.
    concept_summaries = []
    for concept_id, concept_data in results["concepts"].items():
        aggregate = concept_data["aggregate"]
        dist = aggregate.get("distribution", {})
        top2 = float(dist.get("4", 0)) + float(dist.get("5", 0))
        bot2 = float(dist.get("1", 0)) + float(dist.get("2", 0))
        concept_summaries.append({
            "concept_id": concept_id,
            "name": concept_data["concept"].get("name", concept_id),
            "mean_pi": aggregate.get("mean_pi", 0),
            "std_pi": aggregate.get("std_pi", 0),
            "top2box": round(top2, 3),
            "bot2box": round(bot2, 3),
            "pos_neg_ratio": round(top2 / bot2, 1) if bot2 > 0 else 0,
        })
    ranking = compute_tie_groups(concept_summaries, threshold=TIE_GROUP_THRESHOLD)
    tie_group_letters = sorted({r["tie_group"] for r in ranking})
    print(f"    Ranking: {len(ranking)} concepts, {len(tie_group_letters)} tie group(s) "
          f"({', '.join(tie_group_letters)}) at threshold {TIE_GROUP_THRESHOLD} PI")

    # Pass 1: Comparative insights
    system_prompt, user_prompt = _build_prompt(results, persona_lookup, keyword_groups, ranking)
    prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
    print(f"    Prompt size: ~{prompt_tokens:,} tokens")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        insights = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip().strip("`").lstrip("json\n")
        insights = json.loads(cleaned)

    # Inject the authoritative ranking into the output. Not LLM-generated —
    # deterministic from SSR scoring. Downstream consumers (Streamlit explorer,
    # deliverables) should read this, not any ranking-shaped inference from
    # the narrative.
    insights["concept_ranking"] = ranking

    # Pass 2: Standout insights extraction
    print("  Extracting standout insights...")
    try:
        insights["standout_insights"] = extract_standout_insights(
            results, personas, client=client, api_key=api_key
        )
    except Exception as e:
        print(f"    ⚠ Standout extraction failed: {e}")
        insights["standout_insights"] = {}

    # Attach pre-computed segment data for the Streamlit tab.
    insights["_precomputed"] = {}
    for concept_id, concept_data in results["concepts"].items():
        respondents = concept_data["respondents"]
        insights["_precomputed"][concept_id] = {
            "segment_metrics": compute_segment_metrics(respondents, persona_lookup),
            "keyword_frequencies": compute_keyword_frequencies(respondents, keyword_groups),
        }

    insights["_meta"] = {
        "model": "gpt-4o-mini",
        "n_concepts": len(results["concepts"]),
        "concept_ids": list(results["concepts"].keys()),
        "prompt_tokens_approx": prompt_tokens,
        "category": category,
        "topic_groups": list(keyword_groups.keys()),
        "tie_group_threshold": TIE_GROUP_THRESHOLD,
    }

    return insights


def generate_and_save(
    results_path: str | Path,
    personas_path: str | Path | None = None,
    output_path: str | Path | None = None,
    api_key: str | None = None,
) -> dict:
    results_path = Path(results_path)
    if personas_path is None:
        personas_path = results_path.parent / "personas.json"
    if output_path is None:
        output_path = results_path.parent / "insights.json"

    with open(results_path) as f:
        results = json.load(f)
    with open(Path(personas_path)) as f:
        personas = json.load(f)

    print("Generating insights...")
    insights = generate_insights(results, personas, api_key=api_key)

    with open(Path(output_path), "w") as f:
        json.dump(insights, f, indent=2)
    print(f"  Saved: {output_path}")
    return insights


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate insights from SSR results")
    parser.add_argument("results_path", help="Path to results.json")
    parser.add_argument("--personas", help="Path to personas.json (default: same dir)")
    parser.add_argument("--output", "-o", help="Output path (default: insights.json in same dir)")
    args = parser.parse_args()
    generate_and_save(args.results_path, args.personas, args.output)