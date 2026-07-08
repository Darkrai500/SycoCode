"""Live terminal progress for the Pass-1 runner.

Design: the runner emits events (turn done, retry, item done/error) into one
ProgressReporter that owns ALL terminal output, while a shared RunStats holder
feeds both the reporter and the StatusWriter so the on-screen numbers and
``status/<run_id>.json`` can never disagree.

Modes: "auto" (rich when stderr is a TTY, else plain), "rich" (a rich.live.Live
dashboard), "plain" (one banner line, then a compact stats line at most every
15 s, then a final line), "none" (silent). Everything renders to STDERR —
stdout stays reserved for the final JSON summary printed by ``cli.py``.

``rich`` is imported lazily and any import failure degrades to plain mode, so
the runner keeps working without it. The reporter is defensive by design: every
hook works before ``start()`` and after ``finish()``, ``finish()`` is
idempotent, and the Live display is always stopped on finish so a Ctrl-C never
leaves the terminal in a broken state.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

_MODES = ("auto", "rich", "plain", "none")
_GLYPHS = {"completed": "✓", "failed": "✗", "partial": "◐"}
_GLYPH_STYLES = {"completed": "green", "failed": "red", "partial": "yellow"}
_PLAIN_INTERVAL_S = 15.0
# Internal hook for tests/demos: render rich output even when stderr is not a
# real TTY (rich Console(force_terminal=True)). Set SYCO_PROGRESS_FORCE_TTY=1.
_FORCE_TTY_VAR = "SYCO_PROGRESS_FORCE_TTY"


def _fmt_duration(seconds: Optional[float]) -> str:
    """Humanize a duration: 2h05m / 14m47s / 37s. None/negative -> em dash."""
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


@dataclass
class RunStats:
    """Aggregate run counters shared by the ProgressReporter and StatusWriter.

    Token sums are None-safe: a provider count that is absent (None) is never
    fabricated as 0 — it simply does not contribute to the running total.
    """

    tokens: dict = field(default_factory=lambda: {"prompt": 0, "completion": 0,
                                                  "reasoning": 0, "cached": 0})
    cost_usd: float = 0.0
    retries_total: int = 0
    requests_done: int = 0
    error_counts: dict = field(default_factory=dict)
    recent_items: deque = field(default_factory=lambda: deque(maxlen=8))

    _USAGE_KEYS = (("prompt", "prompt_tokens"), ("completion", "completion_tokens"),
                   ("reasoning", "reasoning_tokens"), ("cached", "cached_tokens"))

    def add_turn(self, usage: Optional[dict], cost: Optional[float]) -> None:
        """Account one successful assistant turn (an API call that returned 200)."""
        u = usage or {}
        for key, wire in self._USAGE_KEYS:
            val = u.get(wire)
            if val is not None:
                self.tokens[key] += int(val)
        if cost is not None:
            self.cost_usd += cost
        self.requests_done += 1

    def add_retries(self, n: int) -> None:
        if n > 0:
            self.retries_total += n

    def note_error(self, kind: str) -> None:
        self.error_counts[kind] = self.error_counts.get(kind, 0) + 1

    def add_item(self, item_id: str, status: str, latency_ms: int,
                 cost_usd: Optional[float], turns: int) -> None:
        self.recent_items.append({"item_id": item_id, "status": status,
                                  "latency_ms": latency_ms, "cost_usd": cost_usd,
                                  "turns": turns})


class ProgressReporter:
    """Owns all terminal progress output for one run (stderr only).

    ``counts`` / ``in_flight`` / ``governor`` are live references to the
    runner's own state so the display reads current values at render time —
    elapsed/ETA tick between events because ``__rich_console__`` recomputes
    them on every Live auto-refresh.
    """

    def __init__(self, *, mode: str, run_id: str, model=None, total: int = 0,
                 skipped_existing: int = 0, to_run: int = 0, concurrency: int = 0,
                 stats: Optional[RunStats] = None, counts: Optional[dict] = None,
                 in_flight: Optional[dict] = None, governor=None,
                 status_path: Optional[str] = None, label: str = "Pass-1"):
        self.run_id = run_id
        self.label = label
        self.model = model
        self.total = total
        self.skipped_existing = skipped_existing
        self.to_run = to_run
        self.concurrency = concurrency
        self.stats = stats if stats is not None else RunStats()
        self._counts = counts if counts is not None else {"completed": 0, "failed": 0}
        self._in_flight = in_flight if in_flight is not None else {"n": 0}
        self._governor = governor
        self.status_path = status_path
        self._force_tty = os.environ.get(_FORCE_TTY_VAR) == "1"
        self.mode = self._resolve_mode(mode)
        self._recent_errors: deque = deque(maxlen=6)
        self._t0 = time.monotonic()
        self._last_plain = 0.0
        self._started = False
        self._finished = False
        self._final: Optional[tuple] = None       # (final_status, abort_reason)
        self._live = None
        self._console = None
        self._last_render = None                  # last good rich frame (see _dashboard)

    # ------------------------------------------------------------- lifecycle
    def _resolve_mode(self, mode: str) -> str:
        if mode not in _MODES:
            mode = "auto"
        if mode == "auto":
            try:
                tty = sys.stderr.isatty()
            except Exception:                     # stderr replaced/closed -> assume no TTY
                tty = False
            return "rich" if (self._force_tty or tty) else "plain"
        return mode

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._t0 = time.monotonic()
        self._last_plain = self._t0               # plain: first stats line ~15s after start
        if self.mode == "none":
            return
        if self.mode == "rich":
            try:
                from rich.console import Console
                from rich.live import Live
            except Exception:                     # rich missing/broken -> degrade, never crash
                self.mode = "plain"
            else:
                self._console = Console(stderr=True,
                                        force_terminal=True if self._force_tty else None)
                self._live = Live(self, console=self._console,
                                  refresh_per_second=4, transient=False)
                self._live.start()
                return
        self._emit(self._banner_line())

    def finish(self, final_status: str = "completed",
               abort_reason: Optional[str] = None) -> None:
        """Idempotent; always stops the Live display so the terminal is restored."""
        if self._finished:
            return
        self._finished = True
        self._final = (final_status, abort_reason)
        if self._live is not None:
            try:
                self._live.refresh()              # paint the final frame with the outcome line
            except Exception:
                pass
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None
            return
        if self.mode == "plain" and self._started:
            self._emit(self._final_line(final_status, abort_reason))

    # ----------------------------------------------------------- event hooks
    def on_turn_done(self, usage: Optional[dict], cost: Optional[float]) -> None:
        self.stats.add_turn(usage, cost)
        self._tick()

    def on_retry(self, kind: str) -> None:
        self._recent_errors.append(f"retry: {kind}")
        self._tick()

    def on_item_done(self, item_id: str, status: str, latency_ms: int,
                     cost: Optional[float], turns: int) -> None:
        self.stats.add_item(item_id, status, latency_ms, cost, turns)
        self._tick()

    def on_error(self, item_id: str, kind: str) -> None:
        self._recent_errors.append(f"{item_id}: {kind}")
        self._tick()

    def heartbeat(self) -> None:
        """Runner's periodic liveness ping (no event happened — e.g. every worker
        is sleeping in retry backoff). Plain mode emits the throttled stats line
        if the 15 s throttle allows; rich Live self-refreshes and "none" stays
        silent, so both are no-ops. Must never raise — it runs inside the
        runner's heartbeat task."""
        try:
            self._tick()
        except OSError:
            pass

    # ------------------------------------------------------------ plain mode
    def _emit(self, line: str) -> None:
        try:
            print(line, file=sys.stderr, flush=True)
        except Exception:                         # a dead stderr must never kill the run
            pass

    def _tick(self) -> None:
        # rich refreshes itself from its own timer; "none" is silent.
        if not self._started or self._finished or self.mode != "plain":
            return
        now = time.monotonic()
        if now - self._last_plain >= _PLAIN_INTERVAL_S:
            self._last_plain = now
            self._emit(self._stats_line())

    def _model_desc(self) -> str:
        m = self.model
        if m is None:
            return "?"
        return (f"{getattr(m, 'logical_name', '?')}@{getattr(m, 'provider', '?')} "
                f"({getattr(m, 'api_model_id', '?')})")

    def _rates(self):
        """(done, failed, elapsed_s, items_per_min, eta_s) computed at call time."""
        completed = self._counts.get("completed", 0)
        failed = self._counts.get("failed", 0)
        done = completed + failed
        elapsed = max(1e-9, time.monotonic() - self._t0)
        thr = done / elapsed * 60.0
        eta = ((self.to_run - done) / (done / elapsed)) if done > 0 else None
        return done, failed, elapsed, thr, eta

    def _banner_line(self) -> str:
        return (f"[{self.label}] {self.run_id} · {self._model_desc()} · {self.total} items "
                f"({self.skipped_existing} skipped on resume, {self.to_run} to run) · "
                f"concurrency {self.concurrency} · status {self.status_path or 'n/a'}")

    def _stats_line(self) -> str:
        done, failed, _, thr, eta = self._rates()
        pct = (done / self.to_run * 100.0) if self.to_run else 100.0
        return (f"[{time.strftime('%H:%M:%S')}] {done}/{self.to_run} ({pct:.1f}%) · "
                f"{failed} failed · {self._in_flight.get('n', 0)} in flight · "
                f"{thr:.1f}/min · ETA {_fmt_duration(eta)} · "
                f"${self.stats.cost_usd:.2f} · retries {self.stats.retries_total}")

    def _final_line(self, final_status: str, abort_reason: Optional[str]) -> str:
        completed = self._counts.get("completed", 0)
        failed = self._counts.get("failed", 0)
        line = (f"[{time.strftime('%H:%M:%S')}] {final_status}: {completed} completed, "
                f"{failed} failed · elapsed {_fmt_duration(time.monotonic() - self._t0)} · "
                f"${self.stats.cost_usd:.2f}")
        if abort_reason:
            line += f" · reason: {abort_reason}"
        return line

    # ------------------------------------------------------------- rich mode
    def __rich_console__(self, console, options):  # rich renderable protocol (duck-typed)
        yield self._dashboard()

    def _dashboard(self):
        # Runs on rich's Live auto-refresh THREAD while the asyncio event-loop
        # thread mutates shared state. Two safety layers: _build_dashboard only
        # iterates atomic snapshots of shared structures, and any render error
        # falls back to the last good frame — an exception escaping here would
        # kill rich's refresh thread and freeze the dashboard for the whole run.
        try:
            render = self._build_dashboard()
        except Exception:
            if self._last_render is not None:
                return self._last_render
            from rich.text import Text
            return Text("(progress render pending)", style="dim")
        self._last_render = render
        return render

    def _build_dashboard(self):
        from rich.console import Group
        from rich.panel import Panel
        from rich.progress_bar import ProgressBar
        from rich.table import Table
        from rich.text import Text

        done, failed, elapsed, thr, eta = self._rates()
        completed = done - failed
        to_run = max(self.to_run, 1)
        # Snapshots: tuple()/dict() are single atomic C calls, so the event-loop
        # thread can keep appending while we render. A Python-level loop over
        # the live deques can raise "deque mutated during iteration".
        recent_items = tuple(self.stats.recent_items)
        recent_errors = tuple(self._recent_errors)
        error_counts = dict(self.stats.error_counts)
        tok = dict(self.stats.tokens)
        final = self._final

        header = Text()
        header.append(f"SycoCode {self.label} · {self.run_id}\n", style="bold")
        header.append(f"{self._model_desc()} · {self.total} items · "
                      f"{self.skipped_existing} skipped (resume) · {self.to_run} to run · "
                      f"concurrency {self.concurrency}", style="dim")

        bar_row = Table.grid(expand=True, padding=(0, 1))
        bar_row.add_column(ratio=1)
        bar_row.add_column(justify="right")
        counts_txt = Text()
        counts_txt.append(f"{completed}", style="green")
        counts_txt.append(f"/{self.to_run} · {done / to_run * 100.0:.1f}%")
        if failed:
            counts_txt.append(f" · {failed} failed", style="bold red")
        bar_row.add_row(ProgressBar(total=float(to_run), completed=float(done)), counts_txt)

        gov = getattr(self._governor, "delay", 0.0) or 0.0
        stats_txt = Text(
            f"{thr:.1f} items/min · ETA {_fmt_duration(eta)} · "
            f"elapsed {_fmt_duration(elapsed)} · in-flight {self._in_flight.get('n', 0)} · "
            f"requests {self.stats.requests_done} · retries {self.stats.retries_total} · "
            f"governor {gov:.1f}s\n"
            f"tokens p {tok['prompt']:,} / c {tok['completion']:,} "
            f"(r {tok['reasoning']:,}) · cost ${self.stats.cost_usd:.4f}")

        parts = [header, bar_row, stats_txt]
        if error_counts:
            errs = " · ".join(f"{k}×{v}" for k, v in
                              sorted(error_counts.items(), key=lambda kv: -kv[1]))
            parts.append(Text(f"errors: {errs}", style="yellow"))

        recent = Table.grid(padding=(0, 1))
        for it in recent_items[-6:]:
            st = it.get("status", "?")
            cost = it.get("cost_usd")
            recent.add_row(
                Text(_GLYPHS.get(st, "?"), style=_GLYPH_STYLES.get(st, "yellow")),
                str(it.get("item_id", "?")),
                f"{(it.get('latency_ms') or 0) / 1000.0:.1f}s",
                f"${cost:.4f}" if cost is not None else "—",
            )
        err_lines = [Text(e, style="red") for e in recent_errors]
        if recent_items or err_lines:
            parts.append(Panel(Group(recent, *err_lines), title="recent",
                               border_style="dim", expand=True))

        if final is not None:
            st, reason = final
            style = "bold green" if st == "completed" else "bold red"
            parts.append(Text(f"run {st}" + (f" — {reason}" if reason else ""), style=style))

        return Group(*parts)


class JsonlSink:
    """Append-only, per-row-flushed JSONL writer shared by the judge paths.

    Writing each row the moment it is produced (then flushing) is what makes a
    killed/interrupted judge run RESUMABLE: the old gather-then-write-once design
    lost everything on Ctrl-C, so ``--resume`` had nothing to resume from. An
    ``asyncio.Lock`` serializes concurrent writers (the event loop is single
    threaded, but the lock keeps multi-row writes atomic across awaits)."""

    def __init__(self, path: str, *, resume: bool = False):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a" if resume else "w", encoding="utf-8")
        self._lock = asyncio.Lock()
        self.n_rows = 0

    async def write(self, rows: Iterable[dict]) -> None:
        batch = list(rows)
        if not batch:
            return
        async with self._lock:
            for r in batch:
                self._fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            self._fh.flush()
            self.n_rows += len(batch)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
