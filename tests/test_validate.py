"""Offline unit test for the OpenRouter validation probe (eval/validate.py).

Uses httpx.MockTransport (the same injection seam as eval/client.py) so no
network and no real API key are involved. Checks the error-kind -> message
mapping the panel relies on.

    .venv/bin/python tests/test_validate.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx                                                  # noqa: E402

from eval.validate import validate_model_sync                # noqa: E402

_PASS = 0
_FAIL = 0
KEY_VAR = "OPENROUTER_API_KEY"


def check(name, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1; print(f"  ok  {name}")
    else:
        _FAIL += 1; print(f"  XX  {name}  {detail}")


def transport(*, catalogue=None, models_status=200, chat_status=200, chat_body=None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/models"):
            if models_status >= 400:
                return httpx.Response(models_status, json={"error": {"message": "models err"}})
            return httpx.Response(200, json={"data": [{"id": i} for i in (catalogue or [])]})
        if request.method == "POST" and path.endswith("/chat/completions"):
            if chat_status >= 400:
                return httpx.Response(chat_status, json={"error": {"message": "chat err"}})
            return httpx.Response(200, json=chat_body or {"id": "x", "model": "echo/model"})
        return httpx.Response(404, json={"error": "unexpected"})
    return httpx.MockTransport(handler)


def run(model_id, **kw):
    return validate_model_sync("openrouter", model_id, transport=transport(**kw))


def main() -> None:
    os.environ[KEY_VAR] = "test-key-not-real"

    # A) exists in catalogue + ping 200 -> ok
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"])
    check("A ok", r["ok"] and r["exists"] and r["available"], r)
    check("A message available", "disponible" in r["message"].lower(), r["message"])
    check("A model_returned", r["model_returned"] == "echo/model", r)
    check("A latency recorded", isinstance(r["latency_ms"], int), r)

    # B) date-pinned id not literally in catalogue, but normalized match -> exists True
    r = run("deepseek/deepseek-v4-pro-20260423", catalogue=["deepseek/deepseek-v4-pro"])
    check("B normalized match", r["exists"] is True and r["ok"], r)

    # C) not in catalogue but ping 200 -> ok, exists False, noted
    r = run("vendor/secret-model", catalogue=["other/model"])
    check("C ok despite catalogue miss", r["ok"] and r["exists"] is False, r)
    check("C message notes catalogue", "catálogo" in r["message"], r["message"])

    # D) 404 on ping -> not_found
    r = run("vendor/typo", catalogue=[], chat_status=404)
    check("D not_found", (not r["ok"]) and r["error_kind"] == "not_found", r)
    check("D message specific", "no existe" in r["message"], r["message"])

    # E) 401 on ping -> auth
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"], chat_status=401)
    check("E auth", (not r["ok"]) and r["error_kind"] == "auth", r)
    check("E message mentions key var", KEY_VAR in r["message"], r["message"])

    # F) 402 on ping -> payment / no credit
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"], chat_status=402)
    check("F payment", (not r["ok"]) and r["error_kind"] == "payment", r)
    check("F message credit", "crédito" in r["message"], r["message"])

    # G) 429 on ping -> rate_limit
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"], chat_status=429)
    check("G rate_limit", (not r["ok"]) and r["error_kind"] == "rate_limit", r)

    # H) 503 on ping -> server_overloaded
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"], chat_status=503)
    check("H server", (not r["ok"]) and r["error_kind"] == "server_overloaded", r)

    # I) auth error on /models short-circuits before the ping
    r = run("anthropic/claude-sonnet-4", models_status=401)
    check("I models-auth short-circuit", (not r["ok"]) and r["error_kind"] == "auth", r)

    # J) /models rate-limited (advisory) but ping ok -> still ok, exists None
    r = run("anthropic/claude-sonnet-4", models_status=429)
    check("J models 429 ignored, ping ok", r["ok"] and r["exists"] is None, r)

    # K) missing key -> no network, missing_key
    os.environ.pop(KEY_VAR, None)
    r = run("anthropic/claude-sonnet-4", catalogue=["anthropic/claude-sonnet-4"])
    check("K missing key", (not r["ok"]) and r["error_kind"] == "missing_key", r)
    check("K message names var", KEY_VAR in r["message"], r["message"])
    os.environ[KEY_VAR] = "test-key-not-real"

    print(f"\n{_PASS} passed, {_FAIL} failed")
    sys.exit(1 if _FAIL else 0)


if __name__ == "__main__":
    main()
