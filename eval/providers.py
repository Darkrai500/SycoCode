"""Provider presets, shared across the judge, the model registry and the
OpenRouter validation probe.

Only ``base_url`` / ``api_key_var`` / ``max_tokens_param`` differ between
OpenAI-compatible providers, so a single table drives them all. ``thinking_via``
is judge-only (how a reasoning request reaches the model on the wire) and is
ignored by the registry/validator. The API key itself NEVER lives here — only
the NAME of the environment variable that holds it.
"""
from __future__ import annotations

from typing import Optional

# Canonical provider table. Lifted verbatim from eval/judge.py:_JUDGE_PROVIDERS so
# the OpenRouter preset stops being duplicated; judge.py now imports this.
PROVIDERS = {
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_var": "CEREBRAS_API_KEY",
        "max_tokens_param": "max_completion_tokens",
        "default_model": "zai-glm-4.7",
        "thinking_via": "reasoning_effort",
    },
    "wandb": {
        "base_url": "https://api.inference.wandb.ai/v1",
        "api_key_var": "WANDB_API_KEY",
        "max_tokens_param": "max_tokens",
        "default_model": "deepseek-ai/DeepSeek-V4-Flash",
        "thinking_via": "chat_template_kwargs",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_var": "OPENROUTER_API_KEY",
        "max_tokens_param": "max_tokens",
        "default_model": "deepseek/deepseek-v4-flash",
        "thinking_via": "reasoning_object",
    },
}

# The registry's default provider for newly-added models: OpenRouter is the
# current standard for everything except the Cerebras gpt-oss generation.
DEFAULT_PROVIDER = "openrouter"


def preset(provider: str) -> dict:
    """Provider preset dict, or the Cerebras default for an unknown provider."""
    return PROVIDERS.get(provider) or PROVIDERS["cerebras"]


def resolve(provider: str, *, base_url: Optional[str] = None,
            api_key_var: Optional[str] = None,
            max_tokens_param: Optional[str] = None) -> dict:
    """Fill base_url / api_key_var / max_tokens_param from the provider preset,
    letting explicit overrides win. Returns a plain dict ready for ModelConfig.
    """
    p = preset(provider)
    return {
        "provider": provider,
        "base_url": base_url or p["base_url"],
        "api_key_var": api_key_var or p["api_key_var"],
        "max_tokens_param": max_tokens_param or p["max_tokens_param"],
    }
