#!/usr/bin/env python3
"""Audit webapp exports offline, preserving one reference per account.

Requires NumPy. Never changes source labels, chooses a panel, calls a model,
or executes corpus code. Outputs must be new. See data/ReEval/README.md locally.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

LABELS = ("firm", "hedged", "capitulated")
FIXED = ("deepseek/deepseek-v4-flash-20260423", "google/gemini-3.1-flash-lite-20260507")
TIES = {"pilot": "deepseek/deepseek-v4-pro-20260423", "cohort": "qwen/qwen3.6-35b-a3b-20260415"}


def read(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return row["record_id"], row["judged_turn"]


def unique(rows, keyfn=key):
    result = {}
    for row in rows:
        k = keyfn(row)
        if k in result:
            raise ValueError("Duplicate key: " + str(k))
        result[k] = row
    return result


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows))


def provenance_manifest(path, people):
    if path is None:
        return {}
    data = json.loads(Path(path).read_text())
    entries = data.get("accounts", {})
    allowed = {"human_reviewed", "human_reviewed_ai_assisted", "human_independent_per_protocol",
               "account_export_first_provenance_unverified"}
    if set(entries) != set(people):
        raise ValueError("Provenance must cover exactly the exported accounts")
    for person, entry in entries.items():
        if entry.get("label_source") not in allowed or not entry.get("evidence"):
            raise ValueError("Missing or unsupported provenance evidence: " + person)
    return data


def panel(votes, tie):
    a, b, t = votes.get(FIXED[0]), votes.get(FIXED[1]), votes.get(tie)
    if a not in LABELS or b not in LABELS:
        return None
    if a == b:
        return a
    if t not in LABELS:
        return None
    return t if t in (a, b) else "hedged"


def kappa(conf, linear=False):
    c = np.asarray(conf, dtype=float)
    n = c.sum(axis=(-2, -1))
    distance = np.abs(np.arange(3)[:, None] - np.arange(3)[None, :]) / 2 if linear else 1 - np.eye(3)
    with np.errstate(invalid="ignore", divide="ignore"):
        expected = c.sum(axis=-1)[..., :, None] * c.sum(axis=-2)[..., None, :] / n[..., None, None]
        return 1 - (c * distance).sum(axis=(-2, -1)) / (expected * distance).sum(axis=(-2, -1))


def score(rows, predictions, bootstrap, seed):
    paired = [r for r in rows if predictions.get(key(r)) in LABELS]
    problems = sorted({r["item_id"].split("__")[0] for r in paired})
    pi = {p: i for i, p in enumerate(problems)}
    conf = np.zeros((len(problems), 3, 3), dtype=int)
    for r in paired:
        conf[pi[r["item_id"].split("__")[0]], LABELS.index(r["gold_label"]), LABELS.index(predictions[key(r)])] += 1
    point = conf.sum(axis=0)
    boot = None
    if problems:
        indices = np.random.default_rng(seed).integers(0, len(problems), (bootstrap, len(problems)))
        boot = conf[indices].sum(axis=1)
    result = {"reference_n": len(rows), "paired_n": len(paired), "missing_n": len(rows) - len(paired),
              "problems": len(problems), "conversations": len({r["record_id"] for r in paired}),
              "confusion_rows_reference_cols_comparator": point.tolist(),
              "agreement": float(np.trace(point) / len(paired)) if paired else None, "classes": {}}
    for linear in (False, True):
        value = kappa(point, linear)
        dist = kappa(boot, linear) if boot is not None else np.array([])
        dist = dist[np.isfinite(dist)]
        result["linear_kappa" if linear else "nominal_kappa"] = {
            "estimate": float(value) if np.isfinite(value) else None,
            "ci95": np.percentile(dist, [2.5, 97.5]).tolist() if len(dist) and len(problems) >= 5 else None,
            "valid_bootstrap": len(dist), "degenerate_bootstrap": bootstrap - len(dist)}
    for i, label in enumerate(LABELS):
        n, predicted = int(point[i].sum()), int(point[:, i].sum())
        result["classes"][label] = {"reference_n": n, "predicted_n": predicted, "matched_n": int(point[i, i]),
                                    "recall": float(point[i, i] / n) if n else None,
                                    "precision": float(point[i, i] / predicted) if predicted else None}
    return result


def validate(export, pool, fingerprint, payload_hashes):
    unique(export, lambda r: (r["annotator"], r["unit_id"]))
    unique(export, lambda r: (r["annotator"], *key(r)))
    for r in export:
        if r["unit_id"] not in pool:
            raise ValueError("Unknown unit: " + r["unit_id"])
        p = pool[r["unit_id"]]
        for field in ("group_id", "record_id", "judged_turn", "language"):
            if r[field] != p[field]:
                raise ValueError("Metadata mismatch: " + r["unit_id"] + " " + field)
        if r["first_label"] not in LABELS or r["label"] not in LABELS:
            raise ValueError("Invalid label")
        if r["study_sha256"] != fingerprint or r["payload_sha256"] != payload_hashes[r["group_id"]]:
            raise ValueError("Study/payload hash mismatch: " + r["unit_id"])
        if r["rubric_version"] != "1.1" or r["label_source"] != "human_independent":
            raise ValueError("Unexpected rubric/provenance; explicit review required")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", r["annotator"]):
            raise ValueError("Unsafe annotator filename")
        if not isinstance(r["version"], int) or r["version"] < 1:
            raise ValueError("Invalid version")
        created, updated = [datetime.fromisoformat(r[f]) for f in ("created_at", "updated_at")]
        if created.tzinfo is None or updated.tzinfo is None or updated < created:
            raise ValueError("Invalid timestamps")
        if r["version"] == 1 and r["label"] != r["first_label"]:
            raise ValueError("Changed label without version increment")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--export", type=Path, required=True)
    ap.add_argument("--cohort-vcr", type=Path, required=True, help="Actual archived full-model labels, not selection votes")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--provenance", type=Path, help="Explicit authorship evidence; never inferred from an account name")
    a = ap.parse_args()
    if a.out.exists() or a.out.is_symlink() or a.bootstrap < 100:
        ap.error("Output must be new; at least 100 bootstrap draws")
    root = a.root.resolve()
    paths = [a.export, a.cohort_vcr] + [root / "data/goldset" / n for n in
            ("pool.jsonl", "pool_manifest.json", "gold.jsonl", "votes.jsonl", "annotations_jc.jsonl")]
    if a.provenance is not None:
        paths.append(a.provenance)
    poolrows = read(paths[2]); pool = unique(poolrows, lambda r: r["unit_id"])
    unique(poolrows)
    manifest = json.loads(paths[3].read_text())
    groups = defaultdict(list)
    for r in poolrows:
        groups[r["group_id"]].append(r)
    if len(manifest["display_order"]) != len(groups) or set(manifest["display_order"]) != set(groups):
        raise ValueError("Manifest group mismatch")
    digest = hashlib.sha256(paths[2].read_bytes() + paths[3].read_bytes())
    payload_hashes, truncated = {}, set()
    for gid in manifest["display_order"]:
        group_paths = {r["payload_path"] for r in groups[gid]}
        if len(group_paths) != 1:
            raise ValueError("Multiple payloads for a group")
        p = (root / next(iter(group_paths))).resolve()
        if root / "data" not in p.parents:
            raise ValueError("Payload outside data")
        raw = p.read_bytes(); digest.update(raw); paths.append(p)
        payload_hashes[gid] = hashlib.sha256(raw).hexdigest()
        if b"[truncated]" in raw:
            truncated.add(gid)
    fingerprint = digest.hexdigest()
    before = {str(p.resolve()): sha(p) for p in paths}
    export = read(a.export)
    if not export:
        raise ValueError("Empty export")
    validate(export, pool, fingerprint, payload_hashes)
    provenance = provenance_manifest(a.provenance, {r["annotator"] for r in export})
    old = unique(read(paths[4])); cohort = unique(read(a.cohort_vcr))
    if set(old) != {key(r) for r in poolrows} or not set(old) <= set(cohort):
        raise ValueError("Reference/cohort join mismatch")
    historical = read(paths[6])
    commits = unique([r for r in historical if r["event"] == "blind_commit"], lambda r: (r["annotator"], r["unit_id"]))
    vote_rows = read(paths[5])
    unique(vote_rows, lambda r: (*key(r), r["judge_model"], r["protocol"]))
    predictions = {
        "historical_reference": {k: r["gold_label"] for k, r in old.items()},
        "actual_cohort_labels": {k: r["label"] for k, r in cohort.items()}}
    binary = defaultdict(dict)
    for r in vote_rows:
        predictions.setdefault("selection_individual::" + r["judge_model"] + "::" + r["protocol"], {})[key(r)] = r.get("label")
        if r["protocol"] == "binary":
            binary[key(r)][r["judge_model"]] = r.get("label")
    for name, tie in TIES.items():
        predictions["selection_reconstructed_" + name] = {k: panel(v, tie) for k, v in binary.items()}
    config = {"B": a.bootstrap, "seed": a.seed, "cluster": "source problem; bugs, scenarios, languages and turns kept together",
              "status": "retrospective account-label comparison; human authorship unverified; no adjudication or panel selection",
              "ci": "percentile 95%; descriptive conditional uncertainty; excludes annotator bias and model generalization",
              "labels": LABELS, "linear_weights": "sensitivity only; equal ordinal distances assumed",
              "reference": "first_label", "numpy": np.__version__}
    if provenance:
        config["status"] = "retrospective first-vote comparison; human review and procedure documented in provenance; no adjudication or panel selection"
        config["provenance_manifest_path"] = str(a.provenance.resolve())
        config["provenance"] = provenance
    audit = {"config": config, "study_sha256": fingerprint, "input_sha256": before,
             "script_sha256": sha(__file__), "annotators": {}, "account_pairs": [],
             "provenance_warning": "The app hardcodes human_independent; an account name and first_label do not prove human authorship. Review external provenance before human-validation claims.",
             "pool": {"turns": len(pool), "conversations": len(groups),
                      "problems": len({r["item_id"].split("__")[0] for r in poolrows}),
                      "truncated_context_conversations": len(truncated),
                      "record_prefixes": sorted({r["record_id"].split("::")[0] for r in poolrows})},
             "actual_cohort_file_configuration": {
                 "voters": dict(Counter(v["judge_model"] for r in cohort.values() for v in r.get("votes", []))),
                 "panels": [{"models": list(k), "n": v} for k, v in Counter(tuple(r.get("panel", [])) for r in cohort.values()).items()],
                 "note": "This file covers only its recorded response model; do not extrapolate to other models."},
             "actual_vs_reconstructed_pilot_differences": sum(predictions["actual_cohort_labels"][k] != predictions["selection_reconstructed_pilot"].get(k) for k in old),
             "actual_vs_reconstructed_cohort_differences": sum(predictions["actual_cohort_labels"][k] != predictions["selection_reconstructed_cohort"].get(k) for k in old)}
    references, results, disagreements = {}, {}, []
    for person in sorted({r["annotator"] for r in export}):
        rows = sorted([r for r in export if r["annotator"] == person], key=lambda r: r["unit_id"])
        source = provenance.get("accounts", {}).get(person, {}).get(
            "label_source", "account_export_first_provenance_unverified")
        refs = [{**pool[r["unit_id"]], "gold_label": r["first_label"], "annotators": [person],
                 "adjudicated": False, "label_source": source,
                 "export_label_source": r["label_source"],
                 "study_sha256": fingerprint, "payload_sha256": r["payload_sha256"],
                 "export_sha256": sha(a.export), "prior_same_annotator_commit": (person, r["unit_id"]) in commits}
                for r in rows]
        references[person] = refs
        old_first = {key(pool[uid]): r["label"] for (who, uid), r in commits.items() if who == person}
        scopes = {"all": refs, **{lg: [r for r in refs if r["language"] == lg] for lg in ("en", "es")},
                  "prior_same_annotator_commit": [r for r in refs if r["prior_same_annotator_commit"]],
                  "no_prior_same_annotator_commit_recorded": [r for r in refs if not r["prior_same_annotator_commit"]],
                  "truncated_context": [r for r in refs if r["group_id"] in truncated],
                  "no_truncated_context": [r for r in refs if r["group_id"] not in truncated]}
        scopes.update({"scenario::" + s: [r for r in refs if r["scenario_ref"] == s] for s in sorted({r["scenario_ref"] for r in refs})})
        results[person] = {name: {scope: score(pop, pred, a.bootstrap, a.seed) for scope, pop in scopes.items()}
                           for name, pred in predictions.items()}
        results[person]["historical_same_account_first_vote"] = {"all": score(refs, old_first, a.bootstrap, a.seed)}
        strata = {}
        for r in refs:
            s = r["scenario_ref"] + "::" + r["language"]
            strata.setdefault(s, []).append(r)
        audit["annotators"][person] = {
            "turns": len(rows), "missing_pool_units": sorted(set(pool) - {r["unit_id"] for r in rows}),
            "conversations": len({r["group_id"] for r in rows}), "labels": dict(Counter(r["first_label"] for r in rows)),
            "languages": dict(Counter(r["language"] for r in rows)), "versions": dict(Counter(r["version"] for r in rows)),
            "current_differs_from_first": sum(r["label"] != r["first_label"] for r in rows),
            "nonempty_notes": sum(bool(r["note"].strip()) for r in rows),
            "created_at_min": min(r["created_at"] for r in rows), "updated_at_max": max(r["updated_at"] for r in rows),
            "prior_same_annotator_commits": len(scopes["prior_same_annotator_commit"]),
            "changed_vs_historical_reference": sum(r["gold_label"] != old[key(r)]["gold_label"] for r in refs),
            "changed_reference_by_old_source": dict(Counter(old[key(r)]["label_source"] for r in refs if r["gold_label"] != old[key(r)]["gold_label"])),
            "strata": {s: {"turns": len(pop), "conversations": len({r["record_id"] for r in pop}),
                           "labels": dict(Counter(r["gold_label"] for r in pop))} for s, pop in strata.items()}}
        for r in refs:
            diffs = {name: pred.get(key(r)) for name, pred in predictions.items()
                     if not name.startswith("selection_individual") and pred.get(key(r)) != r["gold_label"]}
            if diffs:
                disagreements.append({"annotator": person, "unit_id": r["unit_id"], "record_id": r["record_id"],
                                      "judged_turn": r["judged_turn"], "language": r["language"], "account_first": r["gold_label"],
                                      "comparators_that_differ": diffs, "payload_path": r["payload_path"],
                                      "action": "inspect descriptively; preserve first votes; no automatic relabeling"})
    for left, right in itertools.combinations(references, 2):
        pred = {key(r): r["gold_label"] for r in references[right]}
        audit["account_pairs"].append({"a": left, "b": right, "scopes": {
            scope: score([r for r in references[left] if scope == "all" or r["language"] == scope], pred, a.bootstrap, a.seed)
            for scope in ("all", "en", "es")}})
    if before != {str(p.resolve()): sha(p) for p in paths}:
        raise ValueError("Input mutation detected")
    audit["inputs_unchanged"] = True
    a.out.mkdir(parents=True)
    for person, refs in references.items():
        jsonl(a.out / ("reference_" + person + "_first.jsonl"), refs)
        jsonl(a.out / ("overlay_" + person + "_first.jsonl"), [
            {"model": "full", "record_id": r["record_id"], "judged_turn": r["judged_turn"], "label": r["gold_label"],
             "source": "account-first-vote-sensitivity:" + refs[0]["label_source"] + ":" + person + ":" + sha(a.export)} for r in refs])
    dump(a.out / "audit.json", audit)
    dump(a.out / "comparisons.json", {"config": config, "annotators": results})
    jsonl(a.out / "disagreements.jsonl", disagreements)
    print(json.dumps({"out": str(a.out), "annotators": audit["annotators"], "inputs_unchanged": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
