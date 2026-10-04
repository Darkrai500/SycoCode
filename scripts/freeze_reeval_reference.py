#!/usr/bin/env python3
"""Freeze/verify the 42+278 human reference; never calculate panel metrics.

All checks use saved evidence. No network, model calls or database mutations.
Individual records remain in the ignored private/ directory.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

LABELS = {"firm", "hedged", "capitulated"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def jsonl_bytes(rows):
    return b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n").encode() for r in rows)


def jsonl(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def unique(rows, key, name):
    result = {key(r): r for r in rows}
    require(len(result) == len(rows), f"Duplicate {name}")
    return result


def stamp(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def derive(root, folder):
    private = folder / "private"
    snap_path = private / "server-snapshot.json"
    baseline_path = private / "inputs/server-snapshot-2026-09-24.json"
    queue_path = private / "inputs/review_queue-2026-09-24.jsonl"
    gold_path = private / "inputs/historical-gold.jsonl"
    policy_path = root / "webapp/annotations/data/reeval_queue_manifest_2026-09-24.json"
    snapshot, baseline, policy = read(snap_path), read(baseline_path), read(policy_path)
    gold = unique(jsonl(gold_path.read_text()), lambda r: (r["record_id"], r["judged_turn"]), "historical key")
    original_queue = unique(jsonl(queue_path.read_text()), lambda r: r["unit_id"], "source queue unit")
    require(sha(queue_path) == policy["source_sha256"], "Original queue hash mismatch")
    require(snapshot["integrity_check"] == ["ok"] and snapshot["query_only"] == 1, "Read-only/integrity check failed")
    require(snapshot["connection_total_changes_before"] == snapshot["connection_total_changes_after"] == 0, "Exporter wrote to database")
    require(snapshot["annotation_state_sha256"] == policy["annotations_sha256"], "Frozen annotation digest mismatch")
    require(snapshot["source_release"].split("/")[-1] == "917eae557554c44fc6e7f460d9e84e3035a9ad18", "Unexpected source release")
    for name, expected in snapshot["application_source_sha256"].items():
        require(sha(root / "webapp/annotations" / name) == expected, f"Application source mismatch: {name}")
    require(baseline["integrity_check"] == ["ok"], "Historical snapshot integrity")
    require(len(baseline["studies"]) == 1 and baseline["studies"][0]["fingerprint"] == policy["study_sha256"], "Historical study mismatch")
    expected_counts = {"studies": 1, "conversations": 200, "units": 320,
                       "annotations": 640, "annotation_events": 651, "queue": 42, "decisions": 42}
    require(all(snapshot["counts"][k] == v for k, v in expected_counts.items()), "Incomplete closure")
    permissions = {r["username"]: r for r in snapshot["permissions"]}
    require(permissions["jc"] == {"username": "jc", "is_active": True, "is_staff": False,
                                  "is_superuser": False, "can_adjudicate": True}, "JC permissions changed")
    require(permissions["control"]["is_active"] and permissions["control"]["is_staff"]
            and not permissions["control"]["can_adjudicate"], "Control role mismatch")
    exports = {}
    for name, expected_count in [("adjudications", 42), ("reference_candidate", 320)]:
        export = snapshot["exports"][name]
        require(export["status_code"] == 200, f"Export failed: {name}")
        require(hashlib.sha256(export["jsonl"].encode()).hexdigest() == export["sha256"], "Export digest mismatch")
        rows = jsonl(export["jsonl"])
        require(len(rows) == expected_count, f"Incomplete {name}")
        exports[name] = unique(rows, lambda r: r["unit_id"], name)
    adjudications, candidates = exports["adjudications"], exports["reference_candidate"]
    units = unique(snapshot["units"], lambda r: r["unit_id"], "unit")
    queue_metadata = unique(snapshot["queue_metadata"], lambda r: r["unit_id"], "queue metadata")
    require(set(original_queue) == set(adjudications) == set(queue_metadata), "Queue membership changed")
    require(sorted(r["position"] for r in queue_metadata.values()) == list(range(42)) or
            sorted(r["position"] for r in queue_metadata.values()) == list(range(1,43)), "Invalid queue ordering")
    require(set(units) == set(candidates) and len(units) == len(gold) == 320, "Unit coverage mismatch")
    require({(r["record_id"], r["judged_turn"]) for r in candidates.values()} == set(gold), "Historical key coverage mismatch")
    old_annotations = unique(baseline["annotations"], lambda r: (r["unit_id"], r["annotator"]), "historical annotation")
    old_events = unique(baseline["events"], lambda r: (r["unit_id"], r["annotator"], r["version"]), "historical event")
    seen_annotations, seen_events, annotation_ids, annotation_event_ids, request_ids = set(), set(), set(), set(), set()
    canonical_annotations, reference = [], []
    decision_event_count = 0
    for unit_id, row in sorted(candidates.items()):
        unit = units[unit_id]
        require(row["schema_version"] == "sycocode-reeval-reference-candidate-v1" and
                row["reference_status"] == "candidate_human_policy_42_plus_278" and
                row["team_consensus"] is False, "Candidate schema/status mismatch")
        for field in ("group_id", "judged_turn", "payload_sha256", "study_sha256", "rubric_version"):
            require(row[field] == unit[field], f"Unit metadata mismatch: {unit_id}/{field}")
        require(row["record_id"] == unit["metadata"]["record_id"], "Record mapping mismatch")
        require(row["study_sha256"] == policy["study_sha256"] and row["rubric_version"] == policy["rubric_version"], "Study/rubric mismatch")
        historic = gold[(row["record_id"], row["judged_turn"])]
        require(unit["language"] == historic["language"], "Language mapping mismatch")
        if "item_id" in unit["metadata"]:
            require(unit["metadata"]["item_id"] == historic["item_id"], "Item mapping mismatch")
        votes = row["annotations"]
        require(len(votes) == 2 and sum(v["annotator"] == "jc" for v in votes) == 1
                and len({v["annotator"] for v in votes}) == 2, "Expected JC + one external")
        for vote in votes:
            key = (unit_id, vote["annotator"])
            old = old_annotations[key]
            require(key not in seen_annotations and vote["annotation_id"] not in annotation_ids, "Duplicate annotation")
            seen_annotations.add(key); annotation_ids.add(vote["annotation_id"])
            require(vote["first_label"] in LABELS and vote["current_label"] in LABELS, "Invalid original label")
            for new_field, old_field in [("first_label", "first_label"), ("current_label", "label"), ("version", "version"), ("note", "note")]:
                require(vote[new_field] == old[old_field], f"Original annotation changed: {unit_id}/{new_field}")
            for field in ("created_at", "updated_at"):
                require(stamp(vote[field]) == stamp(old[field]), "Original annotation timestamp changed")
            for field in ("group_id", "record_id", "judged_turn", "payload_sha256", "study_sha256", "rubric_version"):
                require(row[field] == old[field], "Historical unit mapping changed")
            require(unit["language"] == old["language"], "Historical language changed")
            require(vote["provenance"] == ("jc_manual_review_confirmed" if vote["annotator"] == "jc" else "external_human_annotation"), "Annotation provenance mismatch")
            events = vote["events"]
            require([e["version"] for e in events] == list(range(1, vote["version"] + 1)), "Missing annotation version")
            require(events[0]["label"] == vote["first_label"] and events[-1]["label"] == vote["current_label"], "First/current event mismatch")
            for event in events:
                event_key = (*key, event["version"])
                old_event = old_events[event_key]
                require(event_key not in seen_events and event["event_id"] not in annotation_event_ids, "Duplicate original event")
                seen_events.add(event_key); annotation_event_ids.add(event["event_id"])
                require(all(event[k] == old_event[k] for k in ("version", "label", "note")) and
                        stamp(event["created_at"]) == stamp(old_event["created_at"]), "Original event changed")
            canonical_annotations.append({"unit_id": unit_id, "annotator": vote["annotator"],
                **{k:vote[k] for k in ("first_label", "current_label", "version", "note")},
                "events": [{k:e[k] for k in ("version", "label", "note")} for e in events]})
        decision = row["decision"]
        if unit_id in adjudications:
            entry = adjudications[unit_id]
            require(entry["schema_version"] == "sycocode-adjudication-v1", "Adjudication schema mismatch")
            require(entry["queue_source_row"] == original_queue[unit_id], "Source queue row changed")
            require(entry["queue_source_sha256"] == row["queue_source_sha256"] == policy["source_sha256"], "Queue digest mismatch")
            require(entry["annotation_state_matches"] is True and
                    entry["annotation_state_sha256"] == entry["current_annotation_sha256"] == policy["annotations_sha256"], "Annotation state drift")
            require(queue_metadata[unit_id]["source_sha256"] == policy["source_sha256"] and
                    queue_metadata[unit_id]["annotation_state_sha256"] == policy["annotations_sha256"], "Queue import metadata mismatch")
            require(entry["annotations"] == votes and entry["decision"] == decision, "Decision/export mismatch")
            for field in ("group_id", "record_id", "judged_turn", "payload_sha256", "study_sha256", "rubric_version"):
                require(entry[field] == row[field], "Adjudication mapping mismatch")
            require(entry["language"] == unit["language"] and entry["scenario"] == unit["scenario"], "Adjudication context mismatch")
            require(row["label_source"] == "individual_adjudication" and row["reference_label"] == decision["label"], "Adjudicated reference mismatch")
            require(decision["author"] == "jc" and decision["decision_type"] == "individual_adjudication" and
                    decision["team_consensus"] is False and decision["display_status"] == "Adjudicación de JC", "Decision attribution mismatch")
            events = entry["events"]
            require([e["version"] for e in events] == list(range(1, decision["version"] + 1)), "Missing decision version")
            previous = stamp(queue_metadata[unit_id]["imported_at"])
            for event in events:
                require(event["author"] == "jc" and event["label"] in LABELS and
                        isinstance(event["rationale"], str) and 0 < len(event["rationale"].strip()) <= 5000, "Invalid decision provenance/rationale")
                require(event["vote_snapshot"] == votes, "Decision vote snapshot mismatch")
                require(event["request_id"] not in request_ids, "Duplicate decision request")
                uuid.UUID(event["request_id"]); request_ids.add(event["request_id"])
                event_time = stamp(event["created_at"])
                require(previous <= event_time <= stamp(snapshot["snapshot_utc"]), "Decision chronology mismatch")
                previous = event_time
            latest = events[-1]
            require(all(decision[k] == latest[k] for k in ("version", "label", "rationale", "author")) and
                    stamp(decision["decided_at"]) == stamp(latest["created_at"]), "Latest event differs from decision")
            decision_event_count += len(events)
        else:
            require(decision is None and row["queue_source_sha256"] is None and
                    row["label_source"] == "current_pair_agreement" and
                    row["reference_label"] == votes[0]["current_label"] == votes[1]["current_label"], "Agreement outside queue missing")
        require(row["reference_label"] in LABELS, "Invalid final label")
        reference.append({"schema_version": "sycocode-reeval-frozen-reference-v1",
            "reference_status": "frozen_human_policy_42_plus_278", "reference_version": "2026-09-30-v1",
            "unit_id": unit_id, "group_id": row["group_id"], "record_id": row["record_id"],
            "item_id": historic["item_id"], "judged_turn": row["judged_turn"],
            "language": unit["language"], "scenario": unit["scenario"],
            "gold_label": row["reference_label"], "label_source": row["label_source"],
            "annotators": [v["annotator"] for v in votes], "adjudicated": decision is not None,
            "team_consensus": False, "decision": decision,
            "decision_event_request_id": adjudications[unit_id]["events"][-1]["request_id"] if decision else None,
            "rubric_version": row["rubric_version"], "study_sha256": row["study_sha256"],
            "payload_sha256": row["payload_sha256"], "queue_source_sha256": row["queue_source_sha256"]})
    require(seen_annotations == set(old_annotations) and seen_events == set(old_events), "Historical vote/event coverage mismatch")
    require(decision_event_count == snapshot["counts"]["decision_events"], "Decision event coverage mismatch")
    digest = hashlib.sha256(json.dumps(sorted(canonical_annotations, key=lambda r:(r["unit_id"], r["annotator"])),
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(digest == policy["annotations_sha256"], "Independent annotation digest mismatch")
    sources = dict(Counter(r["label_source"] for r in reference))
    require(sources == {"current_pair_agreement":278, "individual_adjudication":42}, "42+278 policy failed")
    outputs = {"private/adjudications.jsonl": snapshot["exports"]["adjudications"]["jsonl"].encode(),
               "private/reference-candidate.jsonl": snapshot["exports"]["reference_candidate"]["jsonl"].encode(),
               "private/reference-2026-09-30-v1.jsonl": jsonl_bytes(reference)}
    inputs = {str(p.relative_to(folder)): sha(p) for p in [snap_path, baseline_path, queue_path, gold_path]}
    checks = {"status": "passed", "scope": "activity_1_only", "snapshot_utc": snapshot["snapshot_utc"],
        "units": 320, "conversations": len({r["group_id"] for r in reference}), "reference_sources": sources,
        "languages": dict(Counter(r["language"] for r in reference)), "adjudications": 42,
        "pending_adjudications": 0, "adjudication_events": decision_event_count,
        "original_annotations_preserved": len(seen_annotations), "original_events_preserved": len(seen_events),
        "rationales_and_authorship_verified": True, "all_decision_revisions_preserved": True,
        "unique_identifiers_and_historical_mapping_verified": True, "sqlite_integrity": "ok",
        "database_writes_by_exporter": 0, "annotation_state_sha256": digest,
        "panel_metrics_calculated": False, "cohort_recalculated": False, "model_api_calls": 0,
        "independent_panel_validation": False}
    manifest = {"schema_version": "sycocode-reeval-closure-manifest-v1",
        "reference_version": "2026-09-30-v1", "status": "frozen_and_integrity_verified",
        "snapshot_utc": snapshot["snapshot_utc"], "source_release": snapshot["source_release"].split("/")[-1],
        "policy": {"queue_units":42, "current_pair_agreements":278, "reference_units":320,
                   "queue_label": "latest_individual_adjudication", "other_label": "current_pair_agreement",
                   "selection_based_on_kappa":False, "team_consensus":False},
        "scope": "Historical full/gpt-oss pilot; not a held-out sample or a revalidation of 24000 cohort labels",
        "input_sha256": inputs,
        "code_sha256": {"export_reeval_closure.py":sha(root/'scripts/export_reeval_closure.py'),
                        "freeze_reeval_reference.py":sha(root/'scripts/freeze_reeval_reference.py'),
                        "queue_manifest":sha(policy_path)},
        "output_sha256": {k:hashlib.sha256(v).hexdigest() for k,v in outputs.items()},
        "reference_sources": sources, "privacy": "Individual data under private/ excluded from Git",
        "next_activity": "2 - compare saved judge votes; not executed"}
    outputs["verification.json"] = json_bytes(checks)
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["build", "verify"])
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = args.folder.resolve()
    outputs, checks = derive(root, folder)
    for name in outputs:
        path = folder/name
        if args.mode == "build":
            require(not path.exists(), f"Refusing overwrite: {path}")
        else:
            require(path.read_bytes() == outputs[name], f"Verification mismatch: {name}")
    if args.mode == "build":
        for name, content in outputs.items():
            path = folder/name
            with path.open("xb") as stream:
                stream.write(content)
            if name.startswith("private/"):
                path.chmod(0o600)
    print(json.dumps({"mode": args.mode, **checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
