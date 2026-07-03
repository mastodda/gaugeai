# Consumer Research Project — Upgrade Plan for SE/FDE Positioning

**Purpose:** Convert the existing persona/Likert pipeline into a portfolio artifact that demonstrates production RAG, evals, agentic orchestration, observability, and a working demo. Targets Solutions Engineer roles primarily, Forward Deployed Engineer secondarily. One project covers both.

**Time horizon:** ~6 weeks at 12+ hrs/week.

---

## Priority Order (by ROI)

Build in this sequence. Each layer should be working before the next is started.

1. RAG grounding layer
2. Eval harness (the differentiator — do not skip or rush)
3. Agentic workflow via LangGraph
4. Demo UI (SE-critical)
5. Multi-model comparison
6. Observability + agent traces
7. Guardrails (PII + prompt injection)
8. Commercial framing for resume + narrative

---

## 1. RAG Grounding Layer

**What:** Replace pure-prompt persona generation with retrieval-grounded persona context. Personas reference real consumer signal, not just LLM imagination.

**Why it matters:** "Production RAG" is the single most common phrase in SE/FDE job descriptions. Without it, the project reads as prompt engineering. With it, the project reads as a production AI system.

**Implementation:**
- Corpus sources: public product reviews, Reddit threads, earnings call transcripts, public survey microdata (e.g., GSS, Pew datasets), retail review dumps.
- Pipeline: ingestion → chunking → embeddings (reuse and extend existing semantic-similarity work) → vector store (start with FAISS or Chroma locally, mention pgvector/Pinecone as production path) → retrieval + reranking (cross-encoder).
- Inject retrieved context into persona prompts with explicit citations back to source.
- Log retrieval hits per persona for the trace viewer (layer 6).

---

## 2. Eval Harness — The Differentiator

**What:** Systematic evaluation of synthetic responses against real human survey data. Detects calibration error, distribution drift, demographic representation gaps, and positivity-bias delta.

**Why it matters:** Eval engineering is the 2026 non-negotiable. Most candidates skip it. The existing embedding + Likert-mapping work already gives the scoring machinery — this is the shortest bridge in the project to the highest-value skill.

**Implementation:**
- **Golden dataset:** hold out a real consumer survey (public datasets exist — Pew, ANES, retail review benchmarks).
- **Metrics:**
  - Calibration error (synthetic Likert distribution vs. human Likert distribution per question)
  - Distribution divergence (KL or Wasserstein)
  - Positivity-bias delta (mean shift between synthetic and human)
  - Demographic representation fidelity (subgroup-level distributions, not just overall)
  - Optional: semantic faithfulness — does synthetic free-text response align with the retrieved persona context (use existing embedding pipeline).
- **Pass/fail rubrics** per metric with explicit thresholds.
- **Regression suite:** every change to personas/prompts/retrieval re-runs the suite; fail the build on regression beyond threshold.
- **Output:** an eval report (HTML or markdown) with charts. Make this the headline artifact of the project.

---

## 3. Agentic Workflow via LangGraph

**What:** Restructure the pipeline as a multi-step agent graph rather than a linear script.

**Why it matters:** Named framework on the resume hits keyword screens. Demonstrates agentic orchestration — the second-most-cited 2026 skill after evals.

**Implementation:**
- Nodes:
  - Research planner (decomposes product into question set)
  - Persona generator (RAG-grounded)
  - Interviewer (asks persona the question set, multi-turn)
  - Response analyzer (free-text → Likert via existing pipeline)
  - Report writer (synthesizes results)
- Tool-calling: "fetch demographic stats," "pull product reviews on demand," "query competitive product specs."
- State management via LangGraph's persistent state — useful talking point.

---

## 4. Demo UI — SE-Critical

**What:** Web interface where someone enters a product and gets synthetic responses + Likert distributions + citations + benchmark comparison.

**Why it matters:** SE interviews increasingly ask "show me what you built." A live URL beats a GitHub README by 10x. This is the artifact that closes interviews.

**Implementation:**
- Stack: Streamlit for speed, or Next.js + a simple FastAPI backend if frontend polish matters. Either is fine — pick Streamlit if rusty on React.
- Required surfaces:
  - Product input box
  - Live agent trace (showing layer 6 in action — major impressiveness multiplier)
  - Results: Likert distributions per question with confidence intervals
  - Citation panel: which corpus chunks grounded which persona
  - Eval scorecard: how trustworthy is this output (links to layer 2 metrics)
  - Side-by-side: model A vs. model B (layer 5)
- Deploy: Vercel/Render/Fly.io with a real URL. Put the URL on the resume.

---

## 5. Multi-Model Comparison

**What:** Run the same persona/question set across Claude, GPT, and Gemini; compare calibration.

**Why it matters:** Model-agnostic positioning is a natural SE interview talking point. Shows commercial maturity (not religious about a single vendor).

**Implementation:**
- Abstract a model interface (`generate(prompt) -> response`) with three concrete implementations.
- Re-run the eval harness per model; produce a comparison table.
- Document observed differences (one model more positivity-biased, another better at minority demographic representation, etc.).
- Talking point for interviews: "Claude was best at X, GPT at Y, here's how I'd recommend a customer choose."

---

## 6. Observability + Agent Traces

**What:** Log every agent step, prompt version, retrieval hit, tool call. Simple trace viewer.

**Why it matters:** "Debug agent traces" appears in nearly every FDE job description. Shows production-minded thinking.

**Implementation:**
- Use LangSmith if comfortable with the dependency; otherwise roll a simple structured-log + SQLite + trace viewer page in the demo UI.
- Each persona run produces a trace ID; trace viewer shows the full DAG of nodes, inputs, outputs, retrieval hits, model calls, latency, token usage.
- Bonus: log cost per persona run. Commercial framing gold.

---

## 7. Guardrails

**What:** PII redaction on ingested corpora; prompt-injection defenses on any user input.

**Why it matters:** Hits the exact phrasing in AI job descriptions: "identifying privacy leaks, authority escalation, indirect prompt injection vulnerabilities." Cheap to add, disproportionately credible.

**Implementation:**
- PII: Microsoft Presidio or a regex+NER pass before ingestion. Document what it catches.
- Prompt injection: input validation, instruction hierarchy, output classifier checking for jailbreak patterns. Include a small test suite of adversarial inputs.
- Document the limits — don't oversell. "Catches X, doesn't catch Y, here's how I'd extend it in production."

---

## 8. Commercial Framing

**What:** Resume bullets and demo narrative that quantify business value.

**Why it matters:** SE screens specifically for commercial instinct on top of technical depth. Pure-engineering framing leaves money on the table.

**Implementation:**
- Quantify cost: "Replaces $X/survey traditional research with $Y/run synthetic exploration."
- Quantify time: "Weeks-to-hours iteration cycle for product hypotheses."
- Use case framing: where it works (directional signal, low-cost early exploration, hypothesis prioritization) vs. where it doesn't (final go/no-go calls, regulated-claim substantiation). Honesty here is credibility.
- Pitch a customer profile: "Best fit for early-stage CPG / DTC brands testing concepts pre-launch."

---

## Resume Bullet Templates (Post-Upgrade)

Replace the current project bullets with these patterns once the work lands:

- Built production RAG pipeline grounding LLM-generated consumer personas in [N] public review/survey datasets; reduced positivity bias by [X]% vs. baseline prompting.
- Designed eval harness measuring calibration error, distribution divergence, and demographic fidelity against held-out human survey data ([N] questions); regression suite blocks deploys exceeding [X]% drift.
- Orchestrated multi-step agent workflow via LangGraph (planner → persona → interviewer → analyzer → reporter) with tool-calling for live demographic and review data.
- Deployed [demo URL] with live agent trace viewer, multi-model comparison (Claude / GPT / Gemini), and PII/prompt-injection guardrails.
- Cut consumer research iteration cycle from [weeks] to [hours] at [$X/run] vs. [$Y] for traditional methods.

---

## Repositioning Question — Read This Before Starting

Synthetic consumer research is substantively contested in market research circles. In an SE interview, a sharp interviewer will probe whether the output is actually trustworthy. Have crisp answers for:

1. Where it works (directional signal, low-cost exploration, hypothesis prioritization).
2. Where it does not work (final go/no-go decisions, regulated claims, novel categories with no review data).
3. How the eval harness *measures* the gap rather than papering over it.

If those answers feel shaky, **consider repositioning the same RAG + eval + agent machinery to a more defensible use case before sinking 6 weeks in.** Same skills demonstrated, more defensible commercial value:

- **Competitive intel synthesizer** over public filings, earnings calls, product launches. Agent retrieves, summarizes, alerts on changes.
- **Research synthesis tool** over real consumer review corpora — extracts themes, surfaces contradictions, generates briefs. Real consumer data, no synthetic-data validity debate.
- **Regulated-domain Q&A agent** (healthcare compliance, DoD STIG, FDA labeling) — leverages your Deloitte regulated-environment moat directly.

The technical work is identical. The interview defense is much easier. Decide before week 1.

---

## SE vs. FDE Weighting

If the SE bias holds:
- Prioritize: demo UI polish, multi-model comparison, commercial framing, narrative.
- Lighter on: deep observability internals, advanced guardrail engineering.

If FDE comes back into focus:
- Prioritize: eval rigor, agent traces, guardrails, deployment to real infra.
- Lighter on: UI polish, multi-model commercial story.

One scoping rule: do not fork the project for SE vs. FDE. Build the union; emphasize different layers per audience in the resume and demo walkthrough.

---

## Rough 6-Week Plan (12+ hrs/week, AI-assisted)

- **Week 1:** RAG grounding layer working end-to-end. Baseline persona generation grounded in retrieved context. No quality optimization yet.
- **Week 2:** Eval harness v1. Hold-out dataset selected, top 3 metrics implemented, first calibration numbers in hand. (If the numbers are bad, that is a *feature* — story becomes "I measured it and here's how I'm closing the gap.")
- **Week 3:** Restructure as LangGraph agent. Trace logging stubbed.
- **Week 4:** Demo UI v1 deployed to a public URL. Trace viewer live. Multi-model comparison added.
- **Week 5:** Guardrails layer + observability polish. Begin reframing resume bullets. Start applying to top-tier targets.
- **Week 6:** Project README as a mini case study (problem, approach, eval results, demo link, limitations, future work). Unassisted-coding interview reps begin.

---

## Open Questions to Resolve Early

- Repositioning: stick with consumer research or pivot the use case? Decide by end of week 1.
- Vector store: local FAISS/Chroma is fine for demo; do not over-invest in production infra unless it teaches something new.
- Hosting budget: ~$20-50/mo for demo deployment + LLM API costs during eval runs. Budget for it.
- Public corpora licensing: confirm review datasets are usable for a public demo (some scraped data has TOS issues — choose openly-licensed sources where possible).
