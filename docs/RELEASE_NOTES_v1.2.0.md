# SycoCode v1.2.0 — release notes

Date: 2026-11-20. Previous version:
v1.1.0 (2026-10-05, DOI 10.5281/zenodo.23158882).

v1.2.0 adds a held-out human reference for the verbal labels of the nine
evaluated models other than the pilot model, the code that produced it, and
the analysis scripts behind the attribution-rule sensitivity results of the
revised article. Benchmark items, campaign data, replay ledgers and the
functional results are unchanged.

## Added

- **Held-out reference (ReEval-2)** in [`data/reeval2/`](../data/reeval2/README.md):
  180 judged turns sampled from the 21,600 judged turns of the nine cohort
  models; two annotators who are not authors labelled every turn, and a third
  person who is not an author adjudicated the 51 disagreements. Released: the
  six application exports byte-identical with `SHA256SUMS`, the unsealed
  sample key, the pool and manifest loaded in the application, the joined
  reference (`held_out_reference_v1.jsonl`) and the scorer output
  (`reeval2_scores.json`). Conversation payloads are not distributed; their
  SHA-256 hashes are.
- **Protocol** [`docs/methodology/reeval2_protocol.md`](methodology/reeval2_protocol.md),
  byte-identical to the version in force (SHA-256
  `4fd002b78fda14fb17a1002f688380f56b054b4941c66508f7d86a1b27ca876f`), and its
  [record](methodology/reeval2_protocol_record.md): how to verify the hash, why
  the file still says "draft, not frozen", the deviations and limits of the
  procedure, and the two analyses the data did not allow.
- **Annotation application, crossed design** (`webapp/`): pseudonymous fixed
  roles, per-role route allow-list (`CrossedStudyGuard`), calibration page that
  stores nothing, final hand-in with declaration and digest, automatic queue
  cut at the second hand-in, adjudicator closure, downloads only after closure
  with a per-download SHA-256 record, audit export, logged password resets
  (`reset_study_password`). Migration `0004_reeval2_flow` adds the new tables
  and fields; the first study's partitioned design is unchanged.
- **Scripts**: `build_reeval2_calibration.py`, `build_reeval2_rehearsal.py`,
  `export_reeval2_reference.py` (builds the reference after checking the
  exports against the server's own records), `policy_sensitivity.py` (with
  output `data/replay/policy_sensitivity.json`) and the output of
  `decompose_flips.py` (`data/replay/flip_decomposition.json`).

## Changed

- `score_reeval2.py`, `test_score_reeval2.py` and `build_reeval2_sample.py`
  are the versions that ran the study (recall and precision intervals, the
  pre-specified split by scenario type, opaque record identifiers in the pool).
- Documentation of the verbal layer: the README no longer headlines a verbal
  capitulation range or an English/Spanish verbal contrast; verbal results are
  described as secondary and descriptive, with agreement with human labels
  stated for both references (pilot reference: κ 0.62 against the adjudicated
  reference, 0.45 against the external annotators alone; held-out reference:
  κ 0.59, 95% CI 0.50–0.68). The DATASHEET, `data/reeval/README.md`,
  `data/goldset/PANEL_DECISION.md`, the webapp README and the reproduction
  guide were updated accordingly, and the thesis-era result documents in
  `docs/results/` carry a dated note withdrawing their claims of a "robust" or
  "unanimous" English/Spanish verbal effect.
- `.gitignore`: the released directory is `data/reeval2/`; the private working
  copies (`data/ReEval2/sample/`, `data/ReEval2/ensayo/`) stay ignored, also on
  case-insensitive file systems.

## Removed

- `manage.py build_adjudication_queue`: in the crossed design the queue is cut
  automatically, in the same transaction as the second hand-in.

## Not included

- The conversation payloads shown to the annotators (outputs of the nine
  evaluated models, which the repository does not redistribute).
- The deployment runbook of the study's server instance.

## Verification

- `python scripts/export_reeval2_reference.py --out …`: all eight integrity
  checks pass (four server-logged export hashes, two hand-in digests, the
  annotation-state digest at queue cut and at closure); output byte-identical
  to the released reference.
- `python scripts/score_reeval2.py …`: output byte-identical to
  `data/reeval2/reeval2_scores.json`; `scripts/test_score_reeval2.py`: 16/16.
- `python scripts/reeval2_exploratory.py --out …`: output byte-identical to
  `data/reeval2/reeval2_exploratory.json` (checks that are not in the analysis
  plan; Supplementary Table S11.12).
- `python scripts/policy_sensitivity.py` and `python scripts/decompose_flips.py`:
  outputs byte-identical to the released JSON files; the first reproduces
  `data/replay/statistics.json` before running.
- `manage.py test annotations`: 69 tests (the first study's tests unchanged).
