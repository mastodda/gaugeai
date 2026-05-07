---
project_name: 'GaugeAI'
user_name: 'Miles'
date: '2026-05-07'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'code_quality', 'critical_rules']
status: 'complete'
rule_count: 43
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

**Runtime**: Python 3.10+ — use `str | None` unions and `list[T]` / `dict[K, V]` generics (not `Optional`, `List`, `Dict`)

**Critical dependency rules** (no root-level requirements.txt — install manually):

| Package | Rule |
|---------|------|
| `openai>=1.0` | v1.x SDK only — uses `from openai import OpenAI` (v0.x API is incompatible) |
| `google-generativeai` | Install this package, NOT `google-genai` (different SDK, different imports) |
| `Pillow` | Hidden dep — not in any requirements.txt but required at runtime for Gemini image uploads |
| `openai` | **Always required**, even for Gemini/Claude-only runs (embeddings + insights both use OpenAI) |

**Environment variables** (loaded at runtime — agents must not read credential files):
- `OPENAI_API_KEY` — always required
- `GOOGLE_API_KEY` — Gemini runs
- `ANTHROPIC_API_KEY` — Claude runs

**Explorer** (`explorer/`): dependencies in `explorer/requirements.txt`; `pandas<3.0.0` upper bound is enforced (3.x breaking changes). Run `npm install` inside `explorer/` (not project root) for PowerPoint export.

**Model hardcoding**:
- Insights: always `gpt-4o-mini` in `core/insights_generator.py` regardless of main provider — skip with `--mode paper` or `skip_insights=True`
- Embedding: always `text-embedding-3-small` (OpenAI)

## Critical Implementation Rules

### Language-Specific Rules

**Lazy imports — mandatory for API clients**
Never import `EmbeddingClient`, `create_llm_client`, or any provider SDK (`openai`, `google.generativeai`, `anthropic`) at module level. Import them inside function bodies. This keeps dry-run and config loading lightweight and import-error-free when optional packages aren't installed.

```python
# Correct — inside run_pipeline()
from core.embedding_client import EmbeddingClient
from core.llm_client import create_llm_client

# Wrong — at module top
from core.embedding_client import EmbeddingClient  # breaks dry-run
```

**`pathlib.Path` everywhere**
All file paths use `Path` objects internally. Function signatures accept `str | Path`; convert at entry with `Path(x)`. Never use raw strings for file I/O.

**`@dataclass` for domain objects**
New domain objects must be `@dataclass` — not plain dicts, namedtuples, or classes. Existing dataclasses: `PipelineConfig`, `Persona`, `DemographicSpec`, `SSRResult`, `ReferenceSet`.

**Seeded randomness — never use global `random`**
All random sampling must go through `random.Random(seed)` (an instance), not `random.choice()` / `random.randint()` at module level. This ensures reproducible panel generation.

**Progress display pattern**
In-loop progress uses carriage-return style — not `print()`. Call `print()` after the loop for the newline:
```python
sys.stdout.write(f"\r{prefix}: {current}/{total} ({pct:.0f}%)")
sys.stdout.flush()
# after loop:
print()
```

**No comments except for non-obvious WHY**
Do not add docstrings or inline comments explaining what code does. Only add a comment when the reasoning would surprise a reader (a workaround, hidden constraint, or non-obvious invariant).

### Framework & Architecture Rules

**LLM provider pattern — extend via ABC, not conditionals**
All LLM providers implement `LLMClient(ABC)` with a single `elicit_response()` method. Adding a new provider means a new subclass + one entry to the `create_llm_client()` factory dict in `core/llm_client.py` — the single permitted place for provider routing. Never add provider conditionals anywhere else.

**SSR scoring is embedding-in, PMF-out — keep it pure**
`core/ssr_scoring.py` takes pre-computed `np.ndarray` as input and does no I/O. All embedding calls flow through `EmbeddingClient.embed()`. Orchestration belongs in `pipeline.py`. Do not add API calls or file I/O to `ssr_scoring.py`.

**JSON key type mismatch — Likert ratings**
Reference set anchor keys are strings in JSON (`"1"`…`"5"`) but integers in Python. Always cast on load:
```python
anchors = {int(k): v for k, v in set_data["anchors"].items()}
```
When writing PMFs/similarities to JSON, convert back:
```python
{"averaged_pmf": {str(r): round(p, 6) for r, p in result.averaged_pmf.items()}}
```
Note: integer-key dicts are silently fine throughout the pipeline but raise `TypeError` at `json.dumps()` — only at Step 5, after all API calls. Test serialization early on any new non-string-keyed dict.

**New `SSRResult` fields must be explicitly serialized**
`@dataclass` fields are not auto-serialized. Any new field on `SSRResult` must be explicitly added to `result_to_dict()` in `ssr_scoring.py` — omitting it silently drops the field from `results.json` with no error. See the `reasoning_response` guard as the pattern for optional fields.

**Three places must change atomically for new pipeline parameters**
Adding a parameter to `PipelineConfig` requires: (1) the dataclass field, (2) the `pipeline` block in the engagement JSON, (3) `load_pipeline_config()` to wire the JSON value into the dataclass. Missing any one silently uses the hardcoded default.

**Two-stage elicitation — Stage 2 is qualitative only**
Stage 1 (free-text → SSR scoring) produces the Likert PMF. Stage 2 (reasoning follow-up) produces qualitative text stored in `SSRResult.reasoning_response` — never scored. Do not pipe Stage 2 output through `compute_pmf()`.

**Explorer reads a fixed JSON schema — don't add unplanned keys**
`explorer/app.py` reads specific known keys from `results.json` respondent records. Adding new fields to respondent output requires a matching update in the explorer.

**Engagement config is the single source of truth**
All pipeline parameters come from the engagement JSON. Do not hardcode pipeline parameters anywhere else.

**Embedding cache is per-run, not global**
Cache lives at `{output_dir}/.cache/embeddings/`. Each new timestamped run starts empty — reference anchors are re-embedded on every fresh run. To reuse embeddings, reuse the same `--output` directory.

### Testing Rules

**Test location — co-located, not a separate directory**
Tests live in `core/test_*.py` alongside the source. No `tests/` directory. New tests for `core/foo.py` go in `core/test_foo.py`.

**Run tests per-file, not with `pytest .`**
No pytest config file exists. Always run tests explicitly:
```bash
python -m pytest core/test_ssr_scoring.py -v
python -m pytest core/test_persona_generator.py -v
```
Running `pytest .` will also discover BMad scripts and other non-test Python files.

**Unit tests use synthetic embeddings — no API calls**
`test_ssr_scoring.py` uses `make_fake_embeddings()` to simulate real embedding geometry without hitting OpenAI. New unit tests for scoring/math logic must follow this pattern — construct synthetic `np.ndarray` inputs, never call `EmbeddingClient`.

**Integration tests require API keys**
`test_integration.py` makes real API calls. Run explicitly and only when keys are available:
```bash
python -m pytest test_integration.py -v
```

**Explorer validation is separate**
Explorer data loading is validated via `python explorer/test_explorer.py` — not pytest. Run this after any change to `explorer/app.py` or the output JSON schema.

**Test the serialization boundary**
Any test for a new `SSRResult` or `Persona` field must assert the field appears correctly in `result_to_dict()` / `persona_to_dict()` output — silent omission is the most common failure.

**New `LLMClient` implementations must cover the interface contract**
Any new provider subclass requires tests for: (1) text-only input (`concept_image_path=None`), (2) image + text input, (3) return value is a non-empty stripped string.

**Determinism test required when modifying `persona_generator.py`**
Assert that the same `seed` + `DemographicSpec` produces the same first persona (age, gender, region) across two calls. Catches accidental `rng` consumption order changes.

**Test `compute_pmf()` with both `epsilon=0.0` and `epsilon > 0`**
The two epsilon paths have distinct logic. Any modification to `compute_pmf()` must be verified against both cases.

**`lifestyle_attributes.json` dimensions must match prompt template placeholders**
No automated test catches this. After adding a dimension, manually verify every dimension key appears in `user_message_template` in the same file before running the pipeline.

**Dry-run is the smoke test for lazy import discipline**
After any change to `core/pipeline.py` or `run_pipeline.py`, run:
```bash
python run_pipeline.py config/example_engagement.json --dry-run
```
Validates that no top-level API imports were accidentally introduced.

### Code Quality & Style Rules

**No linter or formatter configured**
No `pyproject.toml`, `mypy.ini`, or formatter config exists. Do not introduce Black, Ruff, mypy, or similar tooling unless explicitly asked.

**Function signatures accept `str | Path`, convert internally**
Public functions taking file paths accept `str | Path`; convert with `Path(x)` at the top of the body. Do not accept only `str` or only `Path`.

**No module-level caches or singletons**
Do not add module-level mutable variables (caches, registries, config objects). All state lives in dataclass instances passed through function arguments. The temptation is adding a module-level embedding cache for convenience — don't.

**Error handling: catch at the elicitation loop only**
The per-persona `try/except` in `pipeline.py`'s elicitation loop is intentional — a single bad API response should not abort a 100-persona run. Do not add broad `try/except` blocks inside `ssr_scoring.py` or `persona_generator.py`. Only catch at the loop level in `pipeline.py`.

**Output rounding is fixed — do not change**
- PMF values and similarity scores: `round(x, 6)`
- Expected ratings and distribution aggregates: `round(x, 4)`
Downstream tooling depends on this precision.

**`_meta` block is display-only**
`_meta` in engagement JSON is for human display (name, client, analyst). Pipeline reads from `pipeline`, `demographics`, `concepts`, and `survey_question` only. Never put pipeline parameters in `_meta`.

**`persona_id` format is load-bearing**
Always use `f"resp_{i:04d}"` for persona IDs. This format is used as a dict key in output JSON and referenced by the explorer. Do not use alternative formats in new persona generation code.

**`concept_id` is a slug, not a display name**
`concept_id` is used as a Python dict key and appears verbatim in `results.json`. Use slugs only (`concept_a`, `concept_b`). Display names go in the optional `name` field, accessed throughout via `concept.get("name", concept_id)`.

**Image paths resolve relative to the engagement file**
`pipeline.py` resolves image paths as `config.engagement_path.parent / img_path`. Any new code reading `concept["image_path"]` must use the same resolution — not `Path(img_path)` from the working directory.

**Use `print()` not `logging`**
The pipeline uses `print()` directly for all user-facing output. Do not introduce `import logging` — it suppresses output in ways inconsistent with the existing UX.

### Critical Don't-Miss Rules

**SSR is a probability distribution method — never collapse to a single score prematurely**
The pipeline produces a full PMF `{1: p, 2: p, 3: p, 4: p, 5: p}` per respondent. `expected_rating` and `mode_rating` are derived summaries, not the primary output. New analytics features must operate on the full PMF — not just `expected_rating`. Collapsing to a mean too early discards the distributional signal that makes SSR valuable.

**Tier 2 personas require both `lifestyle_config_path` AND `llm_client`**
`use_rich = lifestyle_config is not None and llm_client is not None`. If either is missing, the pipeline silently falls back to Tier 1 with no warning. An agent wiring up Tier 2 must ensure both are passed to `generate_panel()`.

**`samples_per_persona` averaging happens in `pipeline.py`, not `ssr_scoring.py`**
When `samples_per_persona > 1`, the pipeline calls `score_respondent()` multiple times and averages the PMFs in `pipeline.py`. `ssr_scoring.py` scores a single response — it has no concept of samples. Do not add multi-sample logic to `ssr_scoring.py`.

**`scoring_persona_tier` is independent of the persona generation tier**
`scoring_persona_tier=1` uses the clean demographic prompt for SSR scoring elicitation even when Tier 2 personas are generated — the rich narrative is reserved for Stage 2 reasoning only. These are separate concerns: persona richness vs. which prompt drives scoring.

**`apply_mode()` overrides individual flags — call it first**
`apply_mode(config, "paper")` sets `lifestyle_config_path=None`, `skip_stage_2=True`, `skip_insights=True` — overriding whatever was loaded from the engagement JSON. Always call `apply_mode()` before any flag customization, never after.

**The pipeline is not idempotent on the same output directory**
Reusing an output directory reruns the full pipeline and overwrites `results.json`, `summary.json`, `personas.json`, `insights.json`. Only the embedding cache (`.cache/`) is safely reused. Do not assume partial results are preserved on a rerun.

**Concept image paths can be `null` — always use `.get()` with a None check**
`concept["image_path"]` may be `null` / `None`. All image-related code uses `concept.get("image_path")` and guards with `if img_path and Path(img_path).exists()`. Never pass `concept["image_path"]` to an API without a None check.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — many failures are silent (no exception, wrong output)
- When in doubt about a pattern, look at the existing implementation first; this codebase is internally consistent
- Do not read credential files (`.env`) under any circumstances

**For Humans:**
- Keep this file lean — only rules that prevent real mistakes belong here
- Update when the technology stack changes (new provider, new model, schema changes)
- Review after any significant refactor to remove rules that are now enforced by code structure

_Last updated: 2026-05-07_
