# Reproducing SycoCode offline

Everything reported for the ten-model campaign can be regenerated from files
distributed with the repository, without API keys or model calls. Stored
responses, not live endpoints, are the unit of reproduction: the model behind
a provider's name can change, so a new run against current endpoints is a new
measurement.

Three levels are distinguished:

| Level | What it regenerates | Inputs |
|---|---|---|
| A. Arithmetic | Every flip rate, BSG, interval, paired contrast, Holm adjustment and subgroup of the campaign | `data/replay/` ledgers (no response text) and NumPy |
| Human reference | Agreement of the judge panel with the human reference (Cohen's κ with problem-clustered intervals, by language and class, and under alternative references) | `data/reeval/human_reference_v1.jsonl`, `data/goldset/votes.jsonl` |
| B/C. Audit or re-execution | Code selection, attribution and test execution from raw responses | Raw per-model responses, which are not redistributed; the 320 pilot transcripts are in `data/goldset/payloads/` |

## 1. Verify a checkout

Requires **CPython 3.12**. The lock file pins 29 packages, including transitive
dependencies, with distribution hashes. Installation needs PyPI once; the
checks need no network and block network calls from their Python processes.

```bash
python3.12 -m venv .venv-repro
.venv-repro/bin/python -m pip install --require-hashes -r requirements-reproducibility.lock
WORK=$(mktemp -d)
.venv-repro/bin/python -B -I scripts/check_reproducibility.py --out "$WORK/checks"
```

Success exits 0 and writes `validation.json` with `status: passed`. The output
directory must be new and outside the checkout; the checker works on a
temporary copy and verifies afterwards that its inputs did not change.

| Check | Scope |
|---|---|
| Original test scripts | 127 checks: client and retries, registry, simulated validation, judges and verbal processing |
| Reanalysis | 12 tests of turn states, pairing, uncertainty and agreement |
| Replay package | 9 tests of hashes, unexpected files, links, duplicates, states, no-overwrite and replay without cache |
| Dataset | JSON Schema validation of 50 problems, 7 scenarios and 1,900 items; scenarios and items rebuilt byte for byte |
| Figures | 20 aggregate figures regenerated and decoded (pixel identity with earlier figures is not claimed) |

The oracle self-test executes the canonical solution and one bug of problem
`cand_001`. The profile does not execute model-generated code. The network
guard detects accidental connections; it is not a sandbox for untrusted code.

## 2. Replay the campaign statistics (level A)

```bash
.venv-repro/bin/python -B scripts/build_replay_bundle.py --out "$WORK/SycoCode-Replay-A.zip"
unzip -q "$WORK/SycoCode-Replay-A.zip" -d "$WORK/unpacked"
python3.12 -m venv "$WORK/replay-venv"
"$WORK/replay-venv/bin/python" -m pip install --require-hashes \
  -r "$WORK/unpacked/sycocode-replay/requirements.txt"
"$WORK/replay-venv/bin/python" -B -I \
  "$WORK/unpacked/sycocode-replay/scripts/verify_replay_bundle.py" --out "$WORK/replayed"
```

The package contains the two ledgers (19,000 conversations and 34,000 turns
with identifiers, states under every attribution policy, labels and code
hashes, but no conversation text), the expected statistics, the analysis
scripts and a NumPy-only requirements file. The verifier recomputes the
complete statistics JSON (10 models, 50 problems, 10,000 resamples, seed
20260919) and compares all of it, including denominators, intervals, paired
contrasts and multiplicity adjustments. The ZIP is deterministic for the same
inputs. See [BUNDLE_README.md](BUNDLE_README.md) for what a successful replay
does and does not establish.

## 3. Score the judge panel against the human reference

```bash
.venv-repro/bin/python scripts/score_human_reference.py --out "$WORK/agreement.json"
```

This reproduces the agreement table of the article and the Supplementary
Material: the archived pilot labels (κ = 0.624, 95% CI 0.44–0.76), the
reconstructed cohort configuration (κ = 0.551), agreement between the two
human labels of each turn (κ = 0.529) and the sensitivity of panel agreement
to the choice of reference. The reference itself is described in
[`data/reeval/README.md`](../../data/reeval/README.md).

## Dependencies

`requirements-reproducibility.in` collects the evaluation requirements, JSON
Schema and Matplotlib. The lock is a current verification environment, not a
lock recovered from the June 2026 campaign. To update it deliberately:

```bash
uv pip compile --python-version 3.12 --generate-hashes --no-header --no-annotate \
  requirements-reproducibility.in --output-file requirements-reproducibility.lock
```

`requirements-replay.lock` pins NumPy 2.0.2 for the replay package. After any
dependency change, rerun the checks and the full replay. Hashes verify bytes;
future availability on PyPI is a separate condition. Verified on macOS arm64
with Python 3.12; Linux and Windows were not tested for this profile.
