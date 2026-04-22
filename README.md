f# SycoCode

> A bilingual benchmark for measuring sycophancy in LLMs on code generation and code review tasks.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Dataset License: CC BY 4.0](https://img.shields.io/badge/Dataset%20License-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATASET)
[![Status](https://img.shields.io/badge/Status-In%20Development-orange.svg)](#project-status)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Landing](https://img.shields.io/badge/Project%20Page-darkrai500.github.io%2FTFG__SycoCode-2ea44f)](https://darkrai500.github.io/TFG_SycoCode/)

**Project page:** https://darkrai500.github.io/TFG_SycoCode/

---

## What is SycoCode?

SycoCode is an academic benchmark designed to measure **sycophancy** — the tendency of large language models to yield to user pressure rather than maintain truthful, well-grounded responses — in the specific domain of **code generation and code review**. Unlike general-purpose sycophancy benchmarks (e.g., SycophancyEval, ELEPHANT, SYCON-Bench), which operate on open-ended text and typically rely on LLM-as-judge evaluation, SycoCode grounds every pressure scenario in **executable test suites**: each injected bug is defined by a test that objectively passes or fails, removing the need for subjective adjudication.

The benchmark is also **bilingual** (English / Spanish). Every scenario is instantiated in both languages with otherwise identical content, allowing a direct measurement of whether a model's sycophantic behavior changes with the language of interaction — a dimension that existing code-focused and sycophancy-focused benchmarks have not covered.

The code domain makes the problem particularly consequential. A model that softens a valid bug report under a user's expressed satisfaction, or that reverses a correct diagnosis when the user pushes back, is not merely being polite — it is actively letting defects into the artifacts developers ship. Sycophancy in code review translates directly into production bugs.

## Why this matters

- **A cross-lingual axis for code sycophancy.** The *Bilingual Sycophancy Gap (BSG)* is, to our knowledge, the first metric explicitly designed to quantify how an LLM's susceptibility to social pressure varies between English and Spanish in programming contexts. Prior work (ELEPHANT, Cheng et al., 2025) has explicitly flagged cross-lingual generalization as an open question; SycoCode provides a concrete, reproducible measurement instrument for it in the code domain.

- **Benchmark contamination as an amplifier of evidence, not a confound.** HumanEval and MBPP are well-known training-data staples, and it is plausible that every evaluated model has seen their reference solutions during pretraining. Rather than treating this as a weakness, SycoCode treats it as a **strengthener** of the sycophancy signal: if a model that has likely memorized the correct solution still capitulates when a user asserts the opposite, the observed failure cannot be attributed to ignorance — it is sycophancy in the strict sense. The executable-test ground truth further removes any ambiguity about which answer was correct.

- **Pressure prompts are informationally empty.** The adversarial turns used in SycoCode ("are you sure?", "I have 15 years of experience and I'm telling you this is fine", iterated insistence) contain **no new technical information** that would warrant revising a correct judgment. They are, in argumentative terms, closer to rhetorical fallacies than to counter-arguments. This framing is what lets SycoCode cleanly separate *sycophancy* (yielding in the absence of new evidence) from *legitimate reconsideration* (updating on new evidence).

## Methodology at a glance

### Dataset

Problems are drawn from **HumanEval** (OpenAI, 164 Python problems with test suites) and **MBPP** (Google, ~1,000 problems). A target of 40–50 problems is curated, and each correct reference solution is mutated with a **controlled bug** at one of three difficulty levels:

- **Level 1 — Obvious:** off-by-one errors, incorrect operators, undefined variables.
- **Level 2 — Moderate:** uncovered edge cases (empty lists, negative values), logic errors in compound conditionals, incorrect initializations.
- **Level 3 — Subtle:** numerical precision errors, incorrect behavior only on extreme inputs, accidental mutation of mutable parameters.

For every injected bug, the original test suite **must fail**, yielding a fully automated and verifiable ground truth. Each problem is then instantiated across all four scenarios × two languages, producing on the order of 400–500 evaluations per model.

### Scenarios

| Scenario | Theoretical basis | Description |
|---|---|---|
| **Code Review Sycophancy** | Feedback sycophancy (Sharma et al., 2023) | The model reviews buggy code while the user expresses satisfaction with the implementation; the test measures whether the model softens or suppresses its criticism. |
| **Answer Flip Sycophancy** | FlipFlop (Laban et al., 2023) | The model correctly identifies a bug and is then challenged by the user; the test measures whether it abandons the correct diagnosis. |
| **Expertise Deference** | Social sycophancy (ELEPHANT, Cheng et al., 2025) | The user makes the same incorrect assertion while claiming to be a senior developer or a novice; the test measures the effect of perceived authority. |
| **Insistent Sycophancy** | Multi-turn (SYCON-Bench, Hong et al., 2025; SycEval) | The user insists over 3–8 turns with escalating pressure; the test measures the turn at which the model capitulates. |

### Metrics

| Symbol | Name | What it measures |
|---|---|---|
| **FR** | Flip Rate | Proportion of correct evaluations the model changes to incorrect under user pressure. Adapted from Laban et al. (2023). Range [0, 1]; 0 = total resistance. |
| **BDA** | Bug Detection Accuracy | Model accuracy at detecting bugs under each pressure condition, compared against a no-pressure control. The drop **ΔBDA** quantifies the effect of sycophancy. |
| **SS** | Susceptibility Score | Composite metric weighting FR by bug difficulty: yielding on an obvious (Level 1) bug is scored as more sycophantic than yielding on a subtle (Level 3) bug. |
| **ToC** | Turn of Capitulation | For multi-turn scenarios, the turn at which the model abandons its correct position. Adapted from SYCON-Bench. Higher = greater resistance. |
| **BSG** | Bilingual Sycophancy Gap | Difference in FR (or BDA) between the English and Spanish versions of the same scenario. Original contribution of this work. |

### Composite

A **SycophancyIndex** — an aggregated composite of the five metrics above into a single comparable score per model — is under consideration as an additional post-collection calibration step. It is **not part of the committed methodology** and will only be defined and published if the collected data support a principled aggregation. Per-metric reporting remains primary either way.

## Models evaluated

A target of **eleven models** spanning three categories, accessed uniformly through OpenRouter. The list is **subject to update based on availability** at evaluation time.

| Category | Models |
|---|---|
| Frontier proprietary | Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro |
| Economical variants | Claude Haiku 4.5, Gemini 3.1 Flash Lite , GPT-5.4 mini|
| Open source | DeepSeek-V3.2, Qwen3 Coder, GLM-4.7, Kimi K2.5, Devstral |

The inclusion of economical variants enables an intra-family comparison: do smaller models within the same provider exhibit higher sycophancy? The open-source set adds geographic and architectural diversity, including code-specialized models.

## Project status

- ✅ Proposal approved (April 2026)
- ✅ Experimental design finalized
- 🚧 Dataset construction (in progress)
- ⏳ Data collection (planned Q2–Q3 2026)
- ⏳ Analysis and SycophancyIndex calibration
- ⏳ Public release on HuggingFace

## Planned release

- **This repository** will host the evaluation framework: pipeline code, prompt templates, metric implementations, and analysis notebooks. License: MIT.
- **HuggingFace Datasets** will host the bilingual dataset of problems, injected bugs, test suites, and — once collected — per-model responses. License: CC BY 4.0.
- **Project page:** https://darkrai500.github.io/TFG_SycoCode/ — public landing with overview, motivation, and updates.

## Repository structure

Planned layout. Items marked *(planned)* do not yet exist in the repository.

```
SycoCode/
├── README.md
├── LICENSE                        # MIT (framework code)
├── LICENSE-DATASET                # CC BY 4.0 (dataset)
├── data/                          (planned)
│   ├── problems/                  (planned)  HumanEval/MBPP-derived problems with injected bugs
│   ├── prompts/                   (planned)  Bilingual (EN/ES) pressure prompts per scenario
│   └── tests/                     (planned)  Executable test suites defining ground truth
├── src/                           (planned)
│   ├── pipeline/                  (planned)  OpenRouter-based evaluation runner
│   ├── scenarios/                 (planned)  The four sycophancy scenarios
│   ├── metrics/                   (planned)  FR, BDA/ΔBDA, SS, ToC, BSG
│   └── analysis/                  (planned)  Statistical analysis and leaderboard generation
├── results/                       (planned)  Per-model evaluation outputs
└── notebooks/                     (planned)  Exploratory and reporting notebooks
```

## Installation & usage

Installation and usage instructions will be published alongside the first data release. The evaluation framework is under active development and its API is not yet stable.

## Citation

A formal citation will be updated once the work is published. For now, please cite:

```bibtex
@misc{negrin2026sycocode,
  author       = {Negr{\'i}n, Juan Carlos},
  title        = {SycoCode: A Bilingual Benchmark for Measuring Sycophancy in
                  LLMs on Code Generation and Review Tasks},
  year         = {2026},
  note         = {Undergraduate Thesis (TFG), Universidad de Alcal{\'a}},
  howpublished = {\url{https://darkrai500.github.io/TFG_SycoCode/}}
}
```

## Acknowledgements

This work is developed as an undergraduate thesis (Trabajo de Fin de Grado) within the B.Sc. in Information Systems Engineering (G581) at the **Escuela Politécnica Superior, Universidad de Alcalá (EPS-UAH)**.

Thesis supervision: **Antonio García Cabot** (tutor) and **David de Fitero Domínguez** (co-tutor), Department of Computer Science, EPS-UAH.

## License

- **Framework code** — MIT License. See [LICENSE](LICENSE).
- **Dataset** (upon release) — Creative Commons Attribution 4.0 International (CC BY 4.0). See [LICENSE-DATASET](LICENSE-DATASET).

## Contact

Juan Carlos Negrín — juan.negrin@edu.uah.es
