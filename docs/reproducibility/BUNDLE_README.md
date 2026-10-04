# SycoCode replay package (v1.1.0)

This package recalculates the complete exploratory statistics JSON from the
19 September 2026 derived ledgers: 19,000 conversations, 34,000 turns, 24,000
verbal labels, 10 models and 50 problems. It uses 10,000 resamples and seed
20260919. It contains no conversation text, generated code, individual human
annotations, API credentials or production database.

The package is built from files distributed with SycoCode v1.1.0
(`data/replay/` and the listed scripts) by `scripts/build_replay_bundle.py`.
The included MIT license covers project code; this package does not grant
additional rights over underlying provider or benchmark material.

## Run in a new folder

Use CPython **3.12**. Create the environment outside `sycocode-replay/` so the
verifier can check that the package contains exactly its declared files.
Installation needs PyPI access once; verification and replay need no network
or API keys. Commands below start in the directory containing the extracted
`sycocode-replay/` folder.

```bash
python3.12 -m venv replay-venv
replay-venv/bin/python -m pip install --require-hashes -r sycocode-replay/requirements.txt
replay-venv/bin/python -B -I sycocode-replay/scripts/verify_replay_bundle.py --out replay-results
```

`replay-results` must not already exist. Success exits 0 and writes
`statistics.json`, `validation.json` and `bundle_validation.json`. The complete
statistics JSON must be structurally identical, including denominators,
intervals, paired contrasts and multiplicity adjustments. The verifier also
checks file hashes, duplicate/missing units, common model coverage, and the
link between each conversation and its turns. It rejects unexpected files
and symbolic links. Use a fresh extracted package if an editor creates files.

A Python audit hook blocks accidental network calls in the replay process.
This hook is not an operating-system sandbox for executing untrusted code.
Only saved derived outcomes are analysed. Record the ZIP SHA-256 supplied
with the package: its internal manifest detects modifications but cannot
authenticate an archive whose manifest has also been replaced.

## What a successful replay establishes

It verifies arithmetic on the fixed ledgers. It does not validate the
original extraction, hidden-test execution, labels, judge panel or future API
outputs. Agreement with the human reference is computed separately by
`scripts/score_human_reference.py` from `data/reeval/`; replacing the 320
pilot labels with that reference changes no functional outcome. The expected statistics preserve their
historical exploratory status. Unknown alternative-code outcomes remain null.

`PROVENANCE.json` records the local source hashes of the imported analysis
and ledgers. `manifest.json` records the exact files included here. Review the
source code before running it. Cross-platform floating-point identity is a
check to perform on the target platform, not an assumption of this package.
