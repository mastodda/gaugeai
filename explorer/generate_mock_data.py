"""
generate_mock_data.py — Create realistic mock pipeline output for explorer development.

Generates results.json and personas.json that match the exact format
produced by pipeline.py, using plausible free-text responses and
SSR-like PMF distributions.

Usage:
    python generate_mock_data.py [--output-dir mock_data] [--panel-size 100]
"""

import json
import random
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Response templates — varied by sentiment band
# ---------------------------------------------------------------------------

POSITIVE_RESPONSES = [
    "I'd definitely pick this up next time I'm at the store. Seems like exactly what I've been looking for.",
    "This sounds great, I'd probably buy it. The price point is reasonable for what you get.",
    "Yeah, I'd try this for sure. I like that it's straightforward and not trying to be something it's not.",
    "I think I'd buy this. It fits what I'm looking for and the value seems solid.",
    "This is appealing to me. I'd likely grab one to try it out.",
    "I can see myself buying this regularly. It checks a lot of boxes for me.",
    "Honestly, this sounds like something I'd enjoy. I'd be willing to spend money on it.",
    "I'm pretty interested in this. Would definitely consider purchasing it.",
]

NEUTRAL_RESPONSES = [
    "It's okay, I guess. I might try it if I saw it on sale but I wouldn't go out of my way.",
    "I'm not sure. It's fine but nothing about it really stands out to me.",
    "Maybe. I'd have to see it in person first. The concept is decent but not compelling.",
    "I could take it or leave it. It doesn't really solve a problem I have.",
    "It's alright. Not something I'd seek out but I wouldn't turn it down either.",
    "Hmm, I'm on the fence. There are similar things I already buy that work fine.",
    "I don't have strong feelings either way. It seems adequate but not exciting.",
    "It's not bad, but I'm not sure it's worth switching from what I currently use.",
]

NEGATIVE_RESPONSES = [
    "Not for me. I don't really see the point when there are cheaper options.",
    "I wouldn't buy this. It doesn't appeal to me at all.",
    "No thanks. This isn't something I need or want in my life.",
    "I'd pass on this. The price seems too high for what it is.",
    "This doesn't interest me. I don't think it fits my lifestyle.",
    "I can't see myself buying this. It feels unnecessary.",
]


def _generate_pmf(sentiment: str, rng: random.Random) -> dict[str, float]:
    """Generate a plausible PMF based on sentiment band."""
    if sentiment == "positive":
        # Weight toward 4-5
        raw = {
            "1": rng.uniform(0.01, 0.05),
            "2": rng.uniform(0.03, 0.10),
            "3": rng.uniform(0.10, 0.25),
            "4": rng.uniform(0.25, 0.45),
            "5": rng.uniform(0.15, 0.40),
        }
    elif sentiment == "neutral":
        # Weight toward 3, spread to 2 and 4
        raw = {
            "1": rng.uniform(0.03, 0.12),
            "2": rng.uniform(0.12, 0.28),
            "3": rng.uniform(0.25, 0.40),
            "4": rng.uniform(0.12, 0.28),
            "5": rng.uniform(0.03, 0.12),
        }
    else:
        # Weight toward 1-2
        raw = {
            "1": rng.uniform(0.15, 0.40),
            "2": rng.uniform(0.25, 0.40),
            "3": rng.uniform(0.10, 0.25),
            "4": rng.uniform(0.03, 0.10),
            "5": rng.uniform(0.01, 0.05),
        }

    total = sum(raw.values())
    return {k: round(v / total, 6) for k, v in raw.items()}


def _pmf_expected(pmf: dict[str, float]) -> float:
    return round(sum(int(k) * v for k, v in pmf.items()), 4)


def _pmf_mode(pmf: dict[str, float]) -> int:
    return int(max(pmf, key=pmf.get))


def _generate_per_set_data(pmf: dict[str, float], rng: random.Random) -> tuple[dict, dict]:
    """Generate plausible per-set similarities and PMFs from an averaged PMF."""
    set_names = [
        "direct_likelihood", "purchase_decision", "interest_consideration",
        "spending_money", "try_give_it_a_go", "personal_fit_need",
    ]
    per_set_sims = {}
    per_set_pmfs = {}

    for name in set_names:
        # Similarities: high base (0.95+) with small spread
        base_sim = rng.uniform(0.955, 0.975)
        sims = {}
        set_pmf = {}
        for rating_str, prob in pmf.items():
            noise = rng.uniform(-0.015, 0.015)
            sims[rating_str] = round(base_sim + prob * 0.03 + noise, 6)
            set_pmf[rating_str] = round(prob + rng.uniform(-0.05, 0.05), 6)

        # Re-normalize set PMF
        total = sum(max(0, v) for v in set_pmf.values())
        set_pmf = {k: round(max(0, v) / total, 6) for k, v in set_pmf.items()}

        per_set_sims[name] = sims
        per_set_pmfs[name] = set_pmf

    return per_set_sims, per_set_pmfs


def generate_personas(panel_size: int, seed: int) -> list[dict]:
    """Generate a panel of personas matching persona_to_dict output."""
    rng = random.Random(seed)

    genders = ["woman", "man"]
    gender_weights = [0.52, 0.48]
    regions = ["Midwest", "Northeast", "South", "West"]
    region_weights = [0.21, 0.17, 0.38, 0.24]
    incomes = ["low", "moderate", "upper-moderate", "high"]
    income_weights = [0.25, 0.40, 0.25, 0.10]

    personas = []
    for i in range(panel_size):
        gender = rng.choices(genders, weights=gender_weights, k=1)[0]
        region = rng.choices(regions, weights=region_weights, k=1)[0]
        income = rng.choices(incomes, weights=income_weights, k=1)[0]
        age = rng.randint(21, 65)

        personas.append({
            "persona_id": f"resp_{i:04d}",
            "age": age,
            "gender": gender,
            "region": region,
            "income": income,
            "ethnicity": None,
            "system_prompt": (
                f"You are a {age}-year-old {gender} living in the {region} "
                f"with a {income} household income. Reply briefly to any "
                f"questions posed to you."
            ),
        })

    return personas


POSITIVE_REASONING = [
    "The price point is what gets me — it's competitive with what's already on my shelf. Plus I like that it's natural ingredients, no artificial stuff. If the carbonation is right, this would replace my current brand easily.",
    "I'm drawn to the simplicity of the concept. Zero calories, zero sweeteners, real citrus. That's a rare combination. The 8-pack format works for my household too. Only thing that would make me hesitate is if the flavor was too subtle.",
    "I appreciate that they're not trying to do too much with this product. Clean ingredients, straightforward positioning. The slim can format is a nice touch for portability. I'd want to try one before committing to a full pack though.",
    "What specifically appeals to me is the natural citrus oils angle. Most sparkling waters I've tried use 'natural flavors' which is so vague. This feels more transparent. Price is reasonable. I'd be a repeat buyer if the taste delivers.",
]

NEUTRAL_REASONING = [
    "I don't have strong feelings either way. The product is fine but the sparkling water market is so crowded right now. I'd need to see it in-store and probably try a sample. Nothing about the concept is bad, just nothing jumps out as special.",
    "The concept is decent but I'm already happy with what I buy. I'd need a reason to switch — maybe if it was on sale or a friend recommended it. The price is fine but not compelling enough to change my routine.",
    "I'm not sure what the unique selling point is here. Citrus sparkling water exists from multiple brands. The packaging sounds nice but I buy based on taste, and I can't judge that from a description.",
]

NEGATIVE_REASONING = [
    "The price is the main barrier for me. I can get store-brand sparkling water for much less. The 'premium' positioning doesn't resonate — it's water with bubbles and some citrus. Not worth the markup.",
    "I just don't drink sparkling water. The carbonation bothers my stomach. No matter how good the flavor or how reasonable the price, this product category isn't for me. Nothing they could change would make me buy it.",
    "I'm skeptical of the natural citrus oils claim. In my experience, these products barely taste like anything. I'd rather just squeeze a real lemon into regular water. Also $6.99 for 8 cans feels steep.",
]


def _generate_reasoning(sentiment: str, rng: random.Random) -> str:
    """Pick a mock reasoning response based on sentiment."""
    if sentiment == "positive":
        return rng.choice(POSITIVE_REASONING)
    elif sentiment == "neutral":
        return rng.choice(NEUTRAL_REASONING)
    else:
        return rng.choice(NEGATIVE_REASONING)


def generate_concept_results(
    concept: dict,
    personas: list[dict],
    sentiment_bias: float,  # 0.0 = negative skew, 1.0 = positive skew
    seed: int,
) -> dict:
    """Generate results for one concept across the full panel."""
    rng = random.Random(seed)

    respondents = []
    for persona in personas:
        # Determine sentiment — bias by concept, with demographic influence
        p = sentiment_bias

        # Income effect: higher income slightly more positive
        income_boost = {"low": -0.05, "moderate": 0.0, "upper-moderate": 0.05, "high": 0.08}
        p += income_boost.get(persona.get("income", ""), 0)

        # Age effect: slight variation
        if persona["age"] < 30:
            p += 0.03
        elif persona["age"] > 55:
            p -= 0.03

        roll = rng.random()
        if roll < p * 0.55:
            sentiment = "positive"
            response = rng.choice(POSITIVE_RESPONSES)
        elif roll < p * 0.55 + (1 - p) * 0.4:
            sentiment = "neutral"
            response = rng.choice(NEUTRAL_RESPONSES)
        else:
            sentiment = "negative"
            response = rng.choice(NEGATIVE_RESPONSES)

        pmf = _generate_pmf(sentiment, rng)
        per_set_sims, per_set_pmfs = _generate_per_set_data(pmf, rng)

        # Generate mock reasoning response
        reasoning = _generate_reasoning(sentiment, rng)

        respondents.append({
            "persona_id": persona["persona_id"],
            "free_text_response": response,
            "reasoning_response": reasoning,
            "per_set_similarities": per_set_sims,
            "per_set_pmfs": per_set_pmfs,
            "averaged_pmf": pmf,
            "expected_rating": _pmf_expected(pmf),
            "mode_rating": _pmf_mode(pmf),
        })

    # Aggregate
    avg_dist = {}
    for r in ["1", "2", "3", "4", "5"]:
        avg_dist[r] = round(
            sum(resp["averaged_pmf"][r] for resp in respondents) / len(respondents), 4
        )

    ratings = [r["expected_rating"] for r in respondents]
    mean_pi = round(sum(ratings) / len(ratings), 4)
    std_pi = round((sum((x - mean_pi) ** 2 for x in ratings) / len(ratings)) ** 0.5, 4)

    ages = [p["age"] for p in personas]
    gender_counts = {}
    region_counts = {}
    income_counts = {}
    for p in personas:
        gender_counts[p["gender"]] = gender_counts.get(p["gender"], 0) + 1
        region_counts[p["region"]] = region_counts.get(p["region"], 0) + 1
        if p.get("income"):
            income_counts[p["income"]] = income_counts.get(p["income"], 0) + 1

    return {
        "concept": concept,
        "panel_summary": {
            "panel_size": len(personas),
            "age_min": min(ages),
            "age_max": max(ages),
            "age_mean": round(sum(ages) / len(ages), 1),
            "gender": gender_counts,
            "region": region_counts,
            "income": income_counts if income_counts else None,
        },
        "respondents": respondents,
        "aggregate": {
            "distribution": avg_dist,
            "mean_pi": mean_pi,
            "std_pi": std_pi,
            "n_respondents": len(respondents),
        },
    }


def generate_mock_data(output_dir: str = "mock_data", panel_size: int = 100, seed: int = 42):
    """Generate complete mock results.json and personas.json."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    concepts = [
        {
            "concept_id": "concept_a",
            "name": "CitrusBurst Sparkling Water",
            "description": (
                "CitrusBurst is a premium sparkling water infused with natural "
                "citrus oils. Zero calories, zero sweeteners — just crisp bubbles "
                "with a bright lemon-lime finish. Available in sleek 12oz slim cans, "
                "sold in 8-packs for $6.99."
            ),
            "image_path": None,
        },
        {
            "concept_id": "concept_b",
            "name": "CitrusBurst Sparkling Water — Vitamin Boost",
            "description": (
                "CitrusBurst Vitamin Boost is a premium sparkling water with natural "
                "citrus flavor plus added B-vitamins and electrolytes. Zero calories, "
                "zero sweeteners, with functional hydration benefits. Available in "
                "sleek 12oz slim cans, sold in 8-packs for $8.49."
            ),
            "image_path": None,
        },
    ]

    personas = generate_personas(panel_size, seed)

    # Concept A: moderately positive (0.55 bias)
    # Concept B: slightly less positive (0.45 bias) — higher price, niche appeal
    all_concept_results = {}
    for concept, bias, cseed in [
        (concepts[0], 0.55, seed + 1),
        (concepts[1], 0.45, seed + 2),
    ]:
        all_concept_results[concept["concept_id"]] = generate_concept_results(
            concept, personas, bias, cseed
        )

    results = {
        "meta": {
            "engagement": {
                "engagement": "Example: Sparkling Water Concept Test",
                "client": "ACME Beverages",
                "date": "2026-02-15",
                "analyst": "",
                "notes": "MVP test engagement. Two flavor concepts.",
            },
            "pipeline_config": {
                "llm_provider": "openai",
                "llm_model": "gpt-4o",
                "llm_temperature": 0.5,
                "embedding_model": "text-embedding-3-small",
                "ssr_epsilon": 0.0,
                "ssr_temperature": 1.0,
                "samples_per_persona": 2,
                "seed": seed,
                "reference_sets": [
                    "direct_likelihood", "purchase_decision",
                    "interest_consideration", "spending_money",
                    "try_give_it_a_go", "personal_fit_need",
                ],
            },
            "timestamp": datetime.now().isoformat(),
        },
        "concepts": all_concept_results,
    }

    personas_output = {
        "panel_summary": all_concept_results[concepts[0]["concept_id"]]["panel_summary"],
        "personas": personas,
    }

    results_path = out / "results.json"
    personas_path = out / "personas.json"

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    with open(personas_path, "w") as f:
        json.dump(personas_output, f, indent=2)

    print(f"Generated {panel_size} personas × {len(concepts)} concepts")
    print(f"  {results_path}")
    print(f"  {personas_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock SSR pipeline output")
    parser.add_argument("--output-dir", default="mock_data")
    parser.add_argument("--panel-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate_mock_data(args.output_dir, args.panel_size, args.seed)