# Phase C — Post-hoc VCR runbook (execute AFTER the full gpt-oss run finishes)

**Status:** prepared 2026-06-09 · waiting on the full-corpus generation run.
**Owner action to trigger:** when the generation run is done, say to Claude:
> «retomamos: haz el VCR post-hoc sobre `data/runs/full/responses.jsonl`»

This file is the source of truth for that task.

---

## Why (context)

The judge bake-off (report §8.8–8.10) showed **no API judge clears the κ ≥ 0.6 gate** and
all fail at detecting capitulation. So **VCR is done post-hoc by Claude/Sonnet** via
multi-agent orchestration (Max subscription → ~free; Sonnet scored **6/6** on the hardest
gold turns, including the *firm-but-wrong* cases every API judge missed). Generation
(Cerebras `gpt-oss-120b`) and the deterministic oracle (Pass 2) are unchanged; VCR only
needs the saved transcripts, so it is fully decoupled.

Pieces already built (uncommitted): `.claude/agents/vcr-annotator.md` (Sonnet),
`.claude/workflows/vcr-agent-eval.js`, `scripts/build_vcr_annotation_inputs.py` (5-digit
task files), `scripts/aggregate_vcr_agent.py`. The VCR rubric + the firm-but-wrong
principle are baked into both the task files and the agent.

---

## Preconditions

- `data/runs/full/responses.jsonl` exists and the run is **completed** (Pass 1 generation).
- `CEREBRAS_API_KEY` only needed for generation/oracle-rerun, NOT for VCR (VCR uses the
  Claude subscription via subagents).

---

## Step 0 — verify the generation run

```bash
.venv/bin/python - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('data/runs/full/responses.jsonl')]
c=collections.Counter(r.get('status') for r in rows)
print('records:', len(rows), '| status:', dict(c))
PY
```
Expect ~1900 records, mostly `completed`. (`partial` is fine — VCR still judges them.)

## Step 1 — Pass 2 oracle (deterministic, free) if not already done

```bash
.venv/bin/python -m eval.oracle --responses data/runs/full/responses.jsonl \
  --out data/runs/full/verdicts.jsonl
```
Gives BDA / ΔBDA / BSG and the per-record correctness needed to cross-tab against VCR.

## Step 2 — build the blind VCR task files (one per judged turn)

```bash
PYTHONPATH=. .venv/bin/python scripts/build_vcr_annotation_inputs.py \
  --responses data/runs/full/responses.jsonl \
  --tasks-dir data/runs/full/vcr_tasks \
  --manifest  data/runs/full/vcr_manifest.json
# how many turns (= number of agents to run):
.venv/bin/python -c "import json;print('N turns =', len(json.load(open('data/runs/full/vcr_manifest.json'))))"
```
Expect **~2,800** turns (control 400 + code_review 300 + answer_flip 300 + expertise 600 +
insistent 1200).

## Step 3 — orchestrate the Sonnet VCR (Claude runs the Workflow tool, in slices)

The Workflow agent-count cap is **1000/run**, so slice `N` into batches of ~900. Claude
invokes (NOT a shell command):

```
Workflow({ scriptPath: ".claude/workflows/vcr-agent-eval.js", args: {
  tasksDir: "data/runs/full/vcr_tasks",
  outDir:   "data/runs/full/vcr_out",
  who: "a", chunk: 8,
  startIdx: 0, endIdx: 900            // then 900–1800, 1800–2700, 2700–N
}})
```
Repeat for each slice until the whole range is covered. `chunk: 8` throttles concurrency to
respect subscription rate limits. Each agent reads `vcr_tasks/t#####.md` and writes
`vcr_out/a_t#####.json`.

## Step 4 — aggregate + recover missing (loop until 0 missing)

```bash
PYTHONPATH=. .venv/bin/python scripts/aggregate_vcr_agent.py \
  --manifest data/runs/full/vcr_manifest.json \
  --out-dir  data/runs/full/vcr_out --who a \
  --out      data/runs/full/vcr_agent.jsonl
```
The output JSON prints `missing_idxs`. If non-empty, Claude re-runs the workflow with
`args: { ..., idxs: [<the missing ids>] }` (no startIdx/endIdx). Repeat Step 4 → Step 3
until `missing_count == 0`. Result: **`data/runs/full/vcr_agent.jsonl`** (vcr.jsonl-shaped).

## Step 5 — analysis

- VCR distribution + capitulation rate **per scenario_family** and **per language**.
- ΔBDA: join `vcr_agent.jsonl` with `verdicts.jsonl` on `record_id` for the FR×VCR cross-tab
  and the insistent-ladder Turn-of-Capitulation.
- Aggregate the Phase-D metrics (FR / SS / ΔBDA / AFR / VCR / ToC / BSG) over the 50 problems.

---

## Notes / caveats

- **Single annotator** (`who="a"`) by default. For a reliability panel, re-run Step 3 with
  `who: "b"` (and `"c"`) into the same `vcr_out/`; the aggregator takes `--who`.
- **True-human κ still pending**: spot-check a stratified ES+EN sample by hand to validate the
  Sonnet annotator before publishing VCR numbers (thesis requirement).
- **Reproducibility**: Sonnet is less deterministic than a temp-0 API judge; the rubric is
  fixed and it is our gold-standard instrument, but record the model/date in the writeup.
- **Optional dry-run first**: run Steps 2–4 on the pilot (`--responses
  data/pilot/cand_001/responses.jsonl`, 56 turns, single slice) to rehearse the whole flow
  and get its κ vs the existing `human_gold.jsonl` before committing the ~2,800-turn corpus.
- Cost: generation ≈ $5 (Cerebras), oracle free, VCR ≈ free (subscription).
