"""One-shot "does this model exist and is it available?" probe.

Used by the model registry (the panel's add/edit flow) to validate a model id
BEFORE it is saved. It deliberately bypasses the runner's retry/governor stack
(``eval/retry.py``, built for long batches) — a registration check wants a fast,
single verdict, not minutes of backoff.

Two signals, reusing the shared error taxonomy (``eval/errors.py``):
  1. EXISTENCE (OpenRouter): ``GET /models`` and look for the slug in the
     catalogue. Advisory only — OpenRouter often lists un-pinned ids while the
     registry uses date-pinned ones, so a catalogue miss does NOT fail the check.
  2. AVAILABILITY (authoritative): a minimal ``POST /chat/completions`` with
     ``max_tokens=1``. A 200 proves the key, the credit and an upstream provider
     are all good; any 4xx/5xx is mapped to a specific, user-facing message.

The API key is read from the environment variable NAMED by the provider preset
(never passed around as a value), mirroring ``eval/config.py``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx

from .config import load_dotenv
from .errors import ApiError, classify_status
from . import providers

PRICING_PATH = "config/pricing.json"
_DATE_SUFFIX = re.compile(r"-\d{6,8}$")        # strip "-20260423" / "-260423" date pins


def _normalize_id(model_id: str) -> str:
    return _DATE_SUFFIX.sub("", model_id.strip().lower())


def _pricing_known(provider: str, api_model_id: str, path: str = PRICING_PATH) -> bool:
    """Whether a USD rate exists in config/pricing.json (soft warning, not a gate)."""
    p = Path(path)
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (data.get(provider) or {}).get(api_model_id) is not None


def _message(kind: str, provider: str, api_model_id: str, key_var: str,
             detail: str = "") -> str:
    """Map an error kind to a specific Spanish message for the panel."""
    prov = provider
    table = {
        "missing_key": f"Falta la variable de entorno {key_var}: define la clave de {prov} en .env.",
        "not_found": f"El model id «{api_model_id}» no existe en {prov}.",
        "auth": f"API key de {prov} inválida o no autorizada (revisa {key_var}).",
        "payment": f"La cuenta de {prov} no tiene crédito suficiente.",
        "rate_limit": f"{prov} está limitando peticiones ahora mismo; reinténtalo en unos segundos.",
        "server_overloaded": f"{prov} o el proveedor upstream no está disponible temporalmente.",
        "server_error": f"{prov} devolvió un error de servidor; reinténtalo más tarde.",
        "timeout": f"Tiempo de espera agotado al contactar con {prov}.",
        "connection": f"Error de red al contactar con {prov}.",
        "transport": f"Error de red al contactar con {prov}.",
        "bad_response": f"{prov} devolvió una respuesta ilegible.",
        "empty_response": f"{prov} devolvió una respuesta vacía.",
        "context_length": f"Petición rechazada por longitud de contexto en {prov}.",
        "bad_request": f"Petición rechazada por {prov}" + (f": {detail}" if detail else "."),
    }
    return table.get(kind, f"Error «{kind}» al validar contra {prov}" + (f": {detail}" if detail else "."))


def _net_to_apierror(exc: Exception) -> ApiError:
    """Normalise an httpx wire-level exception, mirroring eval/client.py."""
    if isinstance(exc, httpx.TimeoutException):
        return ApiError("timeout", f"request timed out: {exc}", retryable=True)
    if isinstance(exc, httpx.DecodingError):
        return ApiError("bad_response", f"response decode error: {exc}", retryable=True)
    if isinstance(exc, httpx.TransportError):
        return ApiError("connection", f"connection error: {exc}", retryable=True)
    return ApiError("transport", f"transport error: {exc}", retryable=True)


async def _get_catalogue_ids(client: httpx.AsyncClient, base_url: str) -> set:
    """GET {base}/models -> set of advertised ids. Raises ApiError on HTTP/network error."""
    url = base_url.rstrip("/") + "/models"
    try:
        resp = await client.get(url)
    except httpx.HTTPError as e:
        raise _net_to_apierror(e) from e
    if resp.status_code >= 400:
        raise classify_status(resp.status_code, resp.text)
    try:
        data = resp.json()
    except ValueError as e:
        raise ApiError("bad_response", f"non-JSON /models body: {e}", resp.status_code, retryable=True) from e
    rows = data.get("data") if isinstance(data, dict) else data
    return {r.get("id") for r in (rows or []) if isinstance(r, dict) and r.get("id")}


def _id_in_catalogue(api_model_id: str, ids: set) -> bool:
    if api_model_id in ids:
        return True
    norm = _normalize_id(api_model_id)
    for cid in ids:
        nc = _normalize_id(cid)
        if norm == nc or norm.startswith(nc + "-") or nc.startswith(norm + "-"):
            return True
    return False


async def _ping(client: httpx.AsyncClient, base_url: str, api_model_id: str,
                max_tokens_param: str) -> dict:
    """Minimal 1-token completion. Raises ApiError on HTTP/network error."""
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": api_model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        max_tokens_param: 1,
    }
    try:
        resp = await client.post(url, json=body)
    except httpx.HTTPError as e:
        raise _net_to_apierror(e) from e
    if resp.status_code >= 400:
        raise classify_status(resp.status_code, resp.text)
    try:
        return resp.json()
    except ValueError:
        return {}


async def validate_model(provider: str, api_model_id: str, *,
                         base_url: Optional[str] = None,
                         api_key_var: Optional[str] = None,
                         max_tokens_param: Optional[str] = None,
                         transport=None, timeout_s: float = 30.0) -> dict:
    """Validate that ``api_model_id`` exists and is reachable via ``provider``.

    Returns a JSON-ready verdict::

        {ok, exists, available, error_kind, message, latency_ms,
         model_returned, pricing_known, provider, api_model_id}

    ``ok`` is True only if the availability ping succeeded. ``transport`` injects
    an ``httpx.MockTransport`` for offline tests (same seam as eval/client.py).
    """
    pre = providers.resolve(provider, base_url=base_url, api_key_var=api_key_var,
                            max_tokens_param=max_tokens_param)
    result = {
        "ok": False, "exists": None, "available": False,
        "error_kind": None, "message": "", "latency_ms": None,
        "model_returned": None,
        "pricing_known": _pricing_known(provider, api_model_id),
        "provider": provider, "api_model_id": api_model_id,
    }

    key = os.environ.get(pre["api_key_var"], "").strip()
    if not key:
        result["error_kind"] = "missing_key"
        result["message"] = _message("missing_key", provider, api_model_id, pre["api_key_var"])
        return result

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s), transport=transport,
                                 headers=headers) as client:
        # (1) Existence — advisory. A terminal credential/billing error here is
        # worth surfacing immediately; anything else is ignored (ping decides).
        try:
            ids = await _get_catalogue_ids(client, pre["base_url"])
            result["exists"] = _id_in_catalogue(api_model_id, ids)
        except ApiError as e:
            if e.should_abort_run:
                result["error_kind"] = e.kind
                result["message"] = _message(e.kind, provider, api_model_id,
                                              pre["api_key_var"], e.message)
                return result
            # rate_limit / 5xx / network on /models: leave exists=None, let the ping decide.

        # (2) Availability — authoritative.
        t0 = time.monotonic()
        try:
            payload = await _ping(client, pre["base_url"], api_model_id, pre["max_tokens_param"])
            result["latency_ms"] = int((time.monotonic() - t0) * 1000)
            result["available"] = True
            result["ok"] = True
            result["model_returned"] = payload.get("model") if isinstance(payload, dict) else None
            note = " (no figura en el catálogo, pero responde)" if result["exists"] is False else ""
            result["message"] = "Modelo disponible." + note
        except ApiError as e:
            result["latency_ms"] = int((time.monotonic() - t0) * 1000)
            result["error_kind"] = e.kind
            result["message"] = _message(e.kind, provider, api_model_id,
                                          pre["api_key_var"], e.message)
    return result


def validate_model_sync(provider: str, api_model_id: str, **kwargs) -> dict:
    """Blocking wrapper for synchronous callers (the stdlib panel handler runs
    each request in its own thread, so a fresh event loop here is safe)."""
    return asyncio.run(validate_model(provider, api_model_id, **kwargs))


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m eval.validate",
                                 description="Probe whether a model id exists and is available.")
    ap.add_argument("--provider", default=providers.DEFAULT_PROVIDER)
    ap.add_argument("--model", required=True, help="api_model_id, e.g. anthropic/claude-sonnet-4")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key-var", default=None)
    ap.add_argument("--max-tokens-param", default=None)
    ap.add_argument("--env-file", default=".env")
    args = ap.parse_args(argv)
    load_dotenv(args.env_file)
    res = validate_model_sync(args.provider, args.model, base_url=args.base_url,
                              api_key_var=args.api_key_var,
                              max_tokens_param=args.max_tokens_param)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
