"""
test_explorer.py — Validate explorer data loading and transformation.

Run with: python explorer/test_explorer.py
"""

import json
import sys
from pathlib import Path

import pandas as pd


# Inline the core logic from app.py (no Streamlit dependency needed)

def build_respondent_df(results: dict, personas: dict) -> pd.DataFrame:
    persona_lookup = {p["persona_id"]: p for p in personas["personas"]}
    rows = []
    for concept_id, concept_data in results["concepts"].items():
        concept_name = concept_data["concept"].get("name", concept_id)
        for resp in concept_data["respondents"]:
            persona = persona_lookup.get(resp["persona_id"], {})
            pmf = resp["averaged_pmf"]
            rows.append({
                "concept_id": concept_id,
                "concept_name": concept_name,
                "persona_id": resp["persona_id"],
                "free_text": resp["free_text_response"],
                "expected_rating": resp["expected_rating"],
                "mode_rating": resp["mode_rating"],
                "p1": pmf.get("1", 0), "p2": pmf.get("2", 0),
                "p3": pmf.get("3", 0), "p4": pmf.get("4", 0),
                "p5": pmf.get("5", 0),
                "age": persona.get("age"),
                "gender": persona.get("gender"),
                "region": persona.get("region"),
                "income": persona.get("income"),
            })
    df = pd.DataFrame(rows)
    df["top2box"] = df["p4"] + df["p5"]
    df["bottom2box"] = df["p1"] + df["p2"]
    df["sentiment"] = pd.cut(
        df["expected_rating"], bins=[0, 2.5, 3.5, 5.01],
        labels=["Negative", "Neutral", "Positive"],
    )
    df["age_band"] = pd.cut(
        df["age"], bins=[0, 29, 44, 59, 100],
        labels=["18-29", "30-44", "45-59", "60+"],
    )
    return df


def test_all():
    data_dir = Path(__file__).parent / "mock_data"
    assert (data_dir / "results.json").exists(), "Run generate_mock_data.py first"

    with open(data_dir / "results.json") as f:
        results = json.load(f)
    with open(data_dir / "personas.json") as f:
        personas = json.load(f)

    # Test: structure
    assert "meta" in results
    assert "concepts" in results
    assert len(results["concepts"]) == 2
    print("✅ results.json structure valid")

    assert "personas" in personas
    assert "panel_summary" in personas
    print("✅ personas.json structure valid")

    # Test: build DataFrame
    df = build_respondent_df(results, personas)
    n_concepts = len(results["concepts"])
    n_personas = len(personas["personas"])
    assert len(df) == n_concepts * n_personas, (
        f"Expected {n_concepts * n_personas} rows, got {len(df)}"
    )
    print(f"✅ DataFrame built: {len(df)} rows ({n_personas} personas × {n_concepts} concepts)")

    # Test: columns exist
    required_cols = [
        "concept_id", "concept_name", "persona_id", "free_text",
        "expected_rating", "mode_rating", "p1", "p2", "p3", "p4", "p5",
        "age", "gender", "region", "income", "top2box", "bottom2box",
        "sentiment", "age_band",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    print(f"✅ All {len(required_cols)} required columns present")

    # Test: PMFs sum to ~1
    pmf_sum = df[["p1", "p2", "p3", "p4", "p5"]].sum(axis=1)
    assert pmf_sum.between(0.99, 1.01).all(), f"PMF sums not ≈1: {pmf_sum.describe()}"
    print("✅ PMFs sum to ~1.0")

    # Test: expected ratings in range
    assert df["expected_rating"].between(1, 5).all()
    print("✅ Expected ratings in [1, 5]")

    # Test: demographics joined correctly
    assert df["age"].notna().all(), "Missing age values — persona join failed"
    assert df["gender"].notna().all(), "Missing gender values — persona join failed"
    print("✅ Persona demographics joined correctly")

    # Test: derived columns
    assert set(df["sentiment"].dropna().unique()) <= {"Positive", "Neutral", "Negative"}
    assert set(df["age_band"].dropna().unique()) <= {"18-29", "30-44", "45-59", "60+"}
    print("✅ Derived columns (sentiment, age_band) computed correctly")

    # Test: aggregate stats make sense
    for cid, cdata in results["concepts"].items():
        agg = cdata["aggregate"]
        assert 1 <= agg["mean_pi"] <= 5, f"Mean PI out of range: {agg['mean_pi']}"
        assert agg["n_respondents"] == n_personas
        dist_sum = sum(float(v) for v in agg["distribution"].values())
        assert 0.99 <= dist_sum <= 1.01, f"Aggregate dist doesn't sum to 1: {dist_sum}"
    print("✅ Aggregate statistics valid")

    # Summary
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
    print(f"\nDataFrame shape: {df.shape}")
    print(f"Concepts: {df['concept_name'].unique().tolist()}")
    print(f"Mean PI by concept:")
    for name, group in df.groupby("concept_name"):
        print(f"  {name}: {group['expected_rating'].mean():.2f} (std={group['expected_rating'].std():.2f})")


if __name__ == "__main__":
    test_all()
