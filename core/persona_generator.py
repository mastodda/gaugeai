"""
persona_generator.py — Generate synthetic consumer personas from demographics + lifestyle attributes.

Two-tier persona generation:
  Tier 1 (basic): Sample demographics, render a template-based system prompt.
         Same as original — fast, no API calls, good for dry runs and SSR scoring.
  Tier 2 (rich):  Sample demographics + lifestyle attributes, use an LLM to generate
         a detailed persona narrative. Produces more varied and realistic responses,
         especially for stage 2 reasoning. Requires an LLM client.

The paper conditioned personas on age, gender, income, region, and (rarely) ethnicity.
Age and income were well-replicated by LLMs; gender, region, and ethnicity were
inconsistently captured. Tier 2 adds household composition, shopping mindset,
health orientation, brand adoption style, shopping channel, and media influence.
"""

import json
import random
from pathlib import Path
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Persona:
    """A single synthetic consumer persona."""
    persona_id: str
    age: int
    gender: str
    region: str
    income: str | None = None
    ethnicity: str | None = None
    # Lifestyle attributes (Tier 2)
    lifestyle: dict = field(default_factory=dict)
    # Prompts
    system_prompt: str = ""           # Used for stage 1 (scoring elicitation)
    reasoning_prompt: str = ""        # Used for stage 2 (reasoning elicitation)
    persona_narrative: str = ""       # Raw LLM-generated narrative (for storage)


@dataclass
class DemographicSpec:
    """
    Specification for generating a panel of personas.

    All distributions are dicts mapping category → relative weight.
    Weights don't need to sum to 1; they'll be normalized.
    """
    panel_size: int = 100
    age_range: tuple[int, int] = (18, 75)
    gender_distribution: dict[str, float] = field(
        default_factory=lambda: {"woman": 0.5, "man": 0.5}
    )
    region_distribution: dict[str, float] = field(
        default_factory=lambda: {
            "Midwest": 0.21,
            "Northeast": 0.17,
            "South": 0.38,
            "West": 0.24,
        }
    )
    income_distribution: dict[str, float] | None = None
    ethnicity_distribution: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------

def _weighted_sample(distribution: dict[str, float], rng: random.Random) -> str:
    """Sample a single value from a weighted distribution."""
    keys = list(distribution.keys())
    weights = list(distribution.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def _resolve_distribution(
    dimension: dict,
    persona_age: int,
    persona_income: str | None,
) -> dict[str, float]:
    """
    Resolve the correct distribution for a dimension, applying conditional
    overrides based on age and income if they exist.

    Overrides are checked in order; the first match wins.
    """
    base = dimension["values"]
    overrides = dimension.get("conditional_overrides", {})

    for condition, override_dist in overrides.items():
        if _eval_condition(condition, persona_age, persona_income):
            return override_dist

    return base


def _eval_condition(condition: str, age: int, income: str | None) -> bool:
    """Evaluate a simple condition string like 'age < 30' or 'income == \"low\"'."""
    condition = condition.strip()

    if condition.startswith("age"):
        parts = condition.split()
        if len(parts) == 3:
            op, val = parts[1], int(parts[2])
            if op == "<":
                return age < val
            elif op == ">":
                return age > val
            elif op == "<=":
                return age <= val
            elif op == ">=":
                return age >= val
            elif op == "==":
                return age == val

    if condition.startswith("income") and income:
        # Handle: income == 'low'
        if "==" in condition:
            target = condition.split("==")[1].strip().strip("'\"")
            return income == target

    return False


def _sample_lifestyle(
    lifestyle_config: dict,
    persona_age: int,
    persona_income: str | None,
    rng: random.Random,
) -> dict[str, str]:
    """
    Sample one value from each lifestyle dimension, respecting conditional overrides.

    Returns dict like:
        {"household_composition": "couple, no children", "shopping_mindset": "deal hunter — ...", ...}
    """
    dimensions = lifestyle_config.get("dimensions", {})
    sampled = {}

    for dim_name, dim_config in dimensions.items():
        dist = _resolve_distribution(dim_config, persona_age, persona_income)
        sampled[dim_name] = _weighted_sample(dist, rng)

    return sampled


# ---------------------------------------------------------------------------
# System prompt rendering (Tier 1 — template-based)
# ---------------------------------------------------------------------------

def _render_system_prompt(persona: Persona, template: dict) -> str:
    """
    Render the basic system prompt from template config and persona attributes.
    Used for Tier 1 (no LLM narrative) and as fallback.
    """
    income_clause = ""
    if persona.income:
        income_clause = f" with a {persona.income} household income"

    ethnicity_clause = ""
    if persona.ethnicity:
        ethnicity_clause = f" who identifies as {persona.ethnicity}"

    prompt = template["template"].format(
        age=persona.age,
        gender=persona.gender,
        region=persona.region,
        income_clause=income_clause,
        ethnicity_clause=ethnicity_clause,
    )
    return prompt


# ---------------------------------------------------------------------------
# Persona narrative generation (Tier 2 — LLM-based)
# ---------------------------------------------------------------------------

def generate_persona_narrative(
    persona: Persona,
    lifestyle_config: dict,
    llm_client,
    temperature: float = 1.0,
) -> str:
    """
    Use an LLM to generate a rich persona narrative from structured attributes.

    Args:
        persona: Persona with demographics and lifestyle attributes populated.
        lifestyle_config: The full lifestyle_attributes.json config.
        llm_client: An LLMClient instance (from llm_client.py).
        temperature: Higher = more creative/varied narratives. Default 1.0.

    Returns:
        A 2-3 paragraph persona narrative string.
    """
    narrative_config = lifestyle_config["persona_narrative_prompt"]

    system_prompt = narrative_config["template"]

    # Build the user message from the template
    user_msg = narrative_config["user_message_template"].format(
        age=persona.age,
        gender=persona.gender,
        region=persona.region,
        income=persona.income or "not specified",
        household_composition=persona.lifestyle.get("household_composition", "not specified"),
        shopping_mindset=persona.lifestyle.get("shopping_mindset", "not specified"),
        health_orientation=persona.lifestyle.get("health_orientation", "not specified"),
        brand_adoption_style=persona.lifestyle.get("brand_adoption_style", "not specified"),
        primary_shopping_channel=persona.lifestyle.get("primary_shopping_channel", "not specified"),
        media_influence=persona.lifestyle.get("media_influence", "not specified"),
    )

    # Use the LLM client's elicit_response — it works for any prompt
    narrative = llm_client.elicit_response(
        system_prompt=system_prompt,
        concept_text=user_msg,
        question="Write the persona now.",
        temperature=temperature,
        top_p=0.95,
        max_tokens=500,
    )

    return narrative


def _render_rich_prompts(persona: Persona, lifestyle_config: dict) -> tuple[str, str]:
    """
    Render the stage 1 (scoring) and stage 2 (reasoning) system prompts
    from a persona narrative.

    Returns:
        (system_prompt for scoring, system_prompt for reasoning)
    """
    narrative_config = lifestyle_config["persona_narrative_prompt"]
    narrative = persona.persona_narrative

    scoring_prompt = narrative_config["elicitation_system_prompt_template"].format(
        persona_narrative=narrative,
    )
    reasoning_prompt = narrative_config["reasoning_system_prompt_template"].format(
        persona_narrative=narrative,
    )

    return scoring_prompt, reasoning_prompt


# ---------------------------------------------------------------------------
# Panel generation
# ---------------------------------------------------------------------------

def generate_panel(
    spec: DemographicSpec,
    prompt_template_path: str | Path,
    seed: int = 42,
    lifestyle_config_path: str | Path | None = None,
    llm_client=None,
    narrative_temperature: float = 1.0,
    progress_fn=None,
) -> list[Persona]:
    """
    Generate a full panel of personas from a demographic spec.

    Args:
        spec: DemographicSpec defining the panel composition.
        prompt_template_path: Path to prompt_templates.json.
        seed: Random seed for reproducibility.
        lifestyle_config_path: Path to lifestyle_attributes.json.
            If provided (with llm_client), generates Tier 2 rich personas.
            If None, generates Tier 1 template-based personas.
        llm_client: LLM client for narrative generation. Required for Tier 2.
        narrative_temperature: Temperature for persona narrative generation.
        progress_fn: Optional callback(current, total) for progress display.

    Returns:
        List of Persona objects with rendered system prompts.
    """
    with open(prompt_template_path) as f:
        templates = json.load(f)
    sys_template = templates["system_prompt"]

    # Load lifestyle config if provided
    lifestyle_config = None
    if lifestyle_config_path:
        with open(lifestyle_config_path) as f:
            lifestyle_config = json.load(f)

    use_rich = lifestyle_config is not None and llm_client is not None

    rng = random.Random(seed)
    personas = []

    for i in range(spec.panel_size):
        age = rng.randint(spec.age_range[0], spec.age_range[1])
        gender = _weighted_sample(spec.gender_distribution, rng)
        region = _weighted_sample(spec.region_distribution, rng)

        income = None
        if spec.income_distribution:
            income = _weighted_sample(spec.income_distribution, rng)

        ethnicity = None
        if spec.ethnicity_distribution:
            ethnicity = _weighted_sample(spec.ethnicity_distribution, rng)

        persona = Persona(
            persona_id=f"resp_{i:04d}",
            age=age,
            gender=gender,
            region=region,
            income=income,
            ethnicity=ethnicity,
        )

        if use_rich:
            # Tier 2: sample lifestyle attributes and generate narrative
            persona.lifestyle = _sample_lifestyle(
                lifestyle_config, persona.age, persona.income, rng,
            )

            narrative = generate_persona_narrative(
                persona=persona,
                lifestyle_config=lifestyle_config,
                llm_client=llm_client,
                temperature=narrative_temperature,
            )
            persona.persona_narrative = narrative

            scoring_prompt, reasoning_prompt = _render_rich_prompts(
                persona, lifestyle_config,
            )
            persona.system_prompt = scoring_prompt
            persona.reasoning_prompt = reasoning_prompt

        else:
            # Tier 1: template-based prompt
            persona.system_prompt = _render_system_prompt(persona, sys_template)
            persona.reasoning_prompt = persona.system_prompt  # same prompt, both stages

        personas.append(persona)

        if progress_fn:
            progress_fn(i + 1, spec.panel_size)

    return personas


# ---------------------------------------------------------------------------
# Loading and serialization
# ---------------------------------------------------------------------------

def load_demographic_spec(path: str | Path) -> DemographicSpec:
    """Load a demographic spec from a JSON engagement config file."""
    with open(path) as f:
        data = json.load(f)

    demo = data.get("demographics", data)

    spec = DemographicSpec(
        panel_size=demo.get("panel_size", 100),
        age_range=tuple(demo.get("age_range", [18, 75])),
        gender_distribution=demo.get("gender_distribution", {"woman": 0.5, "man": 0.5}),
        region_distribution=demo.get("region_distribution", {
            "Midwest": 0.21, "Northeast": 0.17, "South": 0.38, "West": 0.24,
        }),
        income_distribution=demo.get("income_distribution"),
        ethnicity_distribution=demo.get("ethnicity_distribution"),
    )
    return spec


def persona_to_dict(persona: Persona) -> dict:
    """Serialize a persona for JSON storage."""
    d = {
        "persona_id": persona.persona_id,
        "age": persona.age,
        "gender": persona.gender,
        "region": persona.region,
        "income": persona.income,
        "ethnicity": persona.ethnicity,
        "system_prompt": persona.system_prompt,
    }
    if persona.lifestyle:
        d["lifestyle"] = persona.lifestyle
    if persona.persona_narrative:
        d["persona_narrative"] = persona.persona_narrative
    if persona.reasoning_prompt and persona.reasoning_prompt != persona.system_prompt:
        d["reasoning_prompt"] = persona.reasoning_prompt
    return d


def panel_summary(personas: list[Persona]) -> dict:
    """Quick summary stats for a generated panel."""
    ages = [p.age for p in personas]
    gender_counts = {}
    region_counts = {}
    income_counts = {}

    for p in personas:
        gender_counts[p.gender] = gender_counts.get(p.gender, 0) + 1
        region_counts[p.region] = region_counts.get(p.region, 0) + 1
        if p.income:
            income_counts[p.income] = income_counts.get(p.income, 0) + 1

    summary = {
        "panel_size": len(personas),
        "tier": "rich" if personas and personas[0].persona_narrative else "basic",
        "age_min": min(ages),
        "age_max": max(ages),
        "age_mean": round(sum(ages) / len(ages), 1),
        "gender": gender_counts,
        "region": region_counts,
        "income": income_counts if income_counts else None,
    }

    # Lifestyle dimension summaries (if Tier 2)
    if personas and personas[0].lifestyle:
        lifestyle_summary = {}
        for dim_name in personas[0].lifestyle.keys():
            counts = {}
            for p in personas:
                val = p.lifestyle.get(dim_name, "unknown")
                # Use short label (before the em dash) for readability
                short = val.split("—")[0].strip() if "—" in val else val
                counts[short] = counts.get(short, 0) + 1
            lifestyle_summary[dim_name] = counts
        summary["lifestyle"] = lifestyle_summary

    return summary
