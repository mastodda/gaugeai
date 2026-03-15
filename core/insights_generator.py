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
load_dotenv()


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


def compute_keyword_frequencies(respondents: list[dict]) -> dict:
    """Count mentions of product-relevant terms across all responses."""
    keyword_groups = {
        "price/value": ["price", "cost", "expensive", "cheap", "afford", "value", "deal", "discount", "save", "saving", "savings", "budget", "money", "worth"],
        "quality": ["quality", "premium", "craftsmanship", "durability", "durable", "well-made", "fabric", "material", "construction"],
        "fit/sizing": ["fit", "sizing", "size", "loose", "tight", "slim", "tailored", "measurement"],
        "brand/trust": ["brand", "trust", "reputation", "recommend", "review", "reviews", "testimonial", "known"],
        "lifestyle_mismatch": ["don't need", "don't wear", "casual", "remote", "work from home", "rarely", "no occasion", "not in the market"],
        "style/aesthetics": ["style", "stylish", "fashion", "look", "appearance", "classic", "modern", "elegant", "timeless"],
        "convenience": ["shipping", "return", "delivery", "online", "hassle", "easy", "convenient"],
        "comparison_shopping": ["compare", "alternative", "competitor", "similar", "other brand", "instead"],
    }

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


# ── Prompt construction ────────────────────────────────────────────────

def _build_prompt(results: dict, persona_lookup: dict) -> tuple[str, str]:
    """Build a single comparative prompt with all pre-computed data."""
    concepts_data = []

    for concept_id, concept_data in results["concepts"].items():
        concept = concept_data["concept"]
        respondents = concept_data["respondents"]
        aggregate = concept_data["aggregate"]
        dist = aggregate.get("distribution", {})

        segment_metrics = compute_segment_metrics(respondents, persona_lookup)
        keyword_freq = compute_keyword_frequencies(respondents)
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
        section = f"""
## Concept: {cd['name']}
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

    # Cross-concept comparison table
    if len(concepts_data) >= 2:
        comp = "\n## PRE-COMPUTED CROSS-CONCEPT COMPARISON:\n"
        a, b = concepts_data[0], concepts_data[1]
        comp += f"\n{a['name']} vs {b['name']}:\n"
        comp += f"  Mean PI: {a['mean_pi']:.2f} vs {b['mean_pi']:.2f} (delta: {a['mean_pi'] - b['mean_pi']:+.2f})\n"
        comp += f"  Top 2 Box: {a['top2box']:.1%} vs {b['top2box']:.1%}\n"
        comp += f"  Pos:Neg: {a['pos_neg_ratio']}:1 vs {b['pos_neg_ratio']}:1\n"

        comp += "\nSegment-level comparison (same personas, both concepts):\n"
        for axis in ["income", "shopping_mindset", "brand_adoption_style"]:
            if axis in a["segment_metrics"] and axis in b["segment_metrics"]:
                comp += f"\n{axis}:\n"
                all_segs = set(a["segment_metrics"][axis].keys()) | set(b["segment_metrics"][axis].keys())
                for seg in sorted(all_segs):
                    a_pi = a["segment_metrics"].get(axis, {}).get(seg, {}).get("mean_pi", 0)
                    b_pi = b["segment_metrics"].get(axis, {}).get(seg, {}).get("mean_pi", 0)
                    delta = a_pi - b_pi
                    comp += f"  {seg}: {a_pi:.2f} vs {b_pi:.2f} (delta: {delta:+.2f})\n"

        all_concepts_text = comp + "\n---\n" + all_concepts_text

    system_prompt = """You are a senior consumer insights strategist analyzing synthetic panel data from an AI concept test.

CRITICAL RULES:
- All metrics are PRE-COMPUTED. Use the EXACT numbers provided. Do NOT invent statistics.
- Focus on COMPARATIVE insights. Which concept wins, for whom, and why?
- Emphasize SEGMENT-SPECIFIC findings. Surface which persona types respond differently.
- Frame as HYPOTHESES TO TEST with real consumers, not proven facts.
- Recommendations must be SPECIFIC to this brand/product. No generic marketing advice.
- When citing verbatims, keep quotes under 25 words.

Respond ONLY with valid JSON (no markdown, no backticks) matching this schema:

{
  "headline": "One sentence: which concept wins and the single most actionable takeaway.",

  "concept_comparison": {
    "winner": "concept_id",
    "winner_name": "name",
    "margin": "How meaningful is the gap — use the pre-computed delta.",
    "key_differentiator": "The specific reason one outperforms, grounded in response evidence."
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
      "topic": "Topic name from keyword frequencies",
      "mention_rate": "Exact % from pre-computed data",
      "role": "driver | barrier | mixed",
      "detail": "How this topic functions across sentiment bands and concepts. Be specific about WHY it's a driver or barrier.",
      "concept_difference": "How it differs between concepts."
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
      "purchase_drivers": [
        {
          "theme": "Short driver name (e.g. 'Significant Discount')",
          "detail": "1-2 sentence explanation grounded in response evidence.",
          "evidence": "A short verbatim quote illustrating this driver."
        }
      ],
      "pain_points": [
        {
          "theme": "Short barrier name (e.g. 'Fit Uncertainty')",
          "detail": "1-2 sentence explanation of why this is a barrier, grounded in response evidence.",
          "evidence": "A short verbatim quote illustrating this pain point."
        }
      ],
      "best_audience": "Most receptive segment with PI data."
    }
  },

  "methodology_notes": [
    "2-3 honest caveats about this data."
  ]
}

segment_insights: 4-6 findings prioritized by actionability. Emphasize lifestyle/psychographic segments.
topic_analysis: 4-5 most important topics. At least 1-2 must be classified as "barrier" — identify topics that drive NEGATIVE sentiment.
recommended_actions: 3-5 items tied to specific data.
concept_specific: one entry per concept using its CONCEPT NAME (not ID) as key. Include 3 purchase_drivers and 3 pain_points per concept, each with theme, detail, and evidence. Pain points should be actionable barriers (e.g. fit uncertainty, lifestyle mismatch, brand unfamiliarity) — NOT restatements of aggregate metrics.
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

def generate_insights(results: dict, personas: dict, api_key: str | None = None) -> dict:
    """Generate comparative insights. One LLM call with pre-computed data, plus standout extraction."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}

    # Pass 1: Comparative insights
    system_prompt, user_prompt = _build_prompt(results, persona_lookup)
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

    # Pass 2: Standout insights extraction
    print("  Extracting standout insights...")
    try:
        insights["standout_insights"] = extract_standout_insights(
            results, personas, client=client, api_key=api_key
        )
    except Exception as e:
        print(f"    ⚠ Standout extraction failed: {e}")
        insights["standout_insights"] = {}

    # Attach pre-computed segment data for the Streamlit tab
    insights["_precomputed"] = {}
    for concept_id, concept_data in results["concepts"].items():
        respondents = concept_data["respondents"]
        insights["_precomputed"][concept_id] = {
            "segment_metrics": compute_segment_metrics(respondents, persona_lookup),
            "keyword_frequencies": compute_keyword_frequencies(respondents),
        }

    insights["_meta"] = {
        "model": "gpt-4o-mini",
        "n_concepts": len(results["concepts"]),
        "concept_ids": list(results["concepts"].keys()),
        "prompt_tokens_approx": prompt_tokens,
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