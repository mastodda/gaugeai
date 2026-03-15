"""
test_integration.py — End-to-end integration test with mock API clients.

Validates the complete pipeline flow without any real API calls:
  1. Load engagement config
  2. Generate personas
  3. Mock LLM produces plausible free-text responses
  4. Mock embedder returns vectors that place responses correctly
  5. SSR scoring produces valid pmfs
  6. Aggregation and output are well-formed

This is your "everything works together" test.
"""

import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.ssr_scoring import (
    ReferenceSet,
    score_respondent,
    result_to_dict,
    aggregate_survey_distribution,
    survey_mean_pi,
    survey_std_pi,
    average_pmfs,
    pmf_expected_value,
    pmf_mode,
    SSRResult,
)
from core.persona_generator import (
    generate_panel,
    load_demographic_spec,
    panel_summary,
    persona_to_dict,
)


# ---------------------------------------------------------------------------
# Mock components
# ---------------------------------------------------------------------------

class MockEmbedder:
    """
    Fake embedder that maps text to vectors based on sentiment keywords.
    Positive words push the vector toward the "likely" direction,
    negative words push toward "unlikely".
    """

    def __init__(self, dim=128, seed=42):
        self.dim = dim
        self.rng = np.random.default_rng(seed)
        # Base direction (shared by all embeddings — simulates semantic clustering)
        self.base = self.rng.normal(0, 1, dim)
        self.base /= np.linalg.norm(self.base)
        # Sentiment axis
        self.sentiment = self.rng.normal(0, 1, dim)
        self.sentiment -= np.dot(self.sentiment, self.base) * self.base
        self.sentiment /= np.linalg.norm(self.sentiment)

    def embed(self, text: str) -> np.ndarray:
        """Map text to a vector. Sentiment keywords shift along the axis."""
        # Simple keyword-based sentiment scoring
        positive = ["likely", "buy", "purchase", "interested", "definitely",
                     "love", "great", "excited", "try", "happily", "confident",
                     "exactly", "work well", "worth"]
        negative = ["unlikely", "wouldn't", "not interested", "pass", "don't",
                     "wouldn't bother", "doesn't fit", "not sure", "skeptical",
                     "expensive", "doubt"]
        neutral = ["might", "maybe", "not sure", "on the fence", "consider"]

        text_lower = text.lower()
        score = 0.0
        for w in positive:
            if w in text_lower:
                score += 0.05
        for w in negative:
            if w in text_lower:
                score -= 0.05
        for w in neutral:
            if w in text_lower:
                score += 0.0  # no shift

        # Add small noise for uniqueness
        noise = self.rng.normal(0, 0.005, self.dim)
        vec = self.base + score * self.sentiment + noise
        return vec / np.linalg.norm(vec)


# Canned free-text responses for different sentiment levels
MOCK_RESPONSES = {
    "positive": [
        "I'd definitely buy this. The concept sounds great and the price is reasonable for what you get.",
        "This looks really appealing. I'm always looking for products like this and would likely purchase it.",
        "I'm excited about this product. It fits exactly what I need and I'd happily pay for it.",
    ],
    "moderate": [
        "I'm somewhat interested. If it works well and isn't too expensive, I might give it a try.",
        "This could be useful, but I'd want to know more before committing. Maybe I'd consider it.",
        "It's an interesting concept. I'd probably try it if I saw it in stores, but I'm not rushing out to buy it.",
    ],
    "negative": [
        "I don't think I'd purchase this. It doesn't really fit what I'm looking for.",
        "I'd probably pass on this. I'm skeptical about the claims and the price seems too high.",
        "This isn't something I would buy. I don't see the value compared to what I already use.",
    ],
}


def mock_elicit(persona_age: int) -> str:
    """
    Simulate LLM response based on age — younger and older slightly less positive,
    middle-aged more positive (mimicking the paper's concave age pattern).
    """
    import random
    rng = random.Random(persona_age)

    if 35 <= persona_age <= 55:
        pool = MOCK_RESPONSES["positive"] + MOCK_RESPONSES["moderate"]
        weights = [0.3, 0.3, 0.3, 0.1, 0.1, 0.1]  # favor positive
    elif persona_age < 25 or persona_age > 65:
        pool = MOCK_RESPONSES["negative"] + MOCK_RESPONSES["moderate"]
        weights = [0.25, 0.25, 0.25, 0.15, 0.15, 0.15]
    else:
        pool = MOCK_RESPONSES["moderate"] + MOCK_RESPONSES["positive"][:1]
        weights = [0.3, 0.3, 0.3, 0.1]

    # Normalize weights to pool length
    weights = weights[:len(pool)]
    return rng.choices(pool, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------

def run_integration_test():
    print("=" * 60)
    print("INTEGRATION TEST — Full pipeline with mock clients")
    print("=" * 60 + "\n")

    # --- Step 1: Load config ---
    print("[1/6] Loading engagement config...")
    engagement_path = Path("config/example_engagement.json")
    with open(engagement_path) as f:
        engagement = json.load(f)
    concepts = engagement["concepts"]
    print(f"  Loaded {len(concepts)} concepts")
    print(f"  Question: {engagement['survey_question']['text']}")

    # --- Step 2: Generate personas ---
    print("\n[2/6] Generating personas...")
    spec = load_demographic_spec(engagement_path)
    # Use smaller panel for test speed
    spec.panel_size = 30
    personas = generate_panel(
        spec=spec,
        prompt_template_path=Path("config/prompt_templates.json"),
        seed=42,
    )
    summary = panel_summary(personas)
    print(f"  Generated {len(personas)} personas")
    print(f"  Age: {summary['age_min']}-{summary['age_max']} (mean {summary['age_mean']})")
    assert len(personas) == 30

    # --- Step 3: Build mock reference sets ---
    print("\n[3/6] Building reference sets with mock embeddings...")
    embedder = MockEmbedder(dim=128)

    with open("config/reference_sets.json") as f:
        ref_config = json.load(f)

    reference_sets = []
    for set_name, set_data in ref_config["sets"].items():
        anchors = {int(k): v for k, v in set_data["anchors"].items()}
        embeddings = {r: embedder.embed(text) for r, text in anchors.items()}
        reference_sets.append(ReferenceSet(
            name=set_name,
            framing=set_data["framing"],
            anchors=anchors,
            embeddings=embeddings,
        ))
    print(f"  {len(reference_sets)} sets embedded")

    # Verify anchor embeddings have correct ordering
    for rs in reference_sets[:1]:
        sims = {}
        very_positive = embedder.embed("I would definitely buy this product, it's exactly what I want.")
        for r, emb in rs.embeddings.items():
            dot = np.dot(very_positive, emb) / (np.linalg.norm(very_positive) * np.linalg.norm(emb))
            sims[r] = dot
        print(f"  Anchor similarities to positive text: {', '.join(f'{r}:{s:.4f}' for r, s in sims.items())}")
        assert sims[5] > sims[1], "Positive text should be more similar to anchor 5 than anchor 1"
    print(f"  Anchor ordering validated ✓")

    # --- Step 4: Elicit and score ---
    print("\n[4/6] Running mock elicitation + scoring for each concept...")

    all_concept_results = {}

    for concept in concepts:
        concept_id = concept["concept_id"]
        print(f"\n  --- {concept.get('name', concept_id)} ---")

        concept_results = []
        samples_per_persona = 2

        for persona in personas:
            sample_pmfs = []
            for s in range(samples_per_persona):
                # Mock elicitation
                response_text = mock_elicit(persona.age)
                response_emb = embedder.embed(response_text)

                result = score_respondent(
                    persona_id=f"{persona.persona_id}_s{s}",
                    free_text_response=response_text,
                    response_embedding=response_emb,
                    reference_sets=reference_sets,
                    epsilon=0.0,
                    temperature=1.0,
                )
                sample_pmfs.append(result)

            # Average samples
            if len(sample_pmfs) == 1:
                concept_results.append(sample_pmfs[0])
            else:
                avg_pmf = average_pmfs([r.averaged_pmf for r in sample_pmfs])
                merged = SSRResult(
                    persona_id=persona.persona_id,
                    free_text_response=" | ".join(r.free_text_response for r in sample_pmfs),
                    per_set_similarities=sample_pmfs[0].per_set_similarities,
                    per_set_pmfs=sample_pmfs[0].per_set_pmfs,
                    averaged_pmf=avg_pmf,
                    expected_rating=pmf_expected_value(avg_pmf),
                    mode_rating=pmf_mode(avg_pmf),
                )
                concept_results.append(merged)

        # Aggregate
        dist = aggregate_survey_distribution(concept_results)
        mean_pi = survey_mean_pi(concept_results)
        std_pi = survey_std_pi(concept_results)

        print(f"    Respondents: {len(concept_results)}")
        print(f"    Mean PI: {mean_pi:.2f} (std: {std_pi:.2f})")
        print(f"    Distribution: " + "  ".join(
            f"{r}:{dist[r]:.0%}" for r in range(1, 6)
        ))

        # Validation
        assert len(concept_results) == 30, f"Expected 30, got {len(concept_results)}"
        assert 1.0 <= mean_pi <= 5.0, f"Mean PI {mean_pi} out of range"
        assert abs(sum(dist.values()) - 1.0) < 1e-6, "Distribution doesn't sum to 1"

        all_concept_results[concept_id] = {
            "results": concept_results,
            "distribution": dist,
            "mean_pi": mean_pi,
            "std_pi": std_pi,
        }

    # --- Step 5: Validate output structure ---
    print("\n\n[5/6] Validating output structure...")

    output = {
        "meta": {
            "engagement": engagement.get("_meta", {}),
            "timestamp": datetime.now().isoformat(),
            "test_mode": True,
        },
        "concepts": {},
    }

    for cid, cdata in all_concept_results.items():
        serialized = [result_to_dict(r) for r in cdata["results"]]
        output["concepts"][cid] = {
            "respondents": serialized,
            "aggregate": {
                "distribution": {str(k): round(v, 4) for k, v in cdata["distribution"].items()},
                "mean_pi": round(cdata["mean_pi"], 4),
                "std_pi": round(cdata["std_pi"], 4),
                "n_respondents": len(serialized),
            },
        }

        # Validate each respondent record
        for resp in serialized:
            assert "persona_id" in resp
            assert "free_text_response" in resp
            assert "averaged_pmf" in resp
            assert "expected_rating" in resp
            assert len(resp["averaged_pmf"]) == 5

    json_str = json.dumps(output, indent=2)
    print(f"  Output JSON: {len(json_str)} chars, {len(json_str.split(chr(10)))} lines")
    print(f"  Concepts: {list(output['concepts'].keys())}")
    print(f"  Respondent records validated ✓")

    # --- Step 6: Cross-concept comparison ---
    print("\n[6/6] Cross-concept comparison...")
    for cid, cdata in all_concept_results.items():
        name = [c for c in concepts if c["concept_id"] == cid][0].get("name", cid)
        print(f"  {name}: PI={cdata['mean_pi']:.2f} ± {cdata['std_pi']:.2f}")

    # --- Done ---
    print("\n" + "=" * 60)
    print("INTEGRATION TEST PASSED")
    print("=" * 60)
    print(f"  {len(personas)} personas × {len(concepts)} concepts × 2 samples = "
          f"{len(personas) * len(concepts) * 2} elicitation calls simulated")
    print(f"  All output structures validated")
    print(f"  Ready for real API calls")
    print("=" * 60)


if __name__ == "__main__":
    run_integration_test()
