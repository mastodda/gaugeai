# Consumer Research AI — Portfolio Polish Plan

## Context

You have a fully functional product:
- End-to-end pipeline running synthetic consumer surveys via LLM personas
- Streamlit launcher with test configuration (Likert + Tier 2 qualitative)
- PDF and PPTX export of generated test results
- Public-facing site at milesstoddart.com with pilot test signup
- One validation run: 5 product concepts, 33 human respondents from Instagram, +1 Likert bias detected, 100% rank-order accuracy on purchase intent

**What's missing for portfolio purposes:**
- Public GitHub repo
- Formal evaluation framework (your validation work exists but isn't codified as runnable tests)
- More validation runs (one is a stroke of luck; three is a pattern)
- Production-flavored engineering signals (structured logging, retry, cost tracking)
- A public technical write-up that puts the methodology in front of hiring managers

## Goal

Move from "private working software with a marketing site" to "publicly visible technical artifact that signals senior AI engineering capability." 

**Hard finish line: 4 weeks from start. Public repo, formal eval suite, two more validation runs, one published technical write-up.**

## Skills This Project Demonstrates

| Skill | How it shows up |
|-------|-----------------|
| Agentic systems | Multi-persona ensemble with sampling configurations |
| Evaluation methodology | Empirical validation against human baseline + bias correction from peer-reviewed methods |
| Structured outputs | Likert distributions via embedding similarity, not raw LLM scoring |
| Production engineering | Cost/latency tracking, retry, deployment, demo UI |
| Research literacy | Implementing methods from peer-reviewed studies |

The eval methodology and the bias correction work are your differentiators. Lead with them everywhere.

---

## Week 1: Repository + README

**Objective:** GitHub repo public, README that sells the work.

### Tasks

**Repo hygiene**
- Create new public GitHub repo (or split an existing private one). Audit for any committed secrets — rewrite history if needed.
- Restructure to: `src/`, `evals/`, `tests/`, `docs/`, `notebooks/` (notebooks for exploration only)
- Pin dependencies in `pyproject.toml` or `requirements.txt`
- `.env.example` with all variables documented; real `.env` gitignored
- Pre-commit hooks: `ruff` for linting, `black` for formatting, `mypy` strict mode on core modules
- Strip dead code, debug prints, commented blocks
- Add LICENSE (MIT is standard for portfolio projects)

**README structure** (this is the most-read artifact in your portfolio)
1. **One-line description** — what it is, in plain language
2. **The problem** (2 paragraphs) — synthetic consumer data, why current approaches are limited, why this matters
3. **Architecture diagram** — Excalidraw or Mermaid. Show: input → persona generation → ensemble responses → embedding-based scoring → bias correction → output
4. **Key design decisions** — for each non-obvious choice, write the tradeoff. Examples to cover:
   - Why ensembles instead of single-shot persona responses
   - Why embedding-based Likert mapping instead of asking the LLM to output a number directly
   - Why these specific persona dimensions
   - How sampling configurations affect output diversity
5. **Evaluation methodology** — your differentiator. Walk through the validation methodology, the +1 bias finding, the 100% rank-order accuracy result. Include the actual numbers.
6. **Quickstart** — clone, install, run, get a result in under 5 minutes. Test this with a fresh user (a friend, your dad, anyone).
7. **Limitations** — what doesn't work, what's untested, what would break at scale
8. **Future work** — pointers to what you'd build next

### Acceptance Criteria

- [ ] Repo is public on GitHub with no committed secrets
- [ ] `README.md` includes all 8 sections above
- [ ] Architecture diagram is embedded as image, not text
- [ ] Quickstart works on a fresh clone in under 5 minutes (verified by someone other than you)
- [ ] Pre-commit hooks pass on every file
- [ ] Repo has a LICENSE, `.gitignore`, `.env.example`, and pinned dependencies

**Time estimate: 12-15 hours**

---

## Week 2: Formalize Evaluation as Code

**Objective:** Your validation work becomes a runnable test suite, not a one-off experiment.

### Tasks

**Eval harness**
- Create `evals/` directory with structure: `evals/datasets/`, `evals/runners/`, `evals/reports/`
- Codify the existing 5-product / 33-respondent validation as a reproducible eval. Store the human baseline data (anonymized) in `evals/datasets/instagram_validation_v1.json`
- Build a runner: `python -m evals.run --dataset instagram_validation_v1` produces a Markdown report with:
  - Mean Likert bias per product
  - Distribution overlap (e.g., Wasserstein distance) between synthetic and human
  - Rank-order accuracy
  - Token cost and latency for the run
- Add regression tests via pytest: `tests/test_eval_regression.py` runs a small held-out subset and fails if metrics drop below configured thresholds

**Bias correction validation**
- Implement the bias correction methods you cited from peer-reviewed studies as a separate module: `src/correction/`
- Run before/after comparison on the validation dataset
- Document the delta in the eval report

**Cost/latency observability**
- Track token usage per run (input tokens, output tokens, cost in USD, by model)
- Track latency per persona, per ensemble, per total run
- Surface these in the eval report and in the Streamlit launcher

### Acceptance Criteria

- [ ] `python -m evals.run --dataset instagram_validation_v1` produces a report with bias, distribution overlap, rank-order accuracy, cost, and latency
- [ ] Pytest regression tests fail when key metrics regress beyond configured thresholds
- [ ] Bias correction module is independently runnable and shows measurable improvement on validation data
- [ ] Cost tracking is accurate to within 1% of actual API billing
- [ ] Streamlit launcher displays cost and latency for each completed test run

**Time estimate: 15-20 hours**

---

## Week 3: Two More Validation Runs + Production Polish

**Objective:** Three validation runs total, plus the production engineering details that signal seniority.

### Tasks

**Validation runs (this is the work that takes calendar time, plan accordingly)**
- Run 2: Different product category (services or B2B if Run 1 was consumer goods, or vice versa). Target 30+ human respondents. Choose products where you have access to honest feedback (network, online communities, Mechanical Turk if budget allows ~$50-100).
- Run 3: Different demographic skew. If Run 1 was your IG followers (likely younger, tech-adjacent), aim for a different cohort. Even 20-30 respondents is meaningful.
- Each run goes into `evals/datasets/` as a separate dataset. Run all three through the eval harness and produce a comparison report.
- Document failure modes: where does the system disagree most with humans? What persona configurations work better/worse for which product types?

**Production engineering**
- Structured logging with `structlog` — JSON logs in production, pretty-printed in dev
- Retry logic on all LLM calls using `tenacity` (exponential backoff, max retries configured per provider)
- Caching layer for development: `diskcache` or SQLite-based cache on prompt hashes so you don't re-pay for identical calls during iteration
- Provider abstraction via `litellm` so swapping models is a config change, not a code change
- Configuration via Pydantic settings, not loose dicts or environment variable sprawl

### Acceptance Criteria

- [ ] Three independent validation datasets exist in `evals/datasets/`
- [ ] Comparison report (`evals/reports/three_run_comparison.md`) shows results across all three with discussion of where the system performs well vs. poorly
- [ ] Logs are structured JSON in production mode, viewable as pretty output in dev mode
- [ ] All LLM calls retry on transient failures with exponential backoff
- [ ] Development cache reduces API costs on repeated runs by >80%
- [ ] Switching from Anthropic to OpenAI requires only a config change, no code changes

**Time estimate: 18-25 hours (gated by recruitment time for human respondents — start Week 2 if possible)**

---

## Week 4: Write-Up + Launch

**Objective:** The world sees this and you start getting inbound interest.

### Tasks

**Technical write-up**
- One blog post, 1500-2500 words, focused on the bias correction methodology. Title direction: "Synthetic consumer research is +1 biased — here's how to fix it" or similar.
- Structure:
  1. The problem (synthetic respondents systematically over-report purchase intent)
  2. The literature (cite the peer-reviewed methods, briefly)
  3. Your implementation (architecture, key choices)
  4. Validation methodology (three runs, what they showed)
  5. The bias correction results (before/after numbers)
  6. What's still broken
- Host options (rank-ordered by signal strength): personal site, Substack, dev.to, Medium. Personal site is best because it lives next to your portfolio.
- Cross-post a thread version to X/Twitter and LinkedIn

**Demo polish**
- Your milesstoddart.com site already exists — link the GitHub repo and the blog post prominently from it
- Add an "Architecture & Methodology" page that mirrors the README's design decisions section
- Make sure the demo flow is smooth: someone lands on the site, understands what the tool does in 30 seconds, can either request a pilot or click through to the GitHub repo

**Outreach kickoff (this is the work most people skip)**
- Build a target list of 25 AI Engineering hiring managers at companies you'd want to work for
- For 10 of them, draft a personalized cold email that opens with one specific thing about their work or company, mentions the project with a link, and proposes a 15-minute conversation. No mass templates.
- Send the first 5 by end of Week 4

### Acceptance Criteria

- [ ] Blog post is published at a public URL
- [ ] Twitter/LinkedIn post links the blog post and the repo, with at least one architecture image or chart
- [ ] milesstoddart.com prominently links both the GitHub repo and the blog post
- [ ] Target hiring manager list (25 names, with company, role, and one specific reference) is built
- [ ] 5 cold emails are sent

**Time estimate: 10-15 hours**

---

## Definition of Done (Project Level)

When all of the following are true, this project is portfolio-ready and you stop polishing:

1. Public GitHub repo with strong README, architecture diagram, working quickstart
2. Eval harness runnable from CLI, three validation datasets, comparison report
3. Production engineering: structured logs, retries, provider abstraction, cost tracking
4. Public blog post with the bias correction methodology
5. Personal site links the repo and the post
6. Cold outreach kickoff: 5 emails sent

**After this point: stop polishing. Move to the email agent. You can always come back, but the next project starts now.**

---

## Anti-Scope-Creep Rules

- No new features. The product as it exists is feature-complete for portfolio purposes.
- No UI redesigns. milesstoddart.com is good enough.
- If a validation run shows the system is broken in some new way, document it in "Limitations" — do NOT pause to fix it.
- If you find yourself "just cleaning up one more thing" past the Week 4 deadline, ship as-is and move on.

---

## Total Time Budget

55-75 hours over 4 weeks. ~14-19 hours/week. If you fall behind, cut the third validation run before cutting the write-up — the write-up is what hiring managers actually see.
