"""API error taxonomy: classify failures as retryable vs terminal.

Retryable  -> back off and try again (transient: capacity, overload, timeout).
Terminal   -> stop retrying. Either fail just this item (bad_request,
              context_length) or abort the whole run (auth, not_found = a
              config/credential problem that would fail every item).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Terminal-and-abort-the-run: a credential/endpoint/billing problem, not item-specific.
# "payment" = OpenRouter 402 (negative credit balance): every call will fail until the
# account is topped up, so retrying just burns wall-clock — abort loudly instead.
ABORT_KINDS = {"auth", "not_found", "payment"}

# Kinds that signal the endpoint is saturated / non-responsive. These widen the
# global CapacityGovernor so ALL workers back off together — capacity exhaustion
# at Cerebras shows up at least as often as a read timeout / connection drop as a
# clean 5xx, so those MUST be included (not just rate_limit/5xx).
OVERLOAD_KINDS = {
    "rate_limit", "server_overloaded", "server_error",
    "timeout", "connection", "transport", "empty_response", "bad_response",
}


class AbortRun(Exception):
    """Raised to abort the entire run: a terminal credential/endpoint error
    (bad key, wrong base_url/model) that would fail every item. Carries the
    in-progress attempt count so accounting stays accurate."""

    def __init__(self, reason: str, attempts: int = 0):
        self.reason = reason
        self.attempts = attempts
        super().__init__(reason)


@dataclass
class ApiError(Exception):
    kind: str
    message: str
    status_code: Optional[int] = None
    retryable: bool = False
    retry_after: Optional[float] = None

    def __post_init__(self) -> None:  # keep Exception.args populated for tracebacks
        super().__init__(self.message)

    def __str__(self) -> str:
        sc = f" status={self.status_code}" if self.status_code is not None else ""
        return f"[{self.kind}]{sc} {self.message}"

    @property
    def is_terminal(self) -> bool:
        return not self.retryable

    @property
    def should_abort_run(self) -> bool:
        return self.kind in ABORT_KINDS


def classify_status(status_code: int, body: str = "") -> ApiError:
    """Map an HTTP status code (+ body) to an ApiError with retry semantics."""
    if status_code == 429:
        # Cerebras "at capacity" / rate limit. Honor Retry-After if the caller sets it.
        return ApiError("rate_limit", "rate limited / at capacity", status_code, retryable=True)
    if status_code in (500, 502, 503, 504):
        return ApiError("server_overloaded", "server overloaded / unavailable", status_code, retryable=True)
    if status_code in (401, 403):
        return ApiError("auth", "authentication/authorization failed (check API key)", status_code, retryable=False)
    if status_code == 402:
        # OpenRouter: insufficient credits / negative balance. Not item-specific.
        return ApiError("payment", body[:200] or "payment required / insufficient credits", status_code, retryable=False)
    if status_code == 404:
        return ApiError("not_found", "endpoint or model id not found", status_code, retryable=False)
    if status_code == 400:
        low = body.lower()
        if "context" in low and ("length" in low or "window" in low or "token" in low):
            return ApiError("context_length", body[:300] or "context length exceeded", status_code, retryable=False)
        return ApiError("bad_request", body[:300] or "bad request", status_code, retryable=False)
    if status_code in (408, 409, 425):
        # request timeout / conflict / too-early: safe to retry.
        return ApiError("transient_4xx", f"transient client error {status_code}", status_code, retryable=True)
    if 400 <= status_code < 500:
        return ApiError("client_error", f"client error {status_code}: {body[:200]}", status_code, retryable=False)
    # any other 5xx
    return ApiError("server_error", f"server error {status_code}: {body[:200]}", status_code, retryable=True)
