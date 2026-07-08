"""Cost-per-token resolution.

A price table keyed by (provider, api_model_id) -> {input_per_1m, output_per_1m}
in USD per 1,000,000 tokens. Unknown model -> cost is None (per the schema).

Defaults below are the published Cerebras gpt-oss-120b rates (verified
2026-06-08). They are OVERRIDABLE/extendable by an optional ``config/pricing.json``
(or $SYCO_PRICING_FILE). CONFIRM live rates in the Cerebras console before
relying on cost for billing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# USD per 1,000,000 tokens.
_DEFAULT_PRICES = {
    "cerebras": {
        "gpt-oss-120b": {"input_per_1m": 0.35, "output_per_1m": 0.75},
    },
}


def _load_overrides() -> dict:
    path = Path(os.environ.get("SYCO_PRICING_FILE", "config/pricing.json"))
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _merged_table() -> dict:
    merged = {prov: dict(models) for prov, models in _DEFAULT_PRICES.items()}
    for provider, models in _load_overrides().items():
        if not isinstance(models, dict):
            continue
        merged.setdefault(provider, {})
        for model, price in models.items():
            merged[provider][model] = price
    return merged


def price_for(provider: str, model_id: str) -> Optional[dict]:
    return _merged_table().get(provider, {}).get(model_id)


def cost_usd(provider: str, model_id: str,
             prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> Optional[float]:
    """Return per-turn cost in USD, or None if the model is not in the price table."""
    price = price_for(provider, model_id)
    if not price:
        return None
    pin = price.get("input_per_1m")
    pout = price.get("output_per_1m")
    if pin is None or pout is None:
        return None
    return round((prompt_tokens or 0) / 1e6 * pin + (completion_tokens or 0) / 1e6 * pout, 8)
