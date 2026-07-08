# Run monitoring

## Live monitoring

`scripts/panel.py` serves a local, zero-dependency "mission control" web panel for any
runner output directory (whatever you passed as `--out-dir` to the Pass-1 runner). It
reads only the artifacts the runner already writes — `status/<run_id>.json`,
`responses.jsonl`, `runs.jsonl` — and never modifies anything.

### Launch

```bash
# default: watches data/runs/full on http://127.0.0.1:8377/
.venv/bin/python scripts/panel.py

# any out-dir, custom port, auto-open browser
.venv/bin/python scripts/panel.py --runs-dir data/runs/pilot --port 8400 --open
```

The UI (served at `/`) shows a run list (newest first), a live progress bar, throughput
sparkline, scenario × language completion matrix, failures feed, and token/cost stat
cards. Cards backed by status-schema-v2 fields (tokens, cost, retries, requests) hide
themselves automatically when watching an old v1 status file. Polling is 2 s while the
run is live, slower otherwise, and pauses while the tab is hidden.

### Endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/runs` | All runs known from the status dir + `runs.jsonl`, newest first: `[{run_id, run_status, total, completed, failed, updated_at, age_seconds, model?}]`. `run_status` trusts only *terminal* v2 values (`finished`/`aborted`) — or a terminal `runs.jsonl` event; anything else (including a v2 `running` left behind by a killed runner) goes through the `updated_at` freshness check and decays to `stale` after 120 s. |
| `GET /api/status?run_id=X` | The raw status JSON (v1 or v2) plus derived `age_seconds`, `percent`, and resolved `run_status`. For runs known only from `runs.jsonl` (no status file) it synthesizes a minimal payload from the run's last event and marks it `"synthesized": true`; the UI shows a "no status file" note. |
| `GET /api/breakdown?run_id=X` | Aggregated from `responses.jsonl`: `by_scenario_language` (`"<scenario_ref>\|<language>" -> {completed, partial, failed}`), `failures` (last 50, newest first, messages clipped to 160 chars), and `totals` (`items, records, prompt_tokens, completion_tokens, cost_usd, retries`). Matrix counts and the failures feed are **last-record-wins per `record_id`** (a `--resume` re-attempt supersedes the earlier failed record, and a later success removes its stale failure entry), while `records` plus all token/cost/retry totals sum over every line including superseded attempts — failed attempts cost real tokens. `items` counts distinct `record_id`s. |
| `GET /api/meta` | `{runs_dir}` — shown in the panel header. |

`/api/breakdown` uses an incremental reader: it remembers a byte offset into
`responses.jsonl` and parses only newly appended bytes on each poll (in bounded 8 MB
chunks, so even a cold start against a huge backlog never loads the whole file at
once), so repeated calls during a multi-thousand-item run stay cheap. If the file
shrinks or its inode changes (rotated/truncated/replaced) it rebuilds from offset 0.

Unknown `run_id`s return a 404 JSON body. The server binds `127.0.0.1` by default and
never derives filesystem paths from request input.
