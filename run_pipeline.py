#!/usr/bin/env python3
"""
run_pipeline.py — CLI entry point for the SSR pipeline.

Usage:
    python run_pipeline.py config/example_engagement.json
    python run_pipeline.py config/example_engagement.json --output output/my_run
    python run_pipeline.py config/example_engagement.json --dry-run
"""

import argparse
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.pipeline import load_pipeline_config, run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Run SSR synthetic survey pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py config/example_engagement.json
  python run_pipeline.py config/example_engagement.json --output output/test_run
  python run_pipeline.py config/example_engagement.json --dry-run

The --dry-run flag validates config and generates personas without making
any API calls. Use it to verify your engagement config before spending credits.
        """,
    )
    parser.add_argument(
        "engagement",
        type=str,
        help="Path to engagement config JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output directory (default: output/run_TIMESTAMP)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and generate personas without API calls",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for panel generation (default: random). Logged in output for reproducibility.",
    )

    args = parser.parse_args()

    engagement_path = Path(args.engagement)
    if not engagement_path.exists():
        print(f"Error: Engagement file not found: {engagement_path}")
        sys.exit(1)

    config = load_pipeline_config(engagement_path, output_dir=args.output)

    # Override seed: random by default, or use --seed value
    if args.seed is not None:
        config.seed = args.seed
    else:
        config.seed = random.randint(0, 2**31 - 1)
    print(f"Seed: {config.seed}  (rerun with --seed {config.seed} to reproduce)\n")

    if args.dry_run:
        _dry_run(config)
    else:
        run_pipeline(config)


def _dry_run(config):
    """Validate everything without making API calls."""
    from core.persona_generator import generate_panel, load_demographic_spec, panel_summary
    import json

    print("=" * 60)
    print("SSR PIPELINE — DRY RUN (no API calls)")
    print("=" * 60)

    meta = config.engagement.get("_meta", {})
    print(f"  Engagement: {meta.get('engagement', 'unnamed')}")
    print(f"  Concepts:   {len(config.concepts)}")
    print(f"  Provider:   {config.llm_provider} / {config.llm_model}")
    print()

    # Validate concepts
    print("[1/4] Validating concepts...")
    for c in config.concepts:
        cid = c.get("concept_id", "?")
        has_text = bool(c.get("description"))
        has_image = bool(c.get("image_path"))
        status = "✓" if (has_text or has_image) else "✗ NO STIMULUS"
        print(f"  {cid}: text={'yes' if has_text else 'no'}, "
              f"image={'yes' if has_image else 'no'} {status}")
        # Validate image file exists if specified
        if has_image:
            img_path = Path(c["image_path"])
            if not img_path.is_absolute():
                img_path = config.engagement_path.parent / img_path
            if img_path.exists():
                size_kb = img_path.stat().st_size / 1024
                print(f"    image: {img_path} ({size_kb:.0f} KB) ✓")
            else:
                print(f"    ✗ IMAGE NOT FOUND: {img_path}")
    print()

    # Validate reference sets
    print("[2/4] Validating reference sets...")
    ref_path = config.reference_sets_path
    if ref_path.exists():
        with open(ref_path) as f:
            ref_config = json.load(f)
        sets = ref_config.get("sets", {})
        print(f"  Found {len(sets)} reference sets at {ref_path}")
        for name, data in sets.items():
            n_anchors = len(data.get("anchors", {}))
            status = "✓" if n_anchors == 5 else f"✗ expected 5 anchors, got {n_anchors}"
            print(f"    {name}: {n_anchors} anchors {status}")
    else:
        print(f"  ✗ Reference sets file not found: {ref_path}")
    print()

    # Generate test panel
    print("[3/4] Generating test panel...")
    prompt_template_path = config.engagement_path.parent / "prompt_templates.json"
    if not prompt_template_path.exists():
        print(f"  ✗ Prompt templates not found: {prompt_template_path}")
        return

    spec = load_demographic_spec(config.engagement_path)
    personas = generate_panel(
        spec=spec,
        prompt_template_path=prompt_template_path,
        seed=config.seed,
    )
    summary = panel_summary(personas)
    print(f"  Panel: {summary['panel_size']} respondents")
    print(f"  Age:    {summary['age_min']}-{summary['age_max']} (mean {summary['age_mean']})")
    print(f"  Gender: {summary['gender']}")
    print(f"  Region: {summary['region']}")
    if summary.get("income"):
        print(f"  Income: {summary['income']}")
    print()

    # Show sample prompts
    print("[4/4] Sample system prompts:")
    for p in personas[:3]:
        print(f"  [{p.persona_id}] {p.system_prompt}")
    print(f"  ... ({len(personas) - 3} more)")
    print()

    # Cost estimate
    n_calls = spec.panel_size * config.samples_per_persona * len(config.concepts)
    n_embeddings = n_calls + 30  # responses + 30 anchor embeddings (cached after first run)
    print("=" * 60)
    print("COST ESTIMATE")
    print("=" * 60)
    print(f"  LLM calls:       {n_calls} ({spec.panel_size} personas × "
          f"{config.samples_per_persona} samples × {len(config.concepts)} concepts)")
    print(f"  Embedding calls:  {n_calls} response embeddings + 30 anchors (cached)")
    print(f"  Estimated time:   ~{n_calls * 1.5 / 60:.0f} min at ~1.5s per LLM call")
    print()
    print("  Run without --dry-run to execute.")
    print("=" * 60)


if __name__ == "__main__":
    main()