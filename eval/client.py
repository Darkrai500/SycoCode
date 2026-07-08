"""Async OpenAI-compatible chat client (provider-agnostic).

Only base_url / api_key / model_id differ between providers, so the same client
serves Cerebras today and OpenRouter later with no logic change. All failures
are normalized to ``ApiError`` so the runner's retry layer can reason about them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

import httpx

from .errors import ApiError, classify_status


@dataclass
class ChatResult:
    content: Optional[str]
    reasoning: Optional[str]          # gpt-oss harmony "analysis" channel; None for non-reasoning models
    finish_reason: Optional[str]
    tool_calls: Optional[list]
    usage: dict                       # prompt/completion/total + reasoning_tokens + cached_tokens
    response_id: Optional[str]
    system_fingerprint: Optional[str]
    model_returned: Optional[str]


def _parse_retry_after(headers) -> Optional[float]:
    ra = headers.get("retry-after")
    if ra is None:
        return None
    try:
        return float(ra)               # Cerebras sends seconds as a number
    except (TypeError, ValueError):
        pass
    try:                               # RFC 7231 HTTP-date form (CDN/gateway 429/503)
        target = parsedate_to_datetime(ra)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None                    # unparseable: fall back to exponential backoff


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model_id: str, *,
                 params, max_tokens_param: str, timeout_s: float, transport=None,
                 extra_body: Optional[dict] = None):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model_id
        self._params = params
        self._max_tokens_param = max_tokens_param
        # Provider-specific passthrough merged verbatim into every request body.
        # Used e.g. for DeepSeek-on-vLLM thinking: {"chat_template_kwargs": {"thinking": true}}
        # (W&B/CoreWeave ignores the top-level reasoning_effort field for DeepSeek-V4).
        self._extra_body = dict(extra_body or {})
        # `transport` is an injection seam for offline tests (httpx.MockTransport);
        # None = real network transport.
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s),
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _payload(self, messages: List[dict]) -> dict:
        p = {
            "model": self._model,
            "messages": messages,
            "temperature": self._params.temperature,
            "top_p": self._params.top_p,
            self._max_tokens_param: self._params.max_tokens,
        }
        if self._params.seed is not None:
            p["seed"] = self._params.seed
        if getattr(self._params, "reasoning_effort", None):
            p["reasoning_effort"] = self._params.reasoning_effort
        for k, v in self._extra_body.items():
            p[k] = v
        return p

    async def chat(self, messages: List[dict]) -> ChatResult:
        try:
            resp = await self._client.post(self._url, json=self._payload(messages))
        except httpx.TimeoutException as e:
            raise ApiError("timeout", f"request timed out: {e}", retryable=True) from e
        except httpx.TransportError as e:
            # connect/read/network/protocol errors (TimeoutException handled above)
            raise ApiError("connection", f"connection error: {e}", retryable=True) from e
        except httpx.DecodingError as e:
            # corrupt/truncated content-encoded body — a transient wire symptom
            raise ApiError("bad_response", f"response decode error: {e}", retryable=True) from e
        except httpx.HTTPError as e:
            # any remaining httpx wire-level error: keep it inside the retry taxonomy
            raise ApiError("transport", f"transport error: {e}", retryable=True) from e

        if resp.status_code >= 400:
            err = classify_status(resp.status_code, resp.text)
            err.retry_after = _parse_retry_after(resp.headers)
            raise err

        try:
            data = resp.json()
        except ValueError as e:
            raise ApiError("bad_response", f"non-JSON response body: {e}",
                           resp.status_code, retryable=True) from e

        choices = data.get("choices") or []
        if not choices:
            raise ApiError("empty_response", "response had no choices",
                           resp.status_code, retryable=True)

        choice = choices[0] or {}
        msg = choice.get("message") or {}
        usage = data.get("usage") or {}
        ctd = usage.get("completion_tokens_details") or {}
        ptd = usage.get("prompt_tokens_details") or {}
        return ChatResult(
            content=msg.get("content"),
            # gpt-oss/GLM use "reasoning"; DeepSeek-on-vLLM uses "reasoning_content".
            reasoning=msg.get("reasoning") or msg.get("reasoning_content"),
            finish_reason=choice.get("finish_reason"),
            tool_calls=msg.get("tool_calls"),
            usage={
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "reasoning_tokens": ctd.get("reasoning_tokens"),
                "cached_tokens": ptd.get("cached_tokens"),
            },
            response_id=data.get("id"),
            system_fingerprint=data.get("system_fingerprint"),
            model_returned=data.get("model"),
        )
