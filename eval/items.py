"""Read-only access to ``items.jsonl`` (the dataset is NEVER mutated here)."""
from __future__ import annotations

import hashlib
import json
from typing import Iterator, List


def dataset_hash(path: str) -> str:
    """sha256 of the whole items file — pins the exact dataset version evaluated."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def iter_items(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for ln, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{ln}: invalid JSON: {e}") from e


def in_scope(item: dict, scope) -> bool:
    if scope.problem_refs and item.get("problem_ref") not in scope.problem_refs:
        return False
    if scope.scenarios and item.get("scenario_ref") not in scope.scenarios:
        return False
    if scope.languages and item.get("language") not in scope.languages:
        return False
    return True


def scoped_items(path: str, scope) -> List[dict]:
    """Materialize the scoped slice (in file order). ``limit`` caps the count."""
    out: List[dict] = []
    for item in iter_items(path):
        if in_scope(item, scope):
            out.append(item)
            if scope.limit and len(out) >= scope.limit:
                break
    return out
