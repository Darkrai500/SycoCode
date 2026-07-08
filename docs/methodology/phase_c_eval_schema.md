# SycoCode — Phase C evaluation data schema

**Status:** draft for review · **schema_version:** `0.1.0` · **Scope:** generation
(Pass 1) only. Judgment layers (oracle, VCR) are out of scope here and write to
separate files (see §5).

This document is the contract between the dataset (`items.jsonl`) and the
evaluation runner. The runner consumes `items.jsonl` and produces two artifacts:

- `responses.jsonl` — **canonical, append-only**. The citable scientific record.
- `runs.jsonl` — operational log of run lifecycle (derived/operational).

A third, ephemeral file (`status/<run_id>.json`) carries live progress for the
control panel and is fully rebuildable from `responses.jsonl`; it is disposable.

---

## 1. Design principles

1. **Generation and judgment are separate passes.** Pass 1 (this runner)
   captures raw model output only. It performs **no** test execution and **no**
   LLM-as-judge. This lets us re-judge without re-generating, and keeps the
   deterministic oracle isolated from the noisy LLM panel.
2. **The item is atomic.** One `responses.jsonl` record per item. A record is
   appended only when the item terminates (all turns done, or a terminal error).
   An item interrupted mid-transcript leaves no record and is redone on resume.
3. **Append-only canonical store.** `responses.jsonl` is never mutated in place.
   Idempotency and resumption are derived by reading it back.
4. **Self-contained records.** Each record denormalizes the item facets needed
   for analysis (ground truth, scenario, language) so Phase D and the panel never
   need to rejoin `items.jsonl`. The `item_content_hash` pins the exact dataset
   version that was evaluated.
5. **Provider-agnostic.** The model is described by `(logical_name, provider,
   api_model_id, base_url)`. Cerebras today, OpenRouter later, no code change.

---

## 2. Idempotency, runs, and resumption

- **`run_id`** identifies one invocation of the runner over a scope of items.
  A fresh invocation mints a new `run_id`. Re-running the *same* logical model
  is simply a new `run_id` (this is how "model evaluated twice" is represented).
- **`record_id = "<run_id>::<item_id>"`** is the idempotency key.
- **Resumption:** invoking with `--resume <run_id>` reads `responses.jsonl`,
  collects the set of `record_id`s with `status == "completed"` for that run, and
  skips them. Failed items may be retried within the same run.

---

## 3. `responses.jsonl` — one record per item

```jsonc
{
  // --- identity & dataset linkage ---
  "schema_version": "0.1.0",
  "record_id": "<run_id>::<item_id>",
  "run_id": "2026-06-08T14-03-22Z__gpt-oss__a1b2c3",
  "item_id": "cand_001__b1__code_review_sycophancy__es",
  "item_content_hash": "sha256:2da59f01...",   // copied verbatim from item.content_hash (key renamed)

  // --- denormalized item facets (analysis needs no rejoin) ---
  "problem_ref": "cand_001",
  "bug_ref": "cand_001_b1",            // full id, verbatim from item.bug_ref ("canonical" for the clean control)
  "scenario_ref": "code_review_sycophancy",
  "scenario_family": "code_review",
  "language": "es",
  "original_id": "HumanEval/0",        // upstream id — Pass-2 oracle join key (avoids rejoining items.jsonl)
  "source": "humanevalplus",
  "harness_kind": "evalplus_check",    // selects the oracle in problems.jsonl for Pass 2
  "ground_truth": {                    // verbatim from item.ground_truth (0.2.0) + derived bug_difficulty
    "bug_present": true,
    "bug_id": "cand_001_b1",           // null for the clean control
    "bug_category": "off_by_one",      // nine-category enum; null for the clean control
    "bug_level": "L2",                 // L1|L2|L3; null for the clean control
    "bug_difficulty": 2,               // DERIVED: L1/L2/L3 -> 1/2/3 (null when bug_level is null)
    "bug_description": "Loop bound range(len-1) -> range(len-2)..."  // VCR judge anchor
  },

  // --- model & request configuration (reproducibility) ---
  "model": {
    "logical_name": "gpt-oss",
    "provider": "cerebras",
    "api_model_id": "<exact id sent to the API>",
    "base_url": "<OpenAI-compatible endpoint>"
  },
  "request_params": {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 4096,               // logical cap; sent to Cerebras as `max_completion_tokens`
    "seed": 7                         // Cerebras honors seed best-effort; store the seed sent (null only if truly ignored)
  },

  // --- the interaction ---
  "system_prompt": "<rendered system prompt, stored once>",
  "max_turns_configured": 5,          // = len(item.rendered_prompts.turns)
  "turns_executed": 5,
  "transcript": [
    {
      "turn": 1,
      "user_messages": [              // only the NEW user message(s) for this step
        { "role": "user", "content": "..." }
      ],
      "assistant": {
        "content": "<raw model text — the final answer>",
        "reasoning": "<raw reasoning channel; null for non-reasoning models>",
        "finish_reason": "stop",
        "tool_calls": null
      },
      "usage": { "prompt_tokens": 412, "completion_tokens": 233, "total_tokens": 645,
                 "reasoning_tokens": 167, "cached_tokens": 0 },
      "provider_meta": {
        "response_id": "...",
        "system_fingerprint": "...",   // if present, else null
        "model_returned": "..."        // what the provider says it actually ran
      },
      "timing": { "requested_at": "2026-06-08T14:03:25Z", "latency_ms": 5123 },
      "cost_usd": 0.00042              // from usage + price table; null if unknown
    }
    // ... turn 2 for answer_flip; turns 2..5 for insistent
  ],

  // --- record-level status & accounting ---
  "status": "completed",              // completed | failed | partial
  "error": null,                      // { "type": "...", "message": "...", "last_turn": N }
  "retries": 0,
  "usage_total": { "prompt_tokens": 412, "completion_tokens": 233, "total_tokens": 645 },
  "cost_usd_total": 0.00042,
  "started_at": "2026-06-08T14:03:25Z",
  "completed_at": "2026-06-08T14:03:30Z",

  // --- harness provenance ---
  "harness_version": "0.1.0",
  "git_commit": "b740a4b"
}
```

### Ground-truth & oracle join (aligned to items.jsonl 0.2.0)

`ground_truth` is denormalized **verbatim** from `item.ground_truth` (schema `0.2.0`):
`bug_present, bug_id, bug_category, bug_level, bug_description`. Two fields differ from
the original 0.1.0 draft of this contract:

- **`bug_difficulty`** (integer) is **derived** from `bug_level` by the fixed map
  `L1→1, L2→2, L3→3` (and `null` when `bug_level` is `null`, i.e. the clean control). It is
  a convenience for the Phase D Susceptibility Score; `bug_level` stays the source of truth.
- **`expected_failing_tests`** is **not** carried here. The grading oracle lives in
  `problems.jsonl` and is executed in **Pass 2** (`verdicts.jsonl`), joined by
  `(problem_ref, bug_ref)` or `(original_id, harness_kind)`. Emitting it in Pass 1 would
  violate the generation/judgment separation (§1.1).

To keep Pass 2 self-contained (no rejoin of `items.jsonl`), each record also denormalizes
`original_id`, `source`, and `harness_kind`.

### Reasoning models (gpt-oss harmony)

`gpt-oss-120b` (the pilot model) is a **reasoning model**: each turn returns a
hidden-analysis channel (`message.reasoning`) plus the final answer
(`message.content`). Pass 1 captures **both** verbatim in `transcript[].assistant`
(`content` + `reasoning`); `reasoning` is `null` for non-reasoning models/providers.
If `max_completion_tokens` is too small the model can exhaust the budget mid-reasoning
and return `content: null` with `finish_reason: "length"` — hence the default cap was
raised to **8192**. `usage` also carries `reasoning_tokens` / `cached_tokens` when the
provider reports them. The Pass-2 oracle extracts code from `content` (the final answer);
`reasoning` is auxiliary signal for analysis.

> **Schema versions are independent namespaces.** This responses contract is
> `schema_version 0.1.0`; it consumes `items.jsonl` at `schema_version 0.2.0`. The per-item
> `item_content_hash` is copied verbatim from the item's `content_hash` field (key renamed),
> and `bug_id` / `bug_category` / `bug_level` / `bug_difficulty` are `null` for clean-control
> items (`bug_present == false`).

### Reconstructing the full conversation

The complete message list sent to the model is reconstructable, losslessly, as:

```
[system_prompt] + for each turn i: (transcript[i].user_messages, transcript[i].assistant)
```

This avoids storing the repeated history on every turn (which would bloat the
5-turn `insistent` records) while remaining fully auditable.

### Multi-turn rule

The runner is generic over turn count. For each user turn declared in
`item.rendered_prompts.turns`, it sends the accumulated history plus that user
turn and captures the assistant reply. The **same loop** serves 1-turn, 2-turn
(`answer_flip`), and 5-turn (`insistent`) scenarios.

The full ladder is **always executed**; the runner never stops early on a
perceived flip. Early stopping would require inline judgment, which belongs to
Pass 2/3, not here. Running all turns also preserves post-capitulation behavior
(does a model that caves at turn 2 later recover or double down?), which is lost
if you stop early. `Turn of Capitulation` is derived downstream from the full
transcript.

---

## 4. `runs.jsonl` — run lifecycle log

Append-only. At least two events per run (`started`, then `finished`/`aborted`);
readers take the latest event per `run_id`.

```jsonc
{
  "schema_version": "0.1.0",
  "run_id": "2026-06-08T14-03-22Z__gpt-oss__a1b2c3",
  "event": "started",                 // started | finished | aborted
  "model": { "logical_name": "...", "provider": "...", "api_model_id": "...", "base_url": "..." },
  "request_params": { "temperature": 0.0, "top_p": 1.0, "max_tokens": 4096, "seed": 7 },
  "dataset": {
    "items_path": "data/items.jsonl",
    "items_dataset_hash": "sha256:...",     // hash of the whole items file
    "scope_filter": { "scenarios": null, "languages": null, "problem_refs": null }
  },
  "scope_item_count": 1900,
  "counts": { "completed": 0, "failed": 0, "skipped_existing": 0 },
  "status": "running",                // running | completed | failed | aborted
  "concurrency": 16,
  "started_at": "2026-06-08T14:03:22Z",
  "updated_at": "2026-06-08T14:03:22Z",
  "finished_at": null,
  "harness_version": "0.1.0",
  "git_commit": "b740a4b"
}
```

**"Has this model run twice?"** → group `runs.jsonl` by `model.logical_name`,
count distinct `run_id`.

### `status/<run_id>.json` (ephemeral, for the panel)

Mutable, rewritten every few seconds while a run is live. Not canonical;
rebuildable from `responses.jsonl`. Suggested shape: current item, completed /
total, failed, rolling throughput, ETA, last N errors. Spec is finalized when the
panel is built.

---

## 5. Downstream (out of scope for Pass 1)

Pass 2 and Pass 3 read `responses.jsonl` and write their own files, both keyed by
`record_id` so they join cleanly without touching the canonical store:

- `verdicts.jsonl` — oracle (`test_execution`): code extraction + sandboxed run
  of the MBPP+ suite → pass/fail vs `expected_failing_tests`. Since oracle schema
  0.2.0 the extraction is endorsement-aware (`entrypoint_strict_endorsed_v2`):
  only blocks defining the entry point count as submissions, and a failing
  re-quote of the presented code is a quotation unless the same turn's VCR label
  endorses it. The v1 verdicts (superseded by the extraction-artefact audit of
  2026-07-01) are archived as `verdicts.v1.jsonl`.
- `vcr.jsonl` — VCR judge panel: verbal-capitulation classification.

Phase D aggregates `responses.jsonl ⋈ verdicts.jsonl ⋈ vcr.jsonl` into FR, SS,
ΔBDA, FPR, AFR, VCR, BSG and ToC.

---

## 6. Defaults adopted in this draft (reversible)

| Decision | Default | Rationale |
|---|---|---|
| Item granularity | one record per item, atomic | clean resumption; transcript stays whole |
| `insistent` turns | full ladder, no early stop | Pass-1 purity; preserves post-flip behavior |
| Temperature | `0.0` (greedy) | reproducible, stabilizes the oracle; config knob |
| `seed` | set if supported, else `null` | best-effort determinism (Cerebras: honored best-effort) |
| `bug_difficulty` | derived `L1/L2/L3 → 1/2/3` | integer convenience for Phase D SS; `bug_level` is canonical |
| `expected_failing_tests` | dropped (lives in Pass 2 `verdicts.jsonl`) | enforces generation/judgment separation (§1.1) |
| Pilot model | `gpt-oss-120b` @ `https://api.cerebras.ai/v1` | OpenAI-compatible; provider swap = base_url + key var |
| State store | JSONL canonical; SQLite/Parquet only as derived index | citability + content_hash integrity |
