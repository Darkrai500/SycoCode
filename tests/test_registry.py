"""Offline unit test for the model registry (eval/registry.py).

No network, no API keys. Exercises slugify/dedupe, add/get/list, immutable-slug
edits, per-model results deletion, and the path-containment guard.

    .venv/bin/python tests/test_registry.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.registry import Registry, RegistryError, slugify    # noqa: E402

_PASS = 0
_FAIL = 0


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1; print(f"  ok  {name}")
    else:
        _FAIL += 1; print(f"  XX  {name}  {detail}")


def main() -> None:
    # ---- slugify ----
    check("slugify basic", slugify("Claude Sonnet 4") == "claude-sonnet-4")
    check("slugify strips punctuation", slugify("  GPT-4o (mini)!! ") == "gpt-4o-mini")
    check("slugify empty -> 'model'", slugify("   ") == "model")

    with tempfile.TemporaryDirectory() as td:
        reg = Registry(models_path=Path(td) / "models.json", runs_root=Path(td) / "runs")

        # ---- add + slug dedupe ----
        a = reg.add(display_name="Claude Sonnet 4", api_model_id="anthropic/claude-sonnet-4")
        check("add returns slug", a["slug"] == "claude-sonnet-4", a)
        check("add fills openrouter preset", a["base_url"] == "https://openrouter.ai/api/v1"
              and a["api_key_var"] == "OPENROUTER_API_KEY" and a["max_tokens_param"] == "max_tokens", a)
        b = reg.add(display_name="Claude Sonnet 4", api_model_id="anthropic/claude-sonnet-4-pinned")
        check("dedupe slug", b["slug"] == "claude-sonnet-4-2", b)
        check("list has 2", len(reg.list()) == 2)
        check("get by slug", reg.get("claude-sonnet-4")["api_model_id"] == "anthropic/claude-sonnet-4")

        # ---- provider override (cerebras) ----
        c = reg.add(display_name="GLM", api_model_id="zai-glm-4.7", provider="cerebras")
        check("cerebras preset", c["base_url"] == "https://api.cerebras.ai/v1"
              and c["max_tokens_param"] == "max_completion_tokens", c)

        # ---- empty fields rejected ----
        try:
            reg.add(display_name="  ", api_model_id="x"); check("empty name rejected", False)
        except RegistryError:
            check("empty name rejected", True)

        # ---- edit: display_name editable, slug immutable ----
        up = reg.update("claude-sonnet-4", display_name="Sonnet (fixed typo)")
        check("rename keeps slug", up["slug"] == "claude-sonnet-4" and up["display_name"] == "Sonnet (fixed typo)", up)
        up2 = reg.update("claude-sonnet-4", api_model_id="anthropic/claude-sonnet-4.5")
        check("edit model id", up2["api_model_id"] == "anthropic/claude-sonnet-4.5")
        try:
            reg.update("nope", display_name="x"); check("update unknown -> error", False)
        except RegistryError:
            check("update unknown -> error", True)

        # ---- to_model_config: logical_name == slug ----
        mc = reg.to_model_config(reg.get("claude-sonnet-4"))
        check("model_config logical_name == slug", mc.logical_name == "claude-sonnet-4", mc.logical_name)

        # ---- has_results + delete removes the per-model dir ----
        rdir = reg.results_dir(reg.get("claude-sonnet-4"))
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "responses.jsonl").write_text("{}\n", encoding="utf-8")
        check("has_results true", reg.has_results(reg.get("claude-sonnet-4")))
        info = reg.delete("claude-sonnet-4")
        check("delete removed results", info["results_removed"] and not rdir.exists(), info)
        check("delete removed entry", reg.get("claude-sonnet-4") is None)
        check("list now 2", len(reg.list()) == 2)

        # ---- delete of a model with no results dir still succeeds ----
        info2 = reg.delete("glm")
        check("delete no-results ok", info2["results_removed"] is False and reg.get("glm") is None, info2)

        # ---- path containment guard ----
        try:
            reg.results_dir({"slug": "evil", "dir": "../../etc"}); check("escape dir blocked", False)
        except RegistryError:
            check("escape dir blocked", True)

        # ---- persistence: a fresh Registry sees saved state ----
        reg2 = Registry(models_path=Path(td) / "models.json", runs_root=Path(td) / "runs")
        check("persisted across instances", reg2.get("claude-sonnet-4-2") is not None)

    print(f"\n{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)


if __name__ == "__main__":
    main()
