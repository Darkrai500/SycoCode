"""Persistent model registry — the source of truth for which models an
iteration evaluates.

Each entry pairs an EDITABLE human ``display_name`` (cosmetic, fix typos freely)
with an immutable ``slug``. The slug is load-bearing: it is the ``logical_name``
baked into every ``run_id`` (``<ts>__<slug>__<uuid6>``) and the per-model results
directory ``data/runs/<slug>/``. Renaming the display name therefore NEVER
touches disk or desynchronises existing results.

The file (``config/models.json``) stores only the NAME of the API-key env var,
never a key. Results live one directory per model, so deleting a model is an
atomic ``rmtree`` of its dir (see ``delete``) — no JSONL surgery.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import ModelConfig, Paths, RateLimitConfig, RequestParams, RetryConfig, RunConfig, ScopeFilter
from . import providers

DEFAULT_MODELS_PATH = "config/models.json"
DEFAULT_RUNS_ROOT = "data/runs"
REGISTRY_VERSION = 1


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    """Filesystem-safe slug from a display name: lowercase, [a-z0-9-] only,
    collapsed/trimmed dashes. Empty input falls back to 'model'."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "model"


def _contained(child: Path, parent: Path) -> bool:
    """True iff resolved ``child`` is inside resolved ``parent`` (no escape via
    .. or symlinks). Guards every filesystem mutation from a crafted slug/dir."""
    child, parent = child.resolve(), parent.resolve()
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class RegistryError(Exception):
    """Bad registry operation (duplicate, unknown slug, unsafe path)."""


@dataclass
class Registry:
    models_path: Path = Path(DEFAULT_MODELS_PATH)
    runs_root: Path = Path(DEFAULT_RUNS_ROOT)

    def __post_init__(self) -> None:
        self.models_path = Path(self.models_path)
        self.runs_root = Path(self.runs_root)

    # ----- persistence -------------------------------------------------
    def load(self) -> dict:
        """Tolerant read; a missing/corrupt file yields an empty registry."""
        if not self.models_path.is_file():
            return {"version": REGISTRY_VERSION, "models": []}
        try:
            data = json.loads(self.models_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": REGISTRY_VERSION, "models": []}
        data.setdefault("version", REGISTRY_VERSION)
        data.setdefault("models", [])
        return data

    def _save(self, data: dict) -> None:
        """Atomic write (tmp + replace), mirroring eval/store.py."""
        self.models_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp = self.models_path.with_name(self.models_path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.models_path)

    # ----- queries -----------------------------------------------------
    def list(self) -> List[dict]:
        return list(self.load().get("models", []))

    def get(self, slug: str) -> Optional[dict]:
        return next((m for m in self.list() if m.get("slug") == slug), None)

    def _unique_slug(self, base: str, existing: set) -> str:
        if base not in existing:
            return base
        i = 2
        while f"{base}-{i}" in existing:
            i += 1
        return f"{base}-{i}"

    def results_dir(self, entry: dict) -> Path:
        """``data/runs/<dir or slug>`` for a model, guaranteed inside runs_root."""
        name = entry.get("dir") or entry["slug"]
        d = self.runs_root / name
        if not _contained(d, self.runs_root):
            raise RegistryError(f"unsafe results dir for {entry.get('slug')!r}")
        return d

    # ----- mutations ---------------------------------------------------
    def add(self, *, display_name: str, api_model_id: str,
            provider: str = providers.DEFAULT_PROVIDER,
            base_url: Optional[str] = None, api_key_var: Optional[str] = None,
            max_tokens_param: Optional[str] = None,
            last_validated: Optional[dict] = None) -> dict:
        display_name = (display_name or "").strip()
        api_model_id = (api_model_id or "").strip()
        if not display_name:
            raise RegistryError("display_name is required")
        if not api_model_id:
            raise RegistryError("api_model_id is required")
        data = self.load()
        existing = {m.get("slug") for m in data["models"]}
        slug = self._unique_slug(slugify(display_name), existing)
        pre = providers.resolve(provider, base_url=base_url,
                                api_key_var=api_key_var,
                                max_tokens_param=max_tokens_param)
        entry = {
            "slug": slug,
            "display_name": display_name,
            "provider": pre["provider"],
            "api_model_id": api_model_id,
            "base_url": pre["base_url"],
            "api_key_var": pre["api_key_var"],
            "max_tokens_param": pre["max_tokens_param"],
            "added_at": _utcnow_iso(),
            "last_validated": last_validated,
        }
        data["models"].append(entry)
        self._save(data)
        return entry

    def update(self, slug: str, *, display_name: Optional[str] = None,
               api_model_id: Optional[str] = None,
               last_validated: Optional[dict] = None) -> dict:
        """Edit cosmetic display_name and/or api_model_id. The slug (and thus
        run_id / results dir) is immutable. Returns the updated entry."""
        data = self.load()
        entry = next((m for m in data["models"] if m.get("slug") == slug), None)
        if entry is None:
            raise RegistryError(f"unknown slug: {slug}")
        if display_name is not None:
            dn = display_name.strip()
            if not dn:
                raise RegistryError("display_name cannot be empty")
            entry["display_name"] = dn
        if api_model_id is not None:
            mid = api_model_id.strip()
            if not mid:
                raise RegistryError("api_model_id cannot be empty")
            entry["api_model_id"] = mid
        if last_validated is not None:
            entry["last_validated"] = last_validated
        self._save(data)
        return entry

    def delete(self, slug: str) -> dict:
        """Remove the entry AND its results directory (data/runs/<dir>). Returns
        ``{"slug","display_name","results_dir","results_removed"}``."""
        data = self.load()
        entry = next((m for m in data["models"] if m.get("slug") == slug), None)
        if entry is None:
            raise RegistryError(f"unknown slug: {slug}")
        results = self.results_dir(entry)        # raises if the path would escape
        removed = False
        if results.exists() and _contained(results, self.runs_root):
            shutil.rmtree(results)
            removed = True
        data["models"] = [m for m in data["models"] if m.get("slug") != slug]
        self._save(data)
        return {"slug": slug, "display_name": entry.get("display_name"),
                "results_dir": str(results), "results_removed": removed}

    def has_results(self, entry: dict) -> bool:
        d = self.results_dir(entry)
        return d.is_dir() and any(d.iterdir())

    # ----- bridge to the runner ----------------------------------------
    def to_model_config(self, entry: dict) -> ModelConfig:
        """A registry entry -> runner ModelConfig. logical_name = slug (the
        immutable identity baked into run_id)."""
        return ModelConfig(
            logical_name=entry["slug"],
            provider=entry["provider"],
            api_model_id=entry["api_model_id"],
            base_url=entry["base_url"],
            api_key_var=entry["api_key_var"],
            max_tokens_param=entry["max_tokens_param"],
        )

    def to_run_config(self, slug: str, *, scope: Optional[ScopeFilter] = None,
                      params: Optional[RequestParams] = None,
                      items_path: str = "data/problems/items.jsonl") -> RunConfig:
        """Build a RunConfig that writes into the model's own per-model dir.
        (Used by the next-phase run launcher; included now so the wiring is ready.)"""
        entry = self.get(slug)
        if entry is None:
            raise RegistryError(f"unknown slug: {slug}")
        out_dir = str(self.results_dir(entry))
        return RunConfig(
            model=self.to_model_config(entry),
            params=params or RequestParams(),
            retry=RetryConfig(),
            rate=RateLimitConfig(),
            scope=scope or ScopeFilter(),
            paths=Paths(items_path=items_path, out_dir=out_dir),
        )
