#!/usr/bin/env python3
"""Build the held-out reference (ReEval-2) from the released key and application exports.

One row per sampled turn, joining the unsealed sample key, the pool loaded in the
annotation application, both annotators' first and current labels, the adjudication
and the resulting reference label. The rule is the one in the protocol (section 4,
step 8): the annotators' common current label where they agree, the adjudicated label
otherwise. The script checks the inputs against each other and refuses to write
anything if they disagree.

Before building, it checks the exports against the server's own records in the
audit export: the SHA-256 the server logged for each download it served, the
digest stored with each annotator's hand-in (``annotations_sha256``) and the
annotation-state digest logged at the queue cut and at closure. The two digests
are recomputed from the released labels and events with the application's own
recipe (``own_annotations_sha256`` in ``webapp/annotations/reeval2.py`` and
``annotation_state_sha256`` in ``webapp/annotations/provenance.py``).

Standard library only; no network; writes only ``--out``.

    python scripts/export_reeval2_reference.py --out data/reeval2/held_out_reference_v1.jsonl
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/reeval2"
LABELS = ("firm", "hedged", "capitulated")
ANNOTATORS = ("a1", "a2")
# Same split as scripts/score_reeval2.py: a single-turn response has no earlier stance to abandon.
SINGLE_TURN_SCENARIOS = {"code_review_sycophancy", "expertise_deference_senior", "expertise_deference_student"}


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_sha256(value) -> str:
    """The application's digest: compact, key-sorted JSON in UTF-8."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def integrity(labels: list[dict], events: list[dict], audit: list[dict], export_dir: Path) -> list[str]:
    """Compare the exports with what the server recorded. Returns one line per check."""
    history = collections.defaultdict(list)
    for e in events:
        history[(e["unit_id"], e["annotator"])].append(e)
    for saves in history.values():
        saves.sort(key=lambda e: e["version"])
    report, failures = [], []

    def check(name, ok):
        report.append(f"{'ok' if ok else 'MISMATCH'}  {name}")
        if not ok:
            failures.append(name)

    served = {"jsonl": "sycocode-jsonl.jsonl", "csv": "sycocode-csv.csv", "events": "sycocode-events.jsonl",
              "agreement": "sycocode-agreement.jsonl", "decisions": "sycocode-reeval-adjudications.jsonl"}
    for row in (a for a in audit if a["type"] == "export"):
        path = export_dir / served[row["kind"]]
        check(f"server-logged SHA-256 of {path.name}",
              path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"])
    for row in (a for a in audit if a["type"] == "submission"):
        mine = sorted((r for r in labels if r["annotator"] == row["account"]), key=lambda r: r["unit_id"])
        rows = [{"unit_id": r["unit_id"], "first_label": r["first_label"], "label": r["label"], "note": r["note"],
                 "version": r["version"],
                 "events": [[e["version"], e["label"], e["note"]] for e in history[(r["unit_id"], row["account"])]]}
                for r in mine]
        check(f"hand-in digest of {row['account']}", canonical_sha256(rows) == row["annotations_sha256"])
    state = canonical_sha256([
        {"unit_id": r["unit_id"], "annotator": r["annotator"], "first_label": r["first_label"],
         "current_label": r["label"], "version": r["version"], "note": r["note"],
         "events": [{"version": e["version"], "label": e["label"], "note": e["note"]}
                    for e in history[(r["unit_id"], r["annotator"])]]}
        for r in sorted(labels, key=lambda r: (r["unit_id"], r["annotator"]))])
    for row in (a for a in audit if a["type"] == "study_event" and "annotation_state_sha256" in a["detail"]):
        check(f"annotation-state digest at {row['kind']}", state == row["detail"]["annotation_state_sha256"])
    if failures:
        raise SystemExit("Exports do not match the server's records, nothing written:\n  " + "\n  ".join(report))
    return report


def build(key: list[dict], pool: list[dict], labels: list[dict], adjudication: list[dict]) -> list[dict]:
    problems = []
    units = {u["unit_id"]: u for u in key}
    opaque = {p["unit_id"]: p for p in pool}
    if len(units) != len(key) or set(units) != set(opaque):
        problems.append("key and pool do not list the same units")
    votes: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for row in labels:
        if row["annotator"] not in ANNOTATORS or row["annotator"] in votes[row["unit_id"]]:
            problems.append(f"unexpected label row {row['unit_id']}/{row['annotator']}")
            continue
        votes[row["unit_id"]][row["annotator"]] = row
        unit = units.get(row["unit_id"])
        if unit is None or (row["group_id"], row["judged_turn"], row["language"], row["payload_sha256"]) != (
                unit["group_id"], unit["judged_turn"], unit["language"], unit["payload_sha256"]):
            problems.append(f"label row {row['unit_id']}/{row['annotator']} does not match the key")
        if row["label"] not in LABELS or row["first_label"] not in LABELS:
            problems.append(f"invalid label in {row['unit_id']}/{row['annotator']}")
    decisions = {}
    for row in adjudication:
        decision = row.get("decision") or {}
        if row["unit_id"] in decisions or decision.get("label") not in LABELS or not decision.get("rationale", "").strip():
            problems.append(f"invalid or duplicated adjudication {row['unit_id']}")
        decisions[row["unit_id"]] = row
    rows = []
    for uid in sorted(units):
        unit, pair = units[uid], votes.get(uid, {})
        if set(pair) != set(ANNOTATORS):
            problems.append(f"{uid} does not have exactly one label per annotator")
            continue
        a1, a2 = (pair[name] for name in ANNOTATORS)
        queued = a1["label"] != a2["label"]
        if queued != (uid in decisions):
            problems.append(f"{uid}: adjudication present={uid in decisions}, current labels differ={queued}")
            continue
        decision = decisions[uid]["decision"] if queued else None
        rows.append({
            "unit_id": uid,
            "group_id": unit["group_id"],
            "record_id": unit["record_id"],
            "pool_record_id": opaque[uid]["record_id"],
            "item_id": opaque[uid]["item_id"],
            "problem_ref": unit["problem_ref"],
            "model": unit["model"],
            "judged_turn": unit["judged_turn"],
            "language": unit["language"],
            "scenario": unit["scenario_ref"],
            "scenario_type": "single_turn" if unit["scenario_ref"] in SINGLE_TURN_SCENARIOS else "multi_turn",
            "rubric_version": a1["rubric_version"],
            "payload_sha256": unit["payload_sha256"],
            "design_weight": unit["design_weight"],
            "stratum_size": unit["stratum_size"],
            "a1_first_label": a1["first_label"],
            "a1_current_label": a1["label"],
            "a2_first_label": a2["first_label"],
            "a2_current_label": a2["label"],
            "in_adjudication_queue": queued,
            "adjudicated_label": decision["label"] if decision else None,
            "adjudication_rationale": decision["rationale"] if decision else None,
            "adjudication_versions": decision["version"] if decision else None,
            "reference_label": decision["label"] if decision else a1["label"],
            "label_source": "adjudicated" if decision else "agreed",
            "panel_label_archived": unit["panel_label"],
            "tiebreak_used": unit["tiebreak_used"],
        })
    unknown = sorted(set(decisions) - set(units))
    if unknown:
        problems.append(f"adjudications for units outside the key: {unknown[:5]}")
    if problems:
        raise SystemExit("Inconsistent inputs, nothing written:\n  " + "\n  ".join(problems[:20]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--key", type=Path, default=DATA / "sample_key.jsonl")
    ap.add_argument("--pool", type=Path, default=DATA / "pool.jsonl")
    ap.add_argument("--labels", type=Path, default=DATA / "export/sycocode-jsonl.jsonl")
    ap.add_argument("--adjudication", type=Path, default=DATA / "export/sycocode-reeval-adjudications.jsonl")
    ap.add_argument("--events", type=Path, default=DATA / "export/sycocode-events.jsonl")
    ap.add_argument("--audit", type=Path, default=DATA / "export/sycocode-audit.jsonl")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    labels = read(args.labels)
    for line in integrity(labels, read(args.events), read(args.audit), args.labels.parent):
        print(line)
    rows = build(read(args.key), read(args.pool), labels, read(args.adjudication))
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    sources = collections.Counter(r["label_source"] for r in rows)
    reference = collections.Counter(r["reference_label"] for r in rows)
    print(f"{len(rows)} units: {sources['agreed']} agreed, {sources['adjudicated']} adjudicated; reference "
          + ", ".join(f"{reference[label]} {label}" for label in LABELS) + f" -> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
