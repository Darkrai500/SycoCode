#!/usr/bin/env python3
"""Build a small pool to rehearse the ReEval-2 flow on the server before the study.

It uses three conversations of the first study (data/goldset), one of them
single-turn, so the first author rehearses all the roles without opening any turn
of the ReEval-2 sample. The result goes to data/ReEval2/ensayo/, which git ignores.

    python scripts/build_reeval2_rehearsal.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/goldset/pool.jsonl"
OUT = ROOT / "data/ReEval2/ensayo"


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    per_group: dict[str, int] = {}
    for row in rows:
        per_group[row["group_id"]] = per_group.get(row["group_id"], 0) + 1
    single_unit = sorted((r for r in rows if per_group[r["group_id"]] == 1), key=lambda r: r["group_id"])
    single_turn = [r for r in single_unit if int(r["judged_turn"]) == 1][:1]
    multi_turn = [r for r in single_unit if int(r["judged_turn"]) > 1][:2]
    chosen = single_turn + multi_turn
    if len(chosen) != 3:
        raise SystemExit("data/goldset does not have the three conversations this rehearsal needs.")

    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "payloads").mkdir(parents=True)
    pool = []
    for i, row in enumerate(chosen):
        target = OUT / "payloads" / f"ensayo{i}.md"
        shutil.copyfile(ROOT / row["payload_path"], target)
        pool.append({**row, "unit_id": f"ensayo-u{i}", "group_id": f"ensayo-g{i}", "record_id": f"ensayo-r{i}",
                     "payload_path": str(target.relative_to(ROOT))})
    (OUT / "pool.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in pool), encoding="utf-8")
    manifest = {"schema_version": "sycocode-reeval2-rehearsal-v1", "rubric_version": "1.1",
                "display_order": [r["group_id"] for r in pool]}
    (OUT / "pool_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pool)} conversations -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
