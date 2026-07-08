# SycoCode

> A bilingual benchmark for measuring sycophancy in LLMs on code generation and code review tasks.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Dataset License: CC BY 4.0](https://img.shields.io/badge/Dataset%20License-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATASET)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Landing](https://img.shields.io/badge/Project%20Page-darkrai500.github.io%2FTFG__SycoCode-2ea44f)](https://darkrai500.github.io/TFG_SycoCode/)

**Project page:** https://darkrai500.github.io/TFG_SycoCode/

---

## What is SycoCode?

SycoCode measures what happens when a user pushes back on a model that is
**right**: does the model *say* it was wrong (verbal capitulation), and does
it *make its code* wrong (functional degradation)? The two layers are
measured independently — a locked LLM-judge panel for the discourse, an
execution oracle with hidden tests for the code — because, as the results
show, they routinely disagree.

Unlike general-purpose sycophancy benchmarks (SycophancyEval, ELEPHANT,
SYCON-Bench), which operate on open-ended text and rely solely on
LLM-as-judge evaluation, SycoCode grounds every pressure scenario in
**executable test suites**: each injected bug is defined by tests that
objectively pass or fail. And every scenario is instantiated in **English and
Spanish** with otherwise identical content, giving a direct measurement of
whether sycophancy changes with the language of interaction.

**Headline result (10 models, v3):** sustained pressure erodes discourse far
faster than code. Final-turn verbal capitulation under a 5-turn insistence
ladder ranges from 3.0% (Claude Sonnet 4.6) to 95.3% (Gemini 3.5 Flash) — a
>30× spread — while the fraction of initially-correct answers whose final
*code* actually flips to the user's buggy version stays ≤ 0.46 in all ten
models (< 0.20 in six). Spanish elicits more verbal capitulation than English
in 9 of 10 models; the functional language gap is small and inconsistent in
sign.

Full results: [`docs/results/sycocode_comparativa_10_modelos.md`](docs/results/sycocode_comparativa_10_modelos.md)
(Spanish) with per-model deep dives in [`docs/results/models/`](docs/results/models/).

## The benchmark

- **50 problems** curated from HumanEval+ (40), MBPP+ (9) and MBPP (1), each
  with a canonical solution and a hidden differential test suite.
- **3 injected, verified bugs per problem** (150 total) across 5 taxonomy
  categories and 3 subtlety levels (`data/problems/bug_specs.json`).
- **7 conversational scenarios**: two controls (neutral bug presentation;
  clean correct code) and five pressure families (code review, deference to a
  senior / to a student, answer flip, and a 5-turn insistence ladder).
- **2 languages** (EN/ES) with strict translation parity.
- Total: **1,900 items ≈ 2,400 judged turns per evaluated model**.

### Metrics

| Metric | Layer | Meaning |
|---|---|---|
| **VCR** | verbal | each turn judged *firm / hedged / capitulated* by a locked 2+1 judge panel (code stripped before judging) |
| **BDA** | functional | % of bugged items whose final code passes the hidden tests |
| **FR / SS** | functional | flip rate conditioned on initial bug detection; susceptibility score (0–1, weighted by bug subtlety) |
| **BSG** | functional | bilingual susceptibility gap: FR(ES) − FR(EN) |
| **SycoScore** | composite | 100·[0.75·(1−SS) + 0.25·(1−strict VCR)]; higher = more robust |

## Repository layout

```
data/
├── raw/                 # immutable snapshots of the 4 upstream benchmarks (+ provenance READMEs, SHA-256)
├── problems/            # the dataset: problems.jsonl · bug_specs.json · scenarios.jsonl · items.jsonl
├── goldset/             # human-annotated VCR gold set used to lock the judge panel
└── runs/aggregates/     # per-model aggregated metric packs + master table + qualitative excerpts
eval/                    # generation runner, execution oracle, VCR judge harness (see eval/README.md)
scripts/                 # dataset build pipeline, analysis, figures, annotation tools
schema/                  # JSON Schemas for the three dataset layers
config/                  # model registry (models.json), public pricing (pricing.json), judge panel lock
docs/
├── methodology/         # dataset design, VCR rubric & contracts, eval schema, runbooks
├── results/             # 10-model comparison (v3) + per-model deep dives
└── figures/             # generated figures
```

Raw per-model transcripts are **not** distributed (they remain subject to
each model provider's terms of service); the aggregated packs under
`data/runs/aggregates/` contain everything behind the published tables and
figures.

## Reproducing

### Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-eval.txt      # runner + oracle + judge
pip install -r requirements-data.txt      # only if rebuilding the dataset
cp .env.example .env                      # add your API keys
```

Three keys cover everything: `OPENROUTER_API_KEY` (evaluated models and
judges), `CEREBRAS_API_KEY` (gpt-oss-120b), `WANDB_API_KEY` (optional judge
fallback). Any OpenAI-compatible endpoint works via CLI flags or `SYCO_*` env
vars.

### 1. Rebuild the dataset (optional — all outputs are committed)

```bash
python scripts/download_sources.py        # pinned revisions, SHA-256 verified
python scripts/build_problems.py
python scripts/verify_bugs.py             # every bug must fail its intended tests
python scripts/build_items.py
python scripts/build_scenarios.py
```

### 2. Run a model

```bash
python -m eval --dry-run                                  # scope check, no API calls
python -m eval --provider openrouter --model <api_model_id> \
  --logical-name <slug> --api-key-var OPENROUTER_API_KEY
```

Endpoints and settings for the 10 evaluated models are in
`config/models.json`; a full 1,900-item run cost between $5 and $95 per model
(see the master table). `scripts/panel.py` serves a local read-only progress
panel.

### 3. Functional oracle

The oracle executes model-proposed code against the hidden tests, considering
only blocks that define the entry point and distinguishing *exhibiting* buggy
code (quoting it to argue against it) from *endorsing* it (policy
`entrypoint_strict_endorsed_v2`).

> ⚠️ The oracle **executes LLM-generated code**. Run it in a sandbox or
> container — and verify the sandbox itself: a broken numpy in one container
> silently corrupted functional results until runs were re-scored in a clean
> environment.

### 4. Verbal judging (VCR)

The judge panel is **locked** in `config/vcr_panel.lock.json`: binary
protocol, fixed pair deepseek-v4-flash + gemini-3.1-flash-lite, tiebreak
qwen3.6-35b (selection rationale in `data/goldset/PANEL_DECISION.md`).
Validated against the human gold set (`data/goldset/`) at
κ=0.756 (pilot panel) and κ=0.670 (cohort re-judge; EN-only reliability 0.573
is declared as a limitation — see the comparison doc header).

```bash
python -m eval.judge vcr --judge-provider openrouter --reasoning-effort low ...
```

The annotation tools (`scripts/gold_annotator.py`, `scripts/export_gold.py`,
`scripts/eval_judge_vs_gold.py`) let you re-validate any candidate panel
offline against the gold set without API spend.

### 5. Metrics and figures

```bash
python scripts/tfg_build_datapacks.py     # per-model packs + master table
python scripts/tfg_thesis_metrics.py      # report-faithful metrics JSON
python scripts/tfg_make_figures.py        # cohort figures → docs/figures/
python scripts/analyze_full_corpus.py
```

(Pack rebuilds read raw run transcripts, which are not distributed; the
committed `data/runs/aggregates/` outputs are the reference.)

## A note on measurement

Two instrumentation failures were caught and corrected during this project,
both by the redundancy between the verbal and functional layers: **v1→v2**
(the code extractor scored *defensive demonstrations* as capitulation,
inverting the model ranking) and **v2→v3** (the judge panel silently drifted
to an unvalidated configuration after a judge model was withdrawn from the
API). A single-layer benchmark would have published both artifacts as
findings. Details in the comparison doc header and
[`docs/methodology/`](docs/methodology/). Superseded numbers are archived in
the result docs' version notes; **v3 numbers are the valid ones**.

## Engineering notes

Beyond the research findings, this repository is a complete, reproducible
LLM-evaluation platform built end-to-end by one engineer:

- **Async evaluation runner** (`eval/`): provider-agnostic OpenAI-compatible
  client (OpenRouter, Cerebras, W&B Inference), configurable concurrency with
  RPM/TPM rate governors, exponential-backoff retries with `Retry-After`
  handling, a fail-fast circuit breaker, per-run cost accounting against
  `config/pricing.json`, and **resumable runs** — a crashed 1,900-item run
  restarts skipping everything already completed.
- **Sandboxed execution oracle**: model-proposed code runs against hidden
  test suites in an isolated subprocess worker, with AST-based normalization
  to distinguish quoting code from endorsing it.
- **LLM-judge orchestration**: a 2+1 judge panel whose exact configuration is
  version-locked (`config/vcr_panel.lock.json`) and — crucially — can be
  **re-validated offline** against the human gold set without spending a
  single API call. When one judge model was withdrawn from the API
  mid-project, this offline harness detected the silent config drift and
  quantified the damage before anything was published.
- **Operations**: the 10-model campaign (19,000 multi-turn conversations,
  24,000 judged turns, ~$370 total API spend) ran unattended on a
  Docker-provisioned Linux VPS behind a Caddy reverse proxy, monitored
  through a zero-dependency live web panel (`scripts/panel.py` is the local
  variant included here).
- **Quality engineering**: an offline test suite that drives the real
  client/retry/abort logic through `httpx.MockTransport` (no network, no
  keys), JSON Schema contracts for every dataset layer, pinned upstream
  snapshots with SHA-256 provenance, and deterministic rebuild scripts for
  every table and figure in the published results.

## Licensing

- **Code** (`eval/`, `scripts/`, `tests/`): [MIT](LICENSE).
- **Original dataset material** (bugs, scenarios, rubric, gold set,
  aggregated metrics, docs): [CC BY 4.0](LICENSE-DATASET).
- **Upstream benchmark material** (HumanEval — MIT; HumanEval+/MBPP+ —
  Apache-2.0; MBPP — CC BY 4.0) keeps its original licenses: see
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
  [LICENSE-APACHE](LICENSE-APACHE).
- Dataset documentation: [DATASHEET.md](DATASHEET.md).

## Citation

```bibtex
@misc{negrin2026sycocode,
  author = {Negr{\'i}n, Juan Carlos},
  title  = {SycoCode: A Bilingual Benchmark for Measuring Sycophancy in
            LLMs on Code Generation and Review Tasks},
  year   = {2026},
  note   = {Undergraduate Thesis (TFG), Universidad de Alcal{\'a}},
  url    = {https://github.com/Darkrai500/SycoCode}
}
```

Machine-readable metadata in [CITATION.cff](CITATION.cff).
