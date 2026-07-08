# SycoCode — Datasheet

This datasheet documents the SycoCode dataset following the *Datasheets for Datasets* framework (Gebru et al., 2021), organised into the seven standard areas. The construction methodology is described in the methodology documentation under `docs/methodology/`; this datasheet records the properties of the dataset *as built*. Questions that have no answer anchored in the available artefacts are marked explicitly rather than filled in.

## Motivation

**For what purpose was the dataset created?** To measure sycophancy in code-generation assistants — the tendency to abandon a correct analysis under user pressure — in a bilingual English/Spanish setting. SycoCode separates what a model *says* (a verbal-capitulation layer) from what it *does* (an execution-verified functional layer), and pairs every problem, bug, and scenario across the two languages so that the language effect can be isolated. No prior benchmark was specific to code assistants or bilingual in this respect.

**Who created the dataset and on whose behalf?** Juan Carlos Negrín, as a Bachelor's thesis (Trabajo de Fin de Grado) at the Escuela Politécnica Superior, Universidad de Alcalá (2025/2026), supervised by Antonio García Cabot and David de Fitero Domínguez.

**Who funded the creation of the dataset?** No external funding or grant is recorded; the work was carried out in an academic (TFG) context.

## Composition

**What do the instances represent, and how many are there?** The dataset has three layers. Layer 1 (`data/problems/problems.jsonl`) holds **50** canonical Python problems, each with **3** execution-verified injected bugs, for **150** bugs in total (bug edits are specified in `data/problems/bug_specs.json`). Layer 2 (`data/problems/scenarios.jsonl`) holds **7** bilingual pressure-scenario templates across five families. Layer 3 (`data/problems/items.jsonl`) holds **1900** fully rendered evaluation items — the Cartesian product of problems, scenarios, bug variants (or the canonical solution for the clean control), and the two languages: **1800** buggy plus **100** clean-control items, split evenly as **950** English and **950** Spanish.

**What does each instance comprise, and is there a label?** Each Layer-3 item carries the rendered prompts, the scenario configuration, and a `ground_truth` block (bug present, bug identifier, category, level, and a textual bug description that anchors the verbal-capitulation judge). The grading oracle is deliberately *not* embedded in the items: it lives in Layer 1 (canonical solution plus harness), which the items reference by identifier.

**How are the bugs distributed?** The 150 bugs use a closed nine-category taxonomy, distributed as: wrong operator 34, off-by-one 29, wrong value 26, missing edge case 19, off-specification 18, wrong function call 13, precision or overflow 7, API misuse 3, and excess logic 1. Their three-tier difficulty is L1/L2/L3 = 52/75/23.

**How are the scenarios composed?** The five families are *control* (a neutral buggy baseline and a clean canonical false-positive control), *code review*, *answer flip* (two-turn), *expertise deference* (a senior and a student variant), and *insistent* (a fixed five-turn ladder); five scenarios are single-turn and two are multi-turn. The 1900 items split as 300 items for each of the six two-language buggy scenarios and 100 for the clean control.

**Are there recommended data splits?** No. SycoCode is an evaluation-only benchmark; no train/validation/test split is defined.

**Are there errors, noise, or redundancies?** Items derived from the same problem and template layers are not statistically independent; this is acknowledged as a threat to validity rather than corrected for (see the results documentation in `docs/results/`). Every injected bug is execution-verified, and each item carries a unique SHA-256 `content_hash`; no per-instance defects are recorded.

**Is the dataset self-contained?** The Layer-3 items deliberately depend on Layer 1 for the grading oracle, which in turn derives from pinned snapshots of the upstream source benchmarks. The long-term availability of those upstream hosts is not guaranteed by this dataset.

**Does the dataset contain confidential, offensive, or personal data?** No. The instances are self-contained programming problems and synthetic dialogue templates; they contain no personal data and no human-subject content.

## Collection Process

**How were the data acquired?** The 50 problems were selected from public code-generation benchmarks, pinned by revision and downloaded reproducibly by `scripts/download_sources.py`: 40 problems from HumanEval+ and 10 from the MBPP family (of which 9 are graded by the MBPP+ differential oracle and 1 by the MBPP-sanitized assert-list oracle). The original HumanEval set was downloaded but excluded from selection in favour of HumanEval+'s stronger tests.

**What was the sampling strategy?** A documented three-phase selection funnel (591 → 174 → 90 → 50) filtered the candidate pool for oracle determinism, a sycophancy-sensitive difficulty band, at least two admissible bug categories, uncontested ground truth, and cross-source de-duplication; the MBPP share was deliberately fixed at 10 of 50 to strengthen the contamination argument (see the corpus-selection notes in `docs/methodology/`).

**How were the bugs and scenarios produced?** Each bug is a single-anchor string-replacement edit authored against the canonical solution and *re-verified by execution* at build time: the generator runs the oracle and refuses to ship any bug that does not provably fail at least one canonical test, so all 150 bugs carry `verified_failing = true` (see the dataset design notes in `docs/methodology/sycocode_dataset_design.md`). The seven pressure scenarios were authored from the sycophancy literature — control and feedback scenarios after Sharma et al. (2023), the answer-flip scenario after Laban et al. (2023), and the insistent five-turn ladder after Hong et al. (2025) and Fanous et al. (2025); the expertise-deference scenarios follow an inline-persona design detailed in the methodology docs.

**Who was involved, and how were they compensated?** The available artefacts do not record the human-versus-tooling division of the bug-authoring and quality-scoring labour, nor any compensation; this is not anchored in the repository.

**Over what timeframe were the data collected?** The source snapshots were downloaded on 2026-05-13 and the dataset-construction phase closed on 2026-05-29; the individual authoring dates of the candidate-selection and bug-injection steps are not separately recorded.

**Were any ethical review processes conducted?** None applies: the dataset contains no human-subject data. The only human-annotation element is a single-annotator calibration set (see Preprocessing).

## Preprocessing / Cleaning / Labeling

**Was preprocessing done?** Layer 1 is generated by `scripts/build_problems.py` (apply each edit, derive a unified diff, run the oracle to capture the failure evidence, schema-validate). Layer 3 is generated deterministically by `scripts/build_items.py` as the Cartesian product, stamping a SHA-256 hash per item and asserting exactly 1900 unique items.

**What cleaning decisions were made?** Candidates whose canonical solution was itself faulty, whose specification was contestable, or whose semantics were inverted were dropped so that ground truth stays uncontested, and structural duplicates were reduced to at most two representatives per cluster (see the corpus-selection notes in `docs/methodology/`). The raw source snapshots are preserved immutable and are never edited in place; all transformation occurs in derived files.

**How were the data labelled?** Bugs carry a closed nine-category taxonomy and a three-tier difficulty rubric, with per-problem provenance fields recording the admitted and used categories and the level rationale. A separate verbal-capitulation calibration gold set of **320** judged assistant turns (distributed under `data/goldset/`) was labelled (firm 291 / hedged 19 / capitulated 10; 41 turns committed by the human annotator and 279 from a frontier-model pre-label proxy), reaching Cohen's κ = 0.65 between the human annotator and the blind pre-label; the judge panel reaches κ = 0.76 against this gold set as originally locked and κ = 0.67 with the substituted cohort tie-breaker (see the judge-calibration documentation in `docs/methodology/`). A second human annotator was postponed, so a human–human inter-annotator agreement is not yet available.

**Is the preprocessing software available?** Yes — the build and verification scripts (`scripts/build_problems.py`, `scripts/build_scenarios.py`, `scripts/build_items.py`, `scripts/verify_bugs.py`) are part of the code base. The tool that produced the candidate quality scores is not present as a script; those scores reflect a manual or assisted judgement.

## Uses

**What tasks has the dataset been used for?** A ten-model comparative study of code-generation sycophancy (see `docs/results/`), evaluating ten LLMs on the same 1900 items, judge panel, and execution oracle, and reporting Bug-Detection Accuracy, its pressured variant, the Verbal-Capitulation Rate, a Susceptibility Score, a baseline-disagreement measure, and a turns-to-capitulation measure. Aggregated per-model results are distributed under `data/runs/aggregates/`; the raw model transcripts from these runs are **not** distributed.

**What else might it be used for?** Cross-lingual robustness studies, judge-calibration research, and as a regression suite for sycophancy mitigations.

**Is there anything that should inform future use?** The corpus is a single 50-problem sample reported without confidence intervals as yet; every absolute accuracy carries a false-positive-rate floor; and one panel judge is also an evaluated model (a partial self-judge confound). These limitations are detailed in the results documentation and bound the strength of cross-model claims.

**Are there tasks for which the dataset should not be used?** The dataset targets logical correctness, not security: security-weakness categories are explicitly excluded, so it should not be used to assess vulnerability detection.

## Distribution

**How and when will the dataset be distributed?** The benchmark is distributed through this dedicated public repository: the dataset under a Creative Commons Attribution (CC-BY) licence (`LICENSE-DATASET`) and the code under the MIT licence (`LICENSE`). Development took place in a separate working repository, and this public repository is the release channel by deliberate decision; no DOI has been assigned at the time of writing.

**Under what licence are the source data redistributed?** The upstream source benchmarks retain their own licences, recorded with the pinned snapshots: HumanEval (MIT; Chen et al., 2021), HumanEval+ and MBPP+ (Apache-2.0; Liu et al., 2023), and MBPP-sanitized (CC-BY-4.0; Austin et al., 2021). A redistribution-compatibility analysis of these licences for the derived corpus is not yet recorded.

**How should the dataset be cited?** As the associated Bachelor's thesis (Negrín, 2026; BibTeX key `negrin2026sycocode`).

## Maintenance

**Who maintains the dataset, and how can they be contacted?** The dataset is maintained by the author; questions and errata can be raised through this repository's issue tracker.

**Will the dataset be updated, and is it versioned?** The dataset layers carry a schema version (`0.2.0`). The dataset is fully regenerable from pinned source snapshots through the documented build pipeline (see `scripts/` and the methodology docs), so corrections propagate by rebuilding. A formal update cadence, erratum policy, version-retention policy, and external-contribution mechanism are not yet defined.

**Are there retention limits or third-party restrictions?** Beyond the inherited upstream licences, no additional retention limits or third-party restrictions are recorded.

---

## References

- Gebru, T., et al. (2021). Datasheets for Datasets. *Communications of the ACM*, 64(12).
- Sharma, M., et al. (2023). Towards Understanding Sycophancy in Language Models.
- Laban, P., et al. (2023). Are You Sure? Challenging LLMs Leads to Performance Drops.
- Hong, J., et al. (2025). Measuring Sycophancy of Language Models in Multi-turn Dialogues.
- Fanous, A., et al. (2025). SycEval: Evaluating LLM Sycophancy.
- Chen, M., et al. (2021). Evaluating Large Language Models Trained on Code (HumanEval).
- Liu, J., et al. (2023). Is Your Code Generated by ChatGPT Really Correct? (EvalPlus: HumanEval+/MBPP+).
- Austin, J., et al. (2021). Program Synthesis with Large Language Models (MBPP).
