"""Intelligent, automatic request pacing and retry.

Three cooperating mechanisms keep the runner well-behaved when Cerebras is at
capacity or rate-limiting:

  - TokenBucket       proactive pacing to stay under the tier's RPM and TPM
                      (so we don't *cause* 429s in the first place).
  - CapacityGovernor  reactive AIMD "soft circuit-breaker": when the endpoint
                      signals saturation (429 / 5xx AND read timeouts /
                      connection drops — see errors.OVERLOAD_KINDS) it widens a
                      GLOBAL spacing shared by every in-flight worker, then
                      decays it on success. This is what makes an at-capacity or
                      non-responsive Cerebras degrade gracefully across all
                      workers instead of being hammered by a thundering herd.
  - compute_backoff   per-request exponential backoff with full jitter that
                      honors a server-provided Retry-After.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Optional


class TokenBucket:
    """Continuous-refill token bucket. ``rate`` is units/second; ``capacity`` is burst."""

    def __init__(self, rate_per_sec: float, capacity: Optional[float] = None):
        self.rate = max(0.0, rate_per_sec)
        self.capacity = capacity if capacity is not None else max(1.0, self.rate)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, amount: float = 1.0) -> None:
        if self.rate <= 0:
            return
        amount = min(amount, self.capacity)
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= amount:
                    self._tokens -= amount
                    return
                wait = (amount - self._tokens) / self.rate
            await asyncio.sleep(wait)


class CapacityGovernor:
    """AIMD global spacing. Grows multiplicatively on overload, decays additively
    on success, shared across all workers."""

    def __init__(self, step_s: float = 0.5, max_s: float = 30.0):
        self.step = step_s
        self.max = max_s
        self._delay = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        d = self._delay
        if d > 0:
            await asyncio.sleep(d)

    async def record_overload(self) -> None:
        async with self._lock:
            self._delay = min(self.max, self._delay * 2 if self._delay > 0 else self.step)

    async def record_success(self) -> None:
        async with self._lock:
            if self._delay > 0:
                self._delay = max(0.0, self._delay - self.step)

    @property
    def delay(self) -> float:
        return self._delay


def compute_backoff(attempt: int, base: float, cap: float,
                    retry_after: Optional[float]) -> float:
    """Exponential backoff with full jitter; honors Retry-After when present.

    ``attempt`` is 1-based (1 = the delay before the first retry).
    """
    exp = min(cap, base * (2 ** max(0, attempt - 1)))
    jittered = random.uniform(0.0, exp)
    if retry_after is not None and retry_after > 0:
        return max(retry_after, jittered)
    return jittered
