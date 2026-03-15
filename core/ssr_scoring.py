"""
ssr_scoring.py — Semantic Similarity Rating (SSR) scoring module.

Implements the SSR method from Maier et al. (2025):
  1. Embed free-text response and reference anchors
  2. Compute cosine similarity between response and each anchor
  3. Subtract minimum similarity (per set) to amplify signal
  4. Apply optional temperature scaling
  5. Normalize to probability mass function (pmf) over Likert scale
  6. Average pmfs across multiple reference sets

This module is intentionally dependency-light. It expects embeddings
as input (numpy arrays) so the embedding API call is handled elsewhere.
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SSRResult:
    """Result for a single synthetic respondent."""
    persona_id: str
    free_text_response: str
    per_set_similarities: dict[str, dict[int, float]]  # set_name -> {1: sim, ..., 5: sim}
    per_set_pmfs: dict[str, dict[int, float]]           # set_name -> {1: p, ..., 5: p}
    averaged_pmf: dict[int, float]                       # {1: p, ..., 5: p}
    expected_rating: float                               # E[r] = sum(r * p(r))
    mode_rating: int                                     # argmax of averaged pmf
    reasoning_response: str | None = None                # Stage 2: qualitative reasoning (not scored)


@dataclass
class ReferenceSet:
    """A single reference set: 5 anchor statements with their embeddings."""
    name: str
    framing: str
    anchors: dict[int, str]              # {1: "text", ..., 5: "text"}
    embeddings: dict[int, np.ndarray]    # {1: vector, ..., 5: vector}


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def compute_pmf(
    response_embedding: np.ndarray,
    reference_set: ReferenceSet,
    epsilon: float = 0.0,
    temperature: float = 1.0,
) -> tuple[dict[int, float], dict[int, float]]:
    """
    Compute Likert pmf for a single response against a single reference set.

    Implements equations (7)-(9) from the paper:
      γ(σ_r, t) = cosine_sim(v_σr, v_t)
      p(r) ∝ [γ(σ_r, t) - γ(σ_ℓ, t) + ε·δ(ℓ,r)]^(1/T)
    where ℓ is the anchor with minimum similarity.

    Args:
        response_embedding: Embedding vector of the free-text response.
        reference_set: ReferenceSet with pre-computed anchor embeddings.
        epsilon: Floor parameter. 0.0 = one rating always gets p=0. Paper default: 0.0.
        temperature: Post-elicitation temperature. Controls pmf sharpness. Paper default: 1.0.

    Returns:
        Tuple of (raw similarities dict, normalized pmf dict).
    """
    # Step 1: Compute cosine similarities to each anchor
    similarities = {}
    for rating, anchor_emb in reference_set.embeddings.items():
        similarities[rating] = cosine_similarity(response_embedding, anchor_emb)

    # Step 2: Find minimum similarity
    min_rating = min(similarities, key=similarities.get)
    min_sim = similarities[min_rating]

    # Step 3: Subtract minimum, apply epsilon floor
    adjusted = {}
    for rating, sim in similarities.items():
        val = sim - min_sim
        if rating == min_rating:
            val += epsilon
        adjusted[rating] = val

    # Step 4: Apply temperature scaling (if T != 1)
    if temperature != 1.0 and temperature > 0:
        for rating in adjusted:
            # Avoid 0^(1/T) issues when epsilon=0
            if adjusted[rating] > 0:
                adjusted[rating] = adjusted[rating] ** (1.0 / temperature)
            # If val is 0, it stays 0 regardless of temperature

    # Step 5: Normalize to pmf
    total = sum(adjusted.values())
    pmf = {}
    if total > 0:
        for rating in sorted(adjusted.keys()):
            pmf[rating] = adjusted[rating] / total
    else:
        # Fallback: uniform if all similarities are identical (shouldn't happen)
        for rating in sorted(adjusted.keys()):
            pmf[rating] = 0.2

    return similarities, pmf


def average_pmfs(pmf_list: list[dict[int, float]]) -> dict[int, float]:
    """Average multiple pmfs element-wise. Used to ensemble across reference sets."""
    n = len(pmf_list)
    if n == 0:
        return {r: 0.2 for r in range(1, 6)}

    averaged = {r: 0.0 for r in range(1, 6)}
    for pmf in pmf_list:
        for r in range(1, 6):
            averaged[r] += pmf.get(r, 0.0)
    for r in averaged:
        averaged[r] /= n
    return averaged


def pmf_expected_value(pmf: dict[int, float]) -> float:
    """E[r] = sum(r * p(r))."""
    return sum(r * p for r, p in pmf.items())


def pmf_mode(pmf: dict[int, float]) -> int:
    """Most likely rating."""
    return max(pmf, key=pmf.get)


# ---------------------------------------------------------------------------
# Full scoring pipeline for one respondent
# ---------------------------------------------------------------------------

def score_respondent(
    persona_id: str,
    free_text_response: str,
    response_embedding: np.ndarray,
    reference_sets: list[ReferenceSet],
    epsilon: float = 0.0,
    temperature: float = 1.0,
) -> SSRResult:
    """
    Full SSR scoring for a single respondent across all reference sets.

    Args:
        persona_id: Unique identifier for this synthetic respondent.
        free_text_response: The raw text the LLM generated.
        response_embedding: Pre-computed embedding of the free-text response.
        reference_sets: List of ReferenceSet objects with pre-computed embeddings.
        epsilon: SSR epsilon parameter (default 0.0).
        temperature: SSR temperature parameter (default 1.0).

    Returns:
        SSRResult with all intermediate and final scoring data.
    """
    per_set_similarities = {}
    per_set_pmfs = {}
    pmfs_to_average = []

    for ref_set in reference_sets:
        sims, pmf = compute_pmf(
            response_embedding=response_embedding,
            reference_set=ref_set,
            epsilon=epsilon,
            temperature=temperature,
        )
        per_set_similarities[ref_set.name] = sims
        per_set_pmfs[ref_set.name] = pmf
        pmfs_to_average.append(pmf)

    averaged = average_pmfs(pmfs_to_average)

    return SSRResult(
        persona_id=persona_id,
        free_text_response=free_text_response,
        per_set_similarities=per_set_similarities,
        per_set_pmfs=per_set_pmfs,
        averaged_pmf=averaged,
        expected_rating=pmf_expected_value(averaged),
        mode_rating=pmf_mode(averaged),
    )


# ---------------------------------------------------------------------------
# Reference set loading
# ---------------------------------------------------------------------------

def load_reference_sets_from_config(
    config_path: str | Path,
    embed_fn=None,
) -> list[ReferenceSet]:
    """
    Load reference sets from config JSON file.

    Args:
        config_path: Path to reference_sets.json.
        embed_fn: Callable that takes a string and returns a numpy array.
                  If None, returns ReferenceSet objects without embeddings
                  (embeddings must be populated separately).

    Returns:
        List of ReferenceSet objects.
    """
    with open(config_path) as f:
        config = json.load(f)

    sets = []
    for set_name, set_data in config["sets"].items():
        anchors = {int(k): v for k, v in set_data["anchors"].items()}

        embeddings = {}
        if embed_fn is not None:
            for rating, text in anchors.items():
                embeddings[rating] = embed_fn(text)

        sets.append(ReferenceSet(
            name=set_name,
            framing=set_data["framing"],
            anchors=anchors,
            embeddings=embeddings,
        ))

    return sets


# ---------------------------------------------------------------------------
# Aggregation utilities (survey-level)
# ---------------------------------------------------------------------------

def aggregate_survey_distribution(results: list[SSRResult]) -> dict[int, float]:
    """Average individual pmfs into a survey-level Likert distribution."""
    return average_pmfs([r.averaged_pmf for r in results])


def survey_mean_pi(results: list[SSRResult]) -> float:
    """Mean purchase intent across all respondents."""
    return float(np.mean([r.expected_rating for r in results]))


def survey_std_pi(results: list[SSRResult]) -> float:
    """Standard deviation of expected ratings across respondents."""
    return float(np.std([r.expected_rating for r in results]))


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def result_to_dict(result: SSRResult) -> dict:
    """Convert SSRResult to JSON-serializable dict for storage."""
    d = {
        "persona_id": result.persona_id,
        "free_text_response": result.free_text_response,
        "per_set_similarities": {
            k: {str(r): round(s, 6) for r, s in v.items()}
            for k, v in result.per_set_similarities.items()
        },
        "per_set_pmfs": {
            k: {str(r): round(p, 6) for r, p in v.items()}
            for k, v in result.per_set_pmfs.items()
        },
        "averaged_pmf": {str(r): round(p, 6) for r, p in result.averaged_pmf.items()},
        "expected_rating": round(result.expected_rating, 4),
        "mode_rating": result.mode_rating,
    }
    if result.reasoning_response is not None:
        d["reasoning_response"] = result.reasoning_response
    return d
