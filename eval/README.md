# Phase C — Pass 1 generation runner (`eval/`)

Consumes the read-only `data/problems/items.jsonl` and produces the canonical
record of raw model output. **No judgment here** — no test execution, no
LLM-as-judge (those are Pass 2/3). Contract: [`docs/phase_c_eval_schema.md`](../docs/methodology/phase_c_eval_schema.md).

## Outputs (under `data/runs/`, gitignored)
- `responses.jsonl` — canonical, append-only; one record per item.
- `runs.jsonl` — run lifecycle (`started` → `finished`/`aborted`).
- `status/<run_id>.json` — live progress (rebuildable, disposable).

## Setup
```bash
.venv/bin/pip install -r requirements-eval.txt   # httpx (already vendored)
cp .env.example .env                              # then paste CEREBRAS_API_KEY=...
```
Get a key at <https://cloud.cerebras.ai>. The key is read from the environment /
`.env` only and is never written to any record.

## Run

**Preview a scope (no API calls):**
```bash
.venv/bin/python -m eval --scope-problem cand_001 --dry-run
```

**Checkpoint 2 — one real single-turn call** (1 item, 1 request):
```bash
.venv/bin/python -m eval \
  --scope-problem cand_001 --scope-scenario code_review_sycophancy \
  --scope-language en --limit 1
```

**Checkpoint 3 — pilot slice** (cand_001: 38 items, ~68 requests; 1/2/5 turns + both controls):
```bash
.venv/bin/python -m eval --scope-problem cand_001
```

**Full run — all 50 problems / 1900 items** (just drop the scope filter):
```bash
.venv/bin/python -m eval
```

**Resume** (skips items already `completed` for that run):
```bash
.venv/bin/python -m eval --resume "<run_id>"
```

## Defaults (Cerebras gpt-oss-120b, Developer tier)
`temperature=0.0`, `top_p=1.0`, `max_tokens=8192` (reasoning model — needs room
for the hidden reasoning channel + final answer), `seed=7`, `concurrency=12`,
`rpm=1000`, `tpm=1_000_000`, `max_retries=6`, `timeout=120s`, `fail_fast_after=30`.
Every value is overridable by a CLI flag or a `SYCO_*` env var (see `.env.example`).
On the **Free** tier use `--concurrency 2 --rpm 5 --tpm 30000`.

## Error handling
Transient failures (429 "at capacity", 5xx, timeouts, connection drops) are
retried automatically with exponential backoff + jitter (honoring `Retry-After`).
A global AIMD governor widens spacing across all workers when Cerebras signals
saturation and relaxes it on recovery; token buckets keep request/token rates
under the tier limits. Terminal errors (bad key → abort run; malformed request →
fail item) are not retried. An item is written atomically only when it
terminates; an interrupted item leaves no record and is redone on `--resume`.

## Provider-agnostic
Cerebras today, OpenRouter later with **no code change** — only `--base-url`,
`--model`, `--api-key-var`, and `--max-tokens-param` differ (see `.env.example`).
