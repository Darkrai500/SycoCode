#!/usr/bin/env python3
"""Offline, stdlib-only audit of SycoCode's published snapshot and optional archive.

No provider calls, environment/credential reads, execution of corpus code, or
transcript text exports. Output is deterministic for fixed input bytes. Paths in
the JSON are relative to the named scope, never machine-specific absolute paths.
Exit 0: report generated (including findings); 2: invalid CLI/input.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

VERSION = "1.0.0"
RAW_NAMES = ("responses.jsonl", "runs.jsonl", "verdicts.jsonl", "vcr.jsonl", "analysis_tfg.json")
PARAM_KEYS = ("temperature", "top_p", "max_tokens", "seed", "reasoning_effort")
MODEL_KEYS = ("logical_name", "provider", "api_model_id")
SOURCE_NAMES = (
    "requirements-data.txt", "requirements-eval.txt", "config/models.json",
    "config/vcr_panel.lock.json", "config/pricing.json",
    "docs/methodology/phase_c_eval_schema.md", "docs/methodology/vcr_rubric.md",
    "docs/methodology/vcr_contracts.md", "data/goldset/PANEL_DECISION.md",
)
SCRIPT_NAMES = (
    "build_items.py", "build_problems.py", "build_scenarios.py", "verify_bugs.py",
    "download_sources.py", "analyze_full_corpus.py", "tfg_build_datapacks.py",
    "tfg_thesis_metrics.py", "tfg_sycoscore_experiments.py", "tfg_thesis_figures.py",
    "build_gold_pool.py", "export_gold.py", "eval_judge_vs_gold.py", "panel.py",
    "build_vcr_annotation_inputs.py", "aggregate_vcr_agent.py",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def unique(values):
    return [json.loads(x) for x in sorted({canonical(v) for v in values})]


def counts(values):
    return dict(sorted(Counter(str(x) for x in values).items()))


def select(row, keys):
    return {k: row[k] for k in keys if k in row}


def safe_input(path):
    # Validate before opening: a leaf or ancestor symlink could point outside
    # the explicit artifact trees. CLI roots themselves are already resolved.
    if path.is_symlink() or path.absolute() != path.resolve():
        raise ValueError("symlinked or redirected input is not supported")


def sha(path):
    safe_input(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    safe_input(path)
    if not path.is_file():
        return None
    try:
        if path.suffix == ".jsonl":
            rows = []
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"{path.name}:{n}: expected a JSON object")
                    rows.append(row)
            return rows
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        # Do not include source text in errors.
        raise ValueError(f"{path.name}: invalid JSON or UTF-8") from exc


def require(root, rel):
    value = load(root / rel)
    if value is None:
        raise ValueError(f"missing required input: {rel}")
    return value


def paths(root):
    """Explicit artifact allowlist; never traverse environment or credential files."""
    result = {root / p for p in SOURCE_NAMES}
    result.update(root / "scripts" / p for p in SCRIPT_NAMES)
    for pattern in (
        "eval/*.py", "schema/*.json", "data/raw/*/*.jsonl", "data/problems/*.json*",
        "data/goldset/*.json*", "data/goldset/prelabels_chunks/*.json*",
        "data/goldset/payloads/*.md", "data/runs/aggregates/*.json",
    ):
        result.update(root.glob(pattern))
    return sorted(p for p in result if p.is_file())


def inventory(root, selected):
    out = []
    for path in selected:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("symlinked or external input is not supported")
        rec = {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
               "sha256": sha(path)}
        if path.suffix in {".json", ".jsonl"}:
            value = load(path)
            rec["format"] = "jsonl" if path.suffix == ".jsonl" else "json"
            if isinstance(value, list):
                rec["rows"] = len(value)
            elif isinstance(value, dict):
                rec["top_level_keys"] = sorted(value)
        out.append(rec)
    return out


def duplicates(rows, fields):
    counter = Counter(tuple(row.get(k) for k in fields) for row in rows)
    return {"duplicate_keys": sum(n > 1 for n in counter.values()),
            "extra_rows": sum(n - 1 for n in counter.values() if n > 1),
            "missing_key_rows": sum(any(row.get(k) is None for k in fields) for row in rows)}


def compare_sets(actual, expected):
    return {"expected": len(expected), "observed_unique": len(actual),
            "missing_count": len(expected - actual), "unexpected_count": len(actual - expected)}


def date_range(values):
    vals = sorted(v for v in values if isinstance(v, str) and v)
    return {"first": vals[0] if vals else None, "last": vals[-1] if vals else None}


def is_dated(model):
    return isinstance(model, str) and bool(re.search(r"(?:19|20)\d{2}-?\d{2}-?\d{2}(?:$|[^0-9])", model))


def pressure_turns(item):
    if item.get("scenario_family") == "control":
        return []
    n = len(item.get("rendered_prompts", {}).get("turns", []))
    return [1] if n == 1 else list(range(2, n + 1))


def audit_dataset(root):
    items = require(root, "data/problems/items.jsonl")
    problems = require(root, "data/problems/problems.jsonl")
    scenarios = require(root, "data/problems/scenarios.jsonl")
    pids = {p.get("problem_id") for p in problems}
    sids = {s.get("scenario_id") for s in scenarios}
    bad_hash = 0
    for item in items:
        payload = {k: v for k, v in item.items() if k != "content_hash"}
        calculated = "sha256:" + hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        bad_hash += item.get("content_hash") != calculated
    report = {
        "items": len(items), "problems": len(problems), "scenarios": len(scenarios),
        "bugs": sum(len(p.get("bugs", [])) for p in problems),
        "by_language": counts(i.get("language") for i in items),
        "by_scenario": counts(i.get("scenario_ref") for i in items),
        "by_schema_version": counts(i.get("schema_version") for i in items),
        "prompt_turns": sum(len(i.get("rendered_prompts", {}).get("turns", [])) for i in items),
        "expected_vcr_turns": sum(len(pressure_turns(i)) for i in items),
        "items_sha256": sha(root / "data/problems/items.jsonl"),
        "duplicate_items": duplicates(items, ("item_id",)),
        "duplicate_problems": duplicates(problems, ("problem_id",)),
        "duplicate_scenarios": duplicates(scenarios, ("scenario_id",)),
        "content_hash_mismatches": bad_hash,
        "unknown_problem_refs": sum(i.get("problem_ref") not in pids for i in items),
        "unknown_scenario_refs": sum(i.get("scenario_ref") not in sids for i in items),
        "hash_algorithm": "SHA-256 of json.dumps(item without content_hash, ensure_ascii=False, sort_keys=True), default separators",
    }
    return report, {i["item_id"]: i for i in items}


def audit_gold(root, item_ids):
    gold = require(root, "data/goldset/gold.jsonl")
    pool = require(root, "data/goldset/pool.jsonl")
    votes = require(root, "data/goldset/votes.jsonl")
    key = lambda row: (row.get("record_id"), row.get("judged_turn"))
    expected = {key(row) for row in gold}
    configurations = unique(select(v, ("judge_model", "judge_provider", "protocol", "rubric_version")) for v in votes)
    return {
        "gold_rows": len(gold), "pool_rows": len(pool), "vote_rows": len(votes),
        "label_sources": counts(g.get("label_source") for g in gold),
        "labels": counts(g.get("gold_label") for g in gold),
        "gold_duplicate_units": duplicates(gold, ("record_id", "judged_turn")),
        "pool_duplicate_units": duplicates(pool, ("record_id", "judged_turn")),
        "vote_duplicate_units": duplicates(votes, ("record_id", "judged_turn", "judge_model", "protocol")),
        "pool_to_gold": compare_sets({key(p) for p in pool}, expected),
        "gold_unknown_items": sum(g.get("item_id") not in item_ids for g in gold),
        "judge_configurations": configurations,
        "vote_coverage": [{"judge_model": c["judge_model"], "protocol": c["protocol"],
                           **compare_sets({key(v) for v in votes if v.get("judge_model") == c["judge_model"] and v.get("protocol") == c["protocol"]}, expected)}
                          for c in configurations],
        "vote_dates": date_range(v.get("judged_at") for v in votes),
        "pool_sampling": select(require(root, "data/goldset/pool_manifest.json"), ("created_at", "rubric_version", "seeds", "per_stratum")),
        "qualification": "Gold label sources are counted from rows; proxy labels are not human ground truth.",
    }


def run_audit(base, slug, items, dataset_sha, pack, lock):
    folder = base / "data/runs" / slug
    rows = {name: load(folder / name) for name in RAW_NAMES}
    available = [name for name, value in rows.items() if value is not None]
    result = {"directory": f"data/runs/{slug}", "available_artifacts": available,
              "missing_artifacts": [n for n in RAW_NAMES if n not in available]}
    if not available:
        result["verification"] = "unavailable: aggregate claims do not establish raw coverage"
        return result
    responses, events, verdicts, vcr = (rows[n] or [] for n in RAW_NAMES[:4])
    rids = {r.get("record_id") for r in responses}
    itemids = {r.get("item_id") for r in responses}
    expected_items = set(items)
    expected_vcr = {(r.get("record_id"), t) for r in responses for t in pressure_turns(items.get(r.get("item_id"), {}))}
    by_id = {r.get("record_id"): r for r in responses}
    turns = [t for r in responses for t in r.get("transcript", [])]
    run_ids = sorted({r.get("run_id") for r in responses} | {r.get("run_id") for r in events})
    models = unique(select(r.get("model") or {}, MODEL_KEYS) for r in responses)
    returned = counts((t.get("provider_meta") or {}).get("model_returned") for t in turns)
    event_runs = []
    for run_id in run_ids:
        rr = [r for r in responses if r.get("run_id") == run_id]
        ee = [e for e in events if e.get("run_id") == run_id]
        event_runs.append({
            "run_id": run_id, "response_rows": len(rr),
            "events": [select(e, ("event", "status", "started_at", "updated_at", "finished_at", "counts", "scope_item_count", "concurrency", "schema_version", "harness_version", "git_commit")) for e in ee],
            "models": unique(select(r.get("model") or {}, MODEL_KEYS) for r in rr + ee),
            "request_params": unique(select(r.get("request_params") or {}, PARAM_KEYS) for r in rr + ee),
            "dataset_hashes": unique((e.get("dataset") or {}).get("items_dataset_hash") for e in ee),
            "response_dates": date_range([r.get("started_at") for r in rr] + [r.get("completed_at") for r in rr]),
            "response_schema_versions": counts(r.get("schema_version") for r in rr),
            "response_harness_versions": counts(r.get("harness_version") for r in rr),
            "response_git_commits": counts(r.get("git_commit") for r in rr),
        })
    hash_mismatch = sum(r.get("item_content_hash") != items[r["item_id"]].get("content_hash") for r in responses if r.get("item_id") in items)
    prompt_mismatch = 0
    for r in responses:
        item = items.get(r.get("item_id"))
        if item is None:
            continue
        prompt_mismatch += r.get("system_prompt") != item.get("rendered_prompts", {}).get("system")
        expected = {p["turn"]: p["content"] for p in item.get("rendered_prompts", {}).get("turns", [])}
        for t in r.get("transcript", []):
            messages = t.get("user_messages") or []
            last_user = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), None)
            prompt_mismatch += last_user != expected.get(t.get("turn"))
    fixed = lock.get("judges", [])[:2]
    pilot_tiebreak = "deepseek/deepseek-v4-pro-20260423"
    allowed_judges = set(fixed + ([pilot_tiebreak] if slug == "full" else lock.get("judges", [])[2:]))
    actual_votes = [v for row in vcr for v in row.get("votes", [])]
    report_params = unique(select(r.get("request_params") or {}, PARAM_KEYS) for r in responses)
    result.update({
        "verification": "local raw artifacts inspected; no provider calls",
        "rows": {n: len(rows[n] or []) for n in RAW_NAMES[:4]},
        "runs": event_runs, "models_requested": models,
        "requested_id_status": [{"id": m.get("api_model_id"), "date_qualified": is_dated(m.get("api_model_id")), "qualification": "A dated name is evidence of naming, not a guarantee of immutable weights."} for m in models],
        "returned_model_ids_per_turn": returned,
        "returned_id_date_qualified": {k: is_dated(k) for k in returned},
        "actual_backend": {"qualification": "Routing provider is recorded in model.provider; backend provider is not inferred from model name or API route.", "recorded_turns": sum(any((t.get("provider_meta") or {}).get(k) for k in ("provider", "backend_provider", "provider_name")) for t in turns), "total_turns": len(turns), "recorded_values": unique(select(t.get("provider_meta") or {}, ("provider", "backend_provider", "provider_name")) for t in turns if any((t.get("provider_meta") or {}).get(k) for k in ("provider", "backend_provider", "provider_name")))},
        "request_params": report_params,
        "seed": {"recorded_values": unique((r.get("request_params") or {}).get("seed") for r in responses), "records_missing_seed": sum("seed" not in (r.get("request_params") or {}) for r in responses), "qualification": "Recorded request configuration, not proof of provider enforcement or a systematic multi-seed experiment."},
        "metadata_gaps": {
            "records_missing_reasoning_effort": sum("reasoning_effort" not in (r.get("request_params") or {}) for r in responses),
            "records_missing_or_unknown_git_commit": sum(r.get("git_commit") in (None, "", "unknown") for r in responses),
            "turns_missing_model_returned": sum(not (t.get("provider_meta") or {}).get("model_returned") for t in turns),
            "turns_missing_system_fingerprint": sum(not (t.get("provider_meta") or {}).get("system_fingerprint") for t in turns),
            "event_runs_without_retained_responses": [e["run_id"] for e in event_runs if e["response_rows"] == 0],
        },
        "integrity": {
            "duplicate_responses": duplicates(responses, ("record_id",)),
            "duplicate_items_across_responses": duplicates(responses, ("item_id",)),
            "duplicate_verdicts": duplicates(verdicts, ("record_id",)),
            "duplicate_vcr": duplicates(vcr, ("record_id", "judged_turn")),
            "item_coverage": compare_sets(itemids, expected_items),
            "verdict_response_coverage": compare_sets({v.get("record_id") for v in verdicts}, rids),
            "vcr_pressure_turn_coverage": compare_sets({(v.get("record_id"), v.get("judged_turn")) for v in vcr}, expected_vcr),
            "record_id_formula_mismatches": sum(r.get("record_id") != f"{r.get('run_id')}::{r.get('item_id')}" for r in responses),
            "item_content_hash_mismatches": hash_mismatch,
            "prompt_component_mismatches": prompt_mismatch,
            "run_dataset_hash_mismatches": sum((e.get("dataset") or {}).get("items_dataset_hash") != "sha256:" + dataset_sha for e in events),
            "response_runs_without_events": len({r.get("run_id") for r in responses} - {e.get("run_id") for e in events}),
            "response_event_params_mismatches": sum(not any(e.get("run_id") == r.get("run_id") and select(e.get("request_params") or {}, PARAM_KEYS) == select(r.get("request_params") or {}, PARAM_KEYS) for e in events) for r in responses),
            "response_event_model_mismatches": sum(not any(e.get("run_id") == r.get("run_id") and select(e.get("model") or {}, MODEL_KEYS) == select(r.get("model") or {}, MODEL_KEYS) for e in events) for r in responses),
            "response_facet_mismatches": sum(select(r, ("problem_ref", "bug_ref", "scenario_ref", "scenario_family", "language", "original_id", "source", "harness_kind")) != select(items[r["item_id"]], ("problem_ref", "bug_ref", "scenario_ref", "scenario_family", "language", "original_id", "source", "harness_kind")) for r in responses if r.get("item_id") in items),
            "response_turn_count_mismatches": sum(r.get("turns_executed") != len(r.get("transcript", [])) or len(r.get("transcript", [])) != len(items.get(r.get("item_id"), {}).get("rendered_prompts", {}).get("turns", [])) for r in responses),
            "verdict_item_link_mismatches": sum(v.get("item_id") != by_id[v["record_id"]].get("item_id") for v in verdicts if v.get("record_id") in by_id),
            "vcr_item_link_mismatches": sum(v.get("item_id") != by_id[v["record_id"]].get("item_id") for v in vcr if v.get("record_id") in by_id),
        },
        "statuses": counts(r.get("status") for r in responses),
        "assistant_turns": len(turns),
        "finish_reasons": counts((t.get("assistant") or {}).get("finish_reason") for t in turns),
        "empty_assistant_turns": sum(not (t.get("assistant") or {}).get("content") for t in turns),
        "verdicts": {"schema_versions": counts(v.get("schema_version") for v in verdicts), "harness_versions": counts((v.get("verdict_meta") or {}).get("harness_version") for v in verdicts), "dates": date_range((v.get("verdict_meta") or {}).get("judged_at") for v in verdicts)},
        "vcr": {"schema_versions": counts(v.get("schema_version") for v in vcr), "rubric_versions": counts(v.get("rubric_version") for v in vcr), "protocols": counts(v.get("protocol") for v in vcr), "judge_providers": counts(v.get("judge_provider") for v in vcr), "panel_sources": counts(v.get("panel_source") for v in vcr), "judges": counts(v.get("judge_model") for v in actual_votes), "dates": date_range(v.get("judged_at") for v in vcr), "pilot_panel_exception": slug == "full", "unexpected_judge_votes": sum(v.get("judge_model") not in allowed_judges for v in actual_votes), "fixed_pair_mismatches": sum(v.get("panel", [])[:2] != fixed for v in vcr), "labels": counts(v.get("label") for v in vcr)},
        "aggregate_cross_checks": {
            "pack_analysis_equals_archive_analysis": pack.get("analysis") == rows["analysis_tfg.json"] if rows["analysis_tfg.json"] is not None else None,
            "pack_record_count_matches": pack.get("analysis", {}).get("overview", {}).get("records") == len(responses),
            "pack_vcr_count_matches": pack.get("vcr_all_turns", {}).get("n") == len(vcr),
            "pack_vcr_label_counts_match": all(pack.get("vcr_all_turns", {}).get(label) == sum(v.get("label") == label for v in vcr) for label in ("firm", "hedged", "capitulated")),
        },
    })
    return result


def build(root, archive):
    dataset, items = audit_dataset(root)
    models = require(root, "config/models.json").get("models", [])
    lock = require(root, "config/vcr_panel.lock.json")
    slugs = sorted(m.get("dir", m["slug"]) for m in models)
    if len(slugs) != len(set(slugs)) or not slugs or any(not re.fullmatch(r"[a-z0-9-]+", slug) for slug in slugs):
        raise ValueError("model registry has duplicate, empty or invalid run directories")
    selected = paths(root)
    for slug in slugs:
        selected.extend(root / "data/runs" / slug / n for n in RAW_NAMES if (root / "data/runs" / slug / n).is_file())
    published_inventory = inventory(root, sorted(set(selected)))
    registry = [{**select(m, ("slug", "display_name", "provider", "api_model_id", "dir")),
                 "last_validation_not_run_evidence": select(m.get("last_validated") or {}, ("at", "ok", "model_returned"))} for m in models]
    output = {
        "audit_schema_version": VERSION,
        "scope": {"published_snapshot": "root", "local_archive_supplied": archive is not None,
                  "inventory": "Explicit dataset, gold, configuration, harness, analysis and model-run allowlist; no credentials, environment or response text exported.",
                  "determinism": "No wall-clock timestamps, file mtimes, absolute paths or mutable git state.",
                  "limits": "Checks are integrity and provenance checks, not full JSON Schema validation, independent metric validation, or a claim of bitwise provider reproducibility."},
        "published_inventory": published_inventory,
        "dataset": dataset, "gold": audit_gold(root, set(items)),
        "model_registry_current_snapshot": registry,
        "vcr_lock_current_snapshot": select(lock, ("schema_version", "locked_at", "protocol", "judges", "judge_provider", "reasoning_effort", "aggregation")),
        "models": [],
    }
    for slug in slugs:
        pack = require(root, f"data/runs/aggregates/{slug}_pack.json")
        entry = {"slug": slug, "published_aggregate_metadata": select(pack, ("display_name", "provider", "api_model_id", "reasoning_effort", "verdicts_source")),
                 "aggregate_metadata_qualification": "Aggregate-script declarations; do not substitute for recorded per-run request metadata.",
                 "published": run_audit(root, slug, items, dataset["items_sha256"], pack, lock)}
        if archive:
            entry["archive"] = run_audit(archive, slug, items, dataset["items_sha256"], pack, lock)
        output["models"].append(entry)
    if archive:
        archive_paths = [archive / "data/runs" / slug / name for slug in slugs for name in RAW_NAMES if (archive / "data/runs" / slug / name).is_file()]
        common = [p["path"] for p in published_inventory if (archive / p["path"]).is_file() and not p["path"].startswith("data/runs/")]
        output["archive_inventory"] = inventory(archive, sorted(set(archive_paths + [archive / p for p in common])))
        archived_hashes = {a["path"]: a["sha256"] for a in output["archive_inventory"]}
        output["snapshot_vs_archive"] = {
            "matching_files": [p["path"] for p in published_inventory if archived_hashes.get(p["path"]) == p["sha256"]],
            "different_files": [p["path"] for p in published_inventory if p["path"] in archived_hashes and archived_hashes[p["path"]] != p["sha256"]],
            "qualification": "Current file equality does not prove these were the source files used by a historical run.",
        }
        manifest = require(root, "data/goldset/pool_manifest.json")
        frame_hash = archived_hashes.get("data/runs/full/responses.jsonl")
        output["gold"]["pool_frame_hash_matches_retained_pilot"] = manifest.get("frame", {}).get("sha256") == frame_hash if frame_hash else None
    output["summary"] = {
        "models": len(slugs), "published_artifact_files": len(published_inventory),
        "models_with_published_responses": sum("responses.jsonl" in m["published"]["available_artifacts"] for m in output["models"]),
        "models_with_archive_responses": sum("responses.jsonl" in m.get("archive", {}).get("available_artifacts", []) for m in output["models"]),
        "archive_response_rows": sum(m.get("archive", {}).get("rows", {}).get("responses.jsonl", 0) for m in output["models"]),
        "archive_verdict_rows": sum(m.get("archive", {}).get("rows", {}).get("verdicts.jsonl", 0) for m in output["models"]),
        "archive_vcr_rows": sum(m.get("archive", {}).get("rows", {}).get("vcr.jsonl", 0) for m in output["models"]),
    }
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Published repository root")
    parser.add_argument("--archive-root", type=Path, help="Optional local experiment archive; read-only")
    parser.add_argument("--output", type=Path, required=True, help="JSON report; must be outside all artifact input directories")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    archive = args.archive_root.resolve() if args.archive_root else None
    destination = args.output.resolve()
    try:
        for source in (root, archive):
            if source is None:
                continue
            if not source.is_dir():
                raise ValueError("input root must be an existing directory")
            for name in ("data", "config", "schema", "eval", "scripts"):
                if destination.is_relative_to(source / name):
                    raise ValueError("--output must be outside artifact input directories")
        if destination.exists():
            raise ValueError("--output already exists; choose a new report path")
        result = build(root, archive)
        # The report may be written inside docs or outside the checkout; inputs are untouched.
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
        print(json.dumps(result["summary"], sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"audit error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
