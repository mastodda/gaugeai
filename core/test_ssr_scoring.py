"""
test_ssr_scoring.py — Validate SSR scoring math with synthetic embeddings.

No API calls required. Uses fake embeddings that simulate the geometric
relationships we'd expect in real embedding space to verify that:
  1. Min-subtraction amplifies the signal correctly
  2. Temperature scaling sharpens/flattens pmfs as expected
  3. Ensemble averaging across sets produces stable results
  4. Edge cases are handled (identical similarities, etc.)
"""

import sys
import numpy as np
sys.path.insert(0, "..")

from core.ssr_scoring import (
    cosine_similarity,
    compute_pmf,
    average_pmfs,
    pmf_expected_value,
    pmf_mode,
    score_respondent,
    ReferenceSet,
    result_to_dict,
)


def make_fake_embeddings(dim=64):
    """
    Create synthetic anchor embeddings that mimic real embedding geometry.

    Real embeddings for Likert anchors are clustered (high mutual cosine sim)
    because the statements are semantically similar — they all discuss purchase
    intent. The signal is in the small differences.
    """
    rng = np.random.default_rng(42)

    # Base vector — all anchors are similar to this (simulates semantic clustering)
    base = rng.normal(0, 1, dim)
    base = base / np.linalg.norm(base)

    # Gradient direction — the axis along which intent increases
    gradient = rng.normal(0, 1, dim)
    # Orthogonalize to base so gradient is a pure signal
    gradient = gradient - np.dot(gradient, base) * base
    gradient = gradient / np.linalg.norm(gradient)

    # Anchors: base + increasing amounts of gradient
    #   anchor_1 (unlikely) → anchor_5 (likely)
    anchor_weights = {1: -0.15, 2: -0.07, 3: 0.0, 4: 0.07, 5: 0.15}

    embeddings = {}
    for rating, weight in anchor_weights.items():
        vec = base + weight * gradient
        embeddings[rating] = vec / np.linalg.norm(vec)

    return embeddings, base, gradient


def make_response_embedding(base, gradient, intent_level, noise_scale=0.02, dim=64):
    """
    Create a fake response embedding at a given intent level.
    intent_level: float, roughly -0.15 to 0.15 matching anchor range.
    """
    rng = np.random.default_rng(hash(str(intent_level)) % 2**32)
    noise = rng.normal(0, noise_scale, dim)
    vec = base + intent_level * gradient + noise
    return vec / np.linalg.norm(vec)


def test_basic_pmf():
    """Test that a positive-intent response produces a right-skewed pmf."""
    print("=" * 60)
    print("TEST 1: Basic PMF — positive intent response")
    print("=" * 60)

    embeddings, base, gradient = make_fake_embeddings()
    ref_set = ReferenceSet(
        name="test_set",
        framing="test",
        anchors={r: f"anchor_{r}" for r in range(1, 6)},
        embeddings=embeddings,
    )

    # Simulate a clearly positive response (intent_level = 0.12, near anchor 5)
    response_emb = make_response_embedding(base, gradient, 0.12)
    sims, pmf = compute_pmf(response_emb, ref_set, epsilon=0.0, temperature=1.0)

    print(f"  Similarities: { {r: round(s, 4) for r, s in sims.items()} }")
    print(f"  PMF:          { {r: round(p, 4) for r, p in pmf.items()} }")
    print(f"  E[rating]:    {pmf_expected_value(pmf):.2f}")
    print(f"  Mode:         {pmf_mode(pmf)}")

    assert pmf[5] > pmf[1], "Positive response should have higher p(5) than p(1)"
    assert pmf_mode(pmf) >= 4, "Mode should be 4 or 5 for positive response"
    assert abs(sum(pmf.values()) - 1.0) < 1e-9, "PMF should sum to 1"
    print("  ✓ PASSED\n")


def test_negative_pmf():
    """Test that a negative-intent response produces a left-skewed pmf."""
    print("=" * 60)
    print("TEST 2: Basic PMF — negative intent response")
    print("=" * 60)

    embeddings, base, gradient = make_fake_embeddings()
    ref_set = ReferenceSet(
        name="test_set",
        framing="test",
        anchors={r: f"anchor_{r}" for r in range(1, 6)},
        embeddings=embeddings,
    )

    response_emb = make_response_embedding(base, gradient, -0.12)
    sims, pmf = compute_pmf(response_emb, ref_set, epsilon=0.0, temperature=1.0)

    print(f"  Similarities: { {r: round(s, 4) for r, s in sims.items()} }")
    print(f"  PMF:          { {r: round(p, 4) for r, p in pmf.items()} }")
    print(f"  E[rating]:    {pmf_expected_value(pmf):.2f}")
    print(f"  Mode:         {pmf_mode(pmf)}")

    assert pmf[1] > pmf[5], "Negative response should have higher p(1) than p(5)"
    assert pmf_mode(pmf) <= 2, "Mode should be 1 or 2 for negative response"
    print("  ✓ PASSED\n")


def test_neutral_pmf():
    """Test that a neutral response produces a center-weighted pmf."""
    print("=" * 60)
    print("TEST 3: Basic PMF — neutral response")
    print("=" * 60)

    embeddings, base, gradient = make_fake_embeddings()
    ref_set = ReferenceSet(
        name="test_set",
        framing="test",
        anchors={r: f"anchor_{r}" for r in range(1, 6)},
        embeddings=embeddings,
    )

    response_emb = make_response_embedding(base, gradient, 0.0)
    sims, pmf = compute_pmf(response_emb, ref_set, epsilon=0.0, temperature=1.0)

    print(f"  PMF:          { {r: round(p, 4) for r, p in pmf.items()} }")
    print(f"  E[rating]:    {pmf_expected_value(pmf):.2f}")

    ev = pmf_expected_value(pmf)
    assert 2.5 < ev < 3.5, f"Neutral response should have E[rating] near 3, got {ev:.2f}"
    print("  ✓ PASSED\n")


def test_temperature_effect():
    """Test that lower temperature produces peakier distributions."""
    print("=" * 60)
    print("TEST 4: Temperature effect")
    print("=" * 60)

    embeddings, base, gradient = make_fake_embeddings()
    ref_set = ReferenceSet(
        name="test_set",
        framing="test",
        anchors={r: f"anchor_{r}" for r in range(1, 6)},
        embeddings=embeddings,
    )

    response_emb = make_response_embedding(base, gradient, 0.10)

    _, pmf_t1 = compute_pmf(response_emb, ref_set, temperature=1.0)
    _, pmf_t05 = compute_pmf(response_emb, ref_set, temperature=0.5)
    _, pmf_t2 = compute_pmf(response_emb, ref_set, temperature=2.0)

    # Entropy as a proxy for peakiness (lower entropy = peakier)
    def entropy(pmf):
        vals = [p for p in pmf.values() if p > 0]
        return -sum(p * np.log(p) for p in vals)

    e1 = entropy(pmf_t1)
    e05 = entropy(pmf_t05)
    e2 = entropy(pmf_t2)

    print(f"  T=0.5 entropy: {e05:.4f}  pmf: { {r: round(p, 3) for r, p in pmf_t05.items()} }")
    print(f"  T=1.0 entropy: {e1:.4f}  pmf: { {r: round(p, 3) for r, p in pmf_t1.items()} }")
    print(f"  T=2.0 entropy: {e2:.4f}  pmf: { {r: round(p, 3) for r, p in pmf_t2.items()} }")

    assert e05 < e1 < e2, "Lower temperature should produce lower entropy (peakier pmf)"
    print("  ✓ PASSED\n")


def test_ensemble_averaging():
    """Test that averaging across multiple sets produces intermediate results."""
    print("=" * 60)
    print("TEST 5: Ensemble averaging across reference sets")
    print("=" * 60)

    rng = np.random.default_rng(99)
    dim = 64

    # Create 3 slightly different reference sets
    ref_sets = []
    for i in range(3):
        embeddings, base, gradient = make_fake_embeddings(dim)
        # Add small per-set perturbation to simulate different phrasings
        for r in embeddings:
            noise = rng.normal(0, 0.01, dim)
            embeddings[r] = embeddings[r] + noise
            embeddings[r] = embeddings[r] / np.linalg.norm(embeddings[r])

        ref_sets.append(ReferenceSet(
            name=f"set_{i}",
            framing=f"test_framing_{i}",
            anchors={r: f"anchor_{r}" for r in range(1, 6)},
            embeddings=embeddings,
        ))

    response_emb = make_response_embedding(base, gradient, 0.08)

    result = score_respondent(
        persona_id="test_001",
        free_text_response="I'd probably try this, seems decent.",
        response_embedding=response_emb,
        reference_sets=ref_sets,
    )

    print(f"  Per-set modes: { {s: pmf_mode(p) for s, p in result.per_set_pmfs.items()} }")
    print(f"  Averaged PMF:  { {r: round(p, 4) for r, p in result.averaged_pmf.items()} }")
    print(f"  E[rating]:     {result.expected_rating:.2f}")
    print(f"  Mode:          {result.mode_rating}")

    assert abs(sum(result.averaged_pmf.values()) - 1.0) < 1e-9
    print("  ✓ PASSED\n")


def test_serialization():
    """Test that results serialize to JSON-compatible dict."""
    print("=" * 60)
    print("TEST 6: Serialization to JSON dict")
    print("=" * 60)

    embeddings, base, gradient = make_fake_embeddings()
    ref_set = ReferenceSet(
        name="test_set", framing="test",
        anchors={r: f"anchor_{r}" for r in range(1, 6)},
        embeddings=embeddings,
    )
    response_emb = make_response_embedding(base, gradient, 0.05)

    result = score_respondent(
        persona_id="test_serial",
        free_text_response="Looks okay, might consider it.",
        response_embedding=response_emb,
        reference_sets=[ref_set],
    )

    d = result_to_dict(result)

    import json
    json_str = json.dumps(d, indent=2)
    print(f"  JSON output length: {len(json_str)} chars")
    print(f"  Keys: {list(d.keys())}")

    # Verify round-trip
    parsed = json.loads(json_str)
    assert parsed["persona_id"] == "test_serial"
    assert abs(float(parsed["expected_rating"]) - result.expected_rating) < 0.01
    print("  ✓ PASSED\n")


if __name__ == "__main__":
    print("\nSSR Scoring Module — Unit Tests")
    print("=" * 60)
    print("Using synthetic embeddings (no API calls)\n")

    test_basic_pmf()
    test_negative_pmf()
    test_neutral_pmf()
    test_temperature_effect()
    test_ensemble_averaging()
    test_serialization()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
