"""
pipeline.py — End-to-end SSR pipeline orchestrator.

Takes an engagement config and runs:
  1. Generate persona panel from demographic spec
  2. Pre-compute reference set embeddings (cached)
  3. For each persona × concept × sample:
     a. Elicit free-text response from LLM
     b. Embed the response
     c. Score via SSR against all reference sets
  4. Aggregate results at survey level
  5. Write structured JSON output

This is designed to be run via CLI (run_pipeline.py) or imported.
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from core.ssr_scoring import (
    ReferenceSet,
    score_respondent,
    result_to_dict,
    aggregate_survey_distribution,
    survey_mean_pi,
    survey_std_pi,
)
from core.persona_generator import (
    generate_panel,
    load_demographic_spec,
    persona_to_dict,
    panel_summary,
)

# API clients are imported lazily inside run_pipeline() to allow
# dry-run and config loading without API packages installed.


@dataclass
class PipelineConfig:
    """All settings for a pipeline run, loaded from engagement config."""
    engagement_path: Path
    engagement: dict
    concepts: list[dict]
    question_text: str
    reasoning_question: str | None
    reference_sets_path: Path
    llm_provider: str
    llm_model: str
    llm_temperature: float
    llm_top_p: float
    reasoning_temperature: float
    samples_per_persona: int
    embedding_model: str
    ssr_epsilon: float
    ssr_temperature: float
    seed: int
    output_dir: Path
    lifestyle_config_path: Path | None = None
    scoring_persona_tier: int = 2
    mode: str = "full"
    skip_stage_2: bool = False
    skip_insights: bool = False


def apply_mode(config: "PipelineConfig", mode: str) -> None:
    """Apply mode-derived flags to a PipelineConfig in-place.

    "paper" — strict Maier et al. methodology: Tier 1 personas, no Stage 2, no insights.
    "full"  — all extensions: Tier 2 personas (if lifestyle config present), Stage 2, insights.
    """
    config.mode = mode
    if mode == "paper":
        config.lifestyle_config_path = None
        config.skip_stage_2 = True
        config.skip_insights = True
    else:
        config.skip_stage_2 = False
        config.skip_insights = False


def load_pipeline_config(engagement_path: str | Path, output_dir: str | Path = None) -> PipelineConfig:
    """Parse an engagement JSON file into a PipelineConfig."""
    path = Path(engagement_path)
    with open(path) as f:
        eng = json.load(f)

    pipeline = eng["pipeline"]
    question = eng["survey_question"]

    # Load reasoning follow-up question from prompt templates (if available)
    templates_path = path.parent / "prompt_templates.json"
    reasoning_question = None
    if templates_path.exists():
        with open(templates_path) as tf:
            templates = json.load(tf)
        reasoning_q = templates.get("elicitation_prompt", {}).get("reasoning_followup", {})
        reasoning_question = reasoning_q.get("question")

    # Check for lifestyle attributes config (enables Tier 2 rich personas).
    # Engagement config may specify a custom file via pipeline.lifestyle_config;
    # otherwise falls back to the default lifestyle_attributes.json in the config dir.
    custom_lifestyle = pipeline.get("lifestyle_config")
    if custom_lifestyle:
        lifestyle_path = path.parent / custom_lifestyle
    else:
        lifestyle_path = path.parent / "lifestyle_attributes.json"
    lifestyle_config_path = lifestyle_path if lifestyle_path.exists() else None

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("output") / f"run_{timestamp}"

    config = PipelineConfig(
        engagement_path=path,
        engagement=eng,
        concepts=eng["concepts"],
        question_text=question["text"],
        reasoning_question=reasoning_question,
        reference_sets_path=path.parent / question["reference_sets_file"],
        llm_provider=pipeline["llm_provider"],
        llm_model=pipeline["llm_model"],
        llm_temperature=pipeline["llm_temperature"],
        llm_top_p=pipeline["llm_top_p"],
        reasoning_temperature=pipeline.get("reasoning_temperature", 1.0),
        samples_per_persona=pipeline["samples_per_persona"],
        embedding_model=pipeline["embedding_model"],
        ssr_epsilon=pipeline["ssr_epsilon"],
        ssr_temperature=pipeline["ssr_temperature"],
        seed=pipeline["seed"],
        output_dir=Path(output_dir),
        lifestyle_config_path=lifestyle_config_path,
        scoring_persona_tier=pipeline.get("scoring_persona_tier", 2),
    )
    apply_mode(config, pipeline.get("mode", "full"))
    return config


def run_pipeline(config: PipelineConfig):
    """
    Execute the full SSR pipeline.

    Prints progress to stdout. Writes results to config.output_dir.
    """
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # Lazy imports — only needed for real runs, not dry-run or config loading
    from core.embedding_client import EmbeddingClient
    from core.llm_client import create_llm_client

    print("=" * 60)
    print("SSR PIPELINE")
    print("=" * 60)
    meta = config.engagement.get("_meta", {})
    print(f"  Engagement: {meta.get('engagement', 'unnamed')}")
    print(f"  Concepts:   {len(config.concepts)}")
    print(f"  Provider:   {config.llm_provider} / {config.llm_model}")
    print(f"  Output:     {config.output_dir}")
    print()

    # ------------------------------------------------------------------
    # Step 1: Initialize LLM client (needed for both persona gen and elicitation)
    # ------------------------------------------------------------------
    print("[1/5] Initializing LLM client...")
    llm = create_llm_client(
        provider=config.llm_provider,
        model=config.llm_model,
    )
    print(f"  Ready: {config.llm_provider} / {config.llm_model}")
    print()

    # ------------------------------------------------------------------
    # Step 2: Generate persona panel
    # ------------------------------------------------------------------
    tier_label = "Tier 2 (rich)" if config.lifestyle_config_path else "Tier 1 (basic)"
    print(f"[2/5] Generating persona panel ({tier_label})...")
    spec = load_demographic_spec(config.engagement_path)

    def _panel_progress(current, total):
        _progress(current, total, prefix="    Generating personas")

    personas = generate_panel(
        spec=spec,
        prompt_template_path=config.engagement_path.parent / "prompt_templates.json",
        seed=config.seed,
        lifestyle_config_path=config.lifestyle_config_path,
        llm_client=llm if config.lifestyle_config_path else None,
        narrative_temperature=1.0,
        scoring_persona_tier=config.scoring_persona_tier,
        progress_fn=_panel_progress if config.lifestyle_config_path else None,
    )
    if config.lifestyle_config_path:
        print()  # newline after progress bar
    summary = panel_summary(personas)
    print(f"  Panel: {summary['panel_size']} respondents, "
          f"ages {summary['age_min']}-{summary['age_max']} "
          f"(mean {summary['age_mean']})")
    print(f"  Gender: {summary['gender']}")
    print(f"  Region: {summary['region']}")
    if summary.get("lifestyle"):
        print(f"  Lifestyle dimensions: {len(summary['lifestyle'])}")
    print()

    # ------------------------------------------------------------------
    # Step 3: Initialize embedding client and reference sets
    # ------------------------------------------------------------------
    print("[3/5] Initializing embedding client and reference sets...")
    embed_client = EmbeddingClient(
        model=config.embedding_model,
        cache_dir=config.output_dir / ".cache" / "embeddings",
    )

    ref_embeddings = embed_client.embed_reference_sets(config.reference_sets_path)

    # Build ReferenceSet objects
    with open(config.reference_sets_path) as f:
        ref_config = json.load(f)

    reference_sets = []
    for set_name, set_data in ref_config["sets"].items():
        anchors = {int(k): v for k, v in set_data["anchors"].items()}
        reference_sets.append(ReferenceSet(
            name=set_name,
            framing=set_data["framing"],
            anchors=anchors,
            embeddings=ref_embeddings[set_name],
        ))
    print(f"  {len(reference_sets)} reference sets loaded and embedded.")
    print()

    # ------------------------------------------------------------------
    # Step 4: Run elicitation + scoring for each concept
    # ------------------------------------------------------------------
    print("[4/5] Running elicitation and scoring...")
    if config.reasoning_question and not config.skip_stage_2:
        print(f"  Stage 2 enabled: reasoning follow-up per persona (T={config.reasoning_temperature})")

    # Resolve image paths relative to engagement file
    for concept in config.concepts:
        img_path = concept.get("image_path")
        if img_path:
            resolved = Path(img_path)
            if not resolved.is_absolute():
                resolved = config.engagement_path.parent / resolved
            if resolved.exists():
                concept["image_path"] = str(resolved)
                print(f"  Image for {concept.get('name', concept['concept_id'])}: {resolved}")
            else:
                print(f"  ⚠ Image not found for {concept.get('name', concept['concept_id'])}: {resolved}")
                print(f"    Falling back to text description.")
                concept["image_path"] = None

    all_concept_results = {}

    for concept in config.concepts:
        concept_id = concept["concept_id"]
        concept_name = concept.get("name", concept_id)
        print(f"\n  --- Concept: {concept_name} ({concept_id}) ---")

        concept_results = []
        total_calls = spec.panel_size * config.samples_per_persona
        call_count = 0

        for persona in personas:
            sample_pmfs = []

            for sample_idx in range(config.samples_per_persona):
                call_count += 1
                _progress(call_count, total_calls, prefix=f"    Eliciting")

                # Elicit free-text response
                try:
                    response_text = llm.elicit_response(
                        system_prompt=persona.system_prompt,
                        concept_text=concept.get("description"),
                        concept_image_path=concept.get("image_path"),
                        question=config.question_text,
                        temperature=config.llm_temperature,
                        top_p=config.llm_top_p,
                    )
                except Exception as e:
                    print(f"\n    ⚠ Error for {persona.persona_id} sample {sample_idx}: {e}")
                    continue

                # Embed response
                response_embedding = embed_client.embed(response_text)

                # Score via SSR
                result = score_respondent(
                    persona_id=f"{persona.persona_id}_s{sample_idx}",
                    free_text_response=response_text,
                    response_embedding=response_embedding,
                    reference_sets=reference_sets,
                    epsilon=config.ssr_epsilon,
                    temperature=config.ssr_temperature,
                )
                sample_pmfs.append(result)

            # Average the n samples for this persona into concept_results
            if sample_pmfs:
                # Use the last sample's full data but with averaged pmf across samples
                if len(sample_pmfs) == 1:
                    final_result = sample_pmfs[0]
                else:
                    from core.ssr_scoring import average_pmfs, pmf_expected_value, pmf_mode, SSRResult
                    avg_pmf = average_pmfs([r.averaged_pmf for r in sample_pmfs])
                    final_result = SSRResult(
                        persona_id=persona.persona_id,
                        free_text_response=" | ".join(r.free_text_response for r in sample_pmfs),
                        per_set_similarities=sample_pmfs[0].per_set_similarities,
                        per_set_pmfs=sample_pmfs[0].per_set_pmfs,
                        averaged_pmf=avg_pmf,
                        expected_rating=pmf_expected_value(avg_pmf),
                        mode_rating=pmf_mode(avg_pmf),
                    )

                # Stage 2: Reasoning follow-up (qualitative only, not scored)
                if config.reasoning_question and not config.skip_stage_2:
                    try:
                        reasoning_text = llm.elicit_response(
                            system_prompt=persona.reasoning_prompt or persona.system_prompt,
                            concept_text=concept.get("description"),
                            concept_image_path=concept.get("image_path"),
                            question=config.reasoning_question,
                            temperature=config.reasoning_temperature,
                            top_p=config.llm_top_p,
                            max_tokens=400,  # Allow longer reasoning responses
                        )
                        final_result.reasoning_response = reasoning_text
                    except Exception as e:
                        print(f"\n    ⚠ Reasoning error for {persona.persona_id}: {e}")

                concept_results.append(final_result)

        print()  # newline after progress bar

        # Aggregate concept-level stats
        if concept_results:
            dist = aggregate_survey_distribution(concept_results)
            mean_pi = survey_mean_pi(concept_results)
            std_pi = survey_std_pi(concept_results)

            print(f"    Mean PI: {mean_pi:.2f} (std: {std_pi:.2f})")
            print(f"    Distribution: {_format_dist(dist)}")
        else:
            dist = {}
            mean_pi = 0
            std_pi = 0
            print(f"    ⚠ No results collected")

        all_concept_results[concept_id] = {
            "concept": concept,
            "panel_summary": summary,
            "respondents": [result_to_dict(r) for r in concept_results],
            "aggregate": {
                "distribution": {str(k): round(v, 4) for k, v in dist.items()},
                "mean_pi": round(mean_pi, 4),
                "std_pi": round(std_pi, 4),
                "n_respondents": len(concept_results),
            },
        }

    # ------------------------------------------------------------------
    # Step 5: Write output
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("WRITING OUTPUT")
    print("=" * 60)

    # Full results file
    output = {
        "meta": {
            "engagement": meta,
            "pipeline_config": {
                "mode": config.mode,
                "llm_provider": config.llm_provider,
                "llm_model": config.llm_model,
                "llm_temperature": config.llm_temperature,
                "embedding_model": config.embedding_model,
                "ssr_epsilon": config.ssr_epsilon,
                "ssr_temperature": config.ssr_temperature,
                "samples_per_persona": config.samples_per_persona,
                "seed": config.seed,
                "reference_sets": list(ref_config["sets"].keys()),
            },
            "timestamp": datetime.now().isoformat(),
        },
        "concepts": all_concept_results,
    }

    results_path = config.output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  Full results:  {results_path}")

    # Summary file (quick-look without individual respondent data)
    summary_output = {
        "meta": output["meta"],
        "summary": {},
    }
    for cid, cdata in all_concept_results.items():
        summary_output["summary"][cid] = {
            "concept_name": cdata["concept"].get("name", cid),
            **cdata["aggregate"],
        }

    summary_path = config.output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary_output, f, indent=2)
    print(f"  Summary:       {summary_path}")

    # Personas file
    personas_path = config.output_dir / "personas.json"
    with open(personas_path, "w") as f:
        json.dump({
            "panel_summary": summary,
            "personas": [persona_to_dict(p) for p in personas],
        }, f, indent=2)
    print(f"  Personas:      {personas_path}")

    # Insights file (LLM-synthesized themes and recommendations)
    if config.skip_insights:
        print("\n  Insights skipped (mode: paper).")
        print(f"    Generate later with: python -m core.insights_generator {results_path}")
    else:
        print("\n  Generating insights (GPT-4o-mini)...")
        try:
            from core.insights_generator import generate_insights
            personas_data = {
                "panel_summary": summary,
                "personas": [persona_to_dict(p) for p in personas],
            }
            insights = generate_insights(output, personas_data)
            insights_path = config.output_dir / "insights.json"
            with open(insights_path, "w") as f:
                json.dump(insights, f, indent=2)
            print(f"  Insights:      {insights_path}")
        except Exception as e:
            print(f"  ⚠ Insights generation failed (non-blocking): {e}")
            print(f"    You can generate insights later with:")
            print(f"    python -m core.insights_generator {results_path}")

    print(f"\nDone. {sum(len(c['respondents']) for c in all_concept_results.values())} "
          f"total respondent records across {len(config.concepts)} concepts.")

    return output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress(current: int, total: int, prefix: str = ""):
    """Simple progress indicator."""
    pct = current / total * 100
    sys.stdout.write(f"\r{prefix}: {current}/{total} ({pct:.0f}%)")
    sys.stdout.flush()


def _format_dist(dist: dict[int, float]) -> str:
    """Format a Likert distribution for terminal display."""
    parts = []
    for r in range(1, 6):
        p = dist.get(r, 0)
        bar = "█" * int(p * 20)
        parts.append(f"{r}:{p:.0%}{bar}")
    return "  ".join(parts)