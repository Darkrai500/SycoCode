"""Local run-monitor web panel ("mission control") for the Pass-1 eval runner.

Zero-dependency stdlib server. It watches a runner output directory
(``data/runs/<out>``) and exposes three read-only JSON endpoints consumed by
``scripts/panel.html``:

* ``/api/runs``       — every run known from the status dir and ``runs.jsonl``.
* ``/api/status``     — raw status file for one run plus derived freshness fields.
* ``/api/breakdown``  — scenario × language matrix, failures and token/cost totals
                        aggregated from ``responses.jsonl``.

``responses.jsonl`` lines are multi-KB (full transcripts) and the file grows
while a run is live, so the breakdown endpoint uses an incremental reader: it
remembers a byte offset per file and only parses bytes appended since the last
request. Status files may be schema v1 (no ``schema_version``) or v2; every
v2-only field is treated as optional.

Security model: localhost bind by default, and no filesystem path is ever
derived from request input — ``run_id`` is only matched against the actual
status-dir listing / ``runs.jsonl`` contents.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

# Make the sibling ``eval`` package importable when run as ``python scripts/panel.py``
# (sys.path[0] is scripts/, not the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval import providers, validate                       # noqa: E402
from eval.registry import Registry, RegistryError           # noqa: E402

STALE_AFTER_S = 120.0        # non-terminal runs not updated for this long are "stale"
FAILURES_KEPT = 50
MESSAGE_CLIP = 160
CHUNK_BYTES = 8 * 1024 * 1024   # bounded catch-up reads of responses.jsonl


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(ts: Optional[str], now: datetime) -> Optional[float]:
    dt = _parse_iso(ts)
    return round((now - dt).total_seconds(), 1) if dt else None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contained(child: Path, parent: Path) -> bool:
    """True iff resolved ``child`` is inside resolved ``parent`` (no .. escape)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


_CTYPES = {".html": "text/html; charset=utf-8",
           ".js": "application/javascript; charset=utf-8",
           ".jsx": "application/javascript; charset=utf-8",
           ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
           ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
           ".map": "application/json; charset=utf-8"}


def _guess_ctype(p: Path) -> str:
    return _CTYPES.get(p.suffix.lower(), "application/octet-stream")


def _read_jsonl(path: Path) -> List[dict]:
    """Tolerant full read for SMALL files only (runs.jsonl events)."""
    out: List[dict] = []
    if not path.is_file():
        return out
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Run discovery + status resolution
# ---------------------------------------------------------------------------

@dataclass
class RunsDir:
    """Read-only view over one runner output directory."""

    root: Path

    @property
    def status_dir(self) -> Path:
        return self.root / "status"

    @property
    def responses_path(self) -> Path:
        return self.root / "responses.jsonl"

    @property
    def runs_path(self) -> Path:
        return self.root / "runs.jsonl"

    def status_files(self) -> Dict[str, Path]:
        """run_id -> status file, from the real directory listing only."""
        if not self.status_dir.is_dir():
            return {}
        return {p.stem: p for p in sorted(self.status_dir.glob("*.json"))
                if not p.name.endswith(".tmp")}

    def last_events(self) -> Dict[str, dict]:
        """run_id -> last event record from runs.jsonl (append-only, small)."""
        last: Dict[str, dict] = {}
        for ev in _read_jsonl(self.runs_path):
            rid = ev.get("run_id")
            if rid:
                last[rid] = ev
        return last

    def known_run_ids(self) -> set:
        return set(self.status_files()) | set(self.last_events())


def _resolve_run_status(status: Optional[dict], last_event: Optional[dict],
                        now: datetime) -> str:
    """Terminal v2 field wins; else terminal runs.jsonl event; else freshness.

    Only terminal v2 values short-circuit: a runner killed before its
    ``finally`` (SIGKILL / OOM / power loss) leaves ``run_status == "running"``
    in the status file forever, so non-terminal values still go through the
    ``updated_at`` freshness check and decay to ``stale``.
    """
    v2 = (status or {}).get("run_status")
    if v2 in ("finished", "aborted"):
        return str(v2)
    ev = (last_event or {}).get("event")
    if ev in ("finished", "aborted"):
        return ev
    updated = (status or {}).get("updated_at") or (last_event or {}).get("updated_at")
    age = _age_seconds(updated, now)
    return "running" if (age is not None and age < STALE_AFTER_S) else "stale"


def _load_status(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None      # mid-rename race or corrupt file: treat as absent


def list_runs(rd: RunsDir) -> List[dict]:
    now = datetime.now(timezone.utc)
    events = rd.last_events()
    entries: List[dict] = []
    seen: set = set()

    for run_id, path in rd.status_files().items():
        st = _load_status(path)
        if st is None:
            continue
        seen.add(run_id)
        ev = events.get(run_id)
        entry = {
            "run_id": run_id,
            "run_status": _resolve_run_status(st, ev, now),
            "total": st.get("total"),
            "completed": st.get("completed"),
            "failed": st.get("failed"),
            "updated_at": st.get("updated_at"),
            "age_seconds": _age_seconds(st.get("updated_at"), now),
        }
        model = st.get("model") or (ev or {}).get("model")
        if model:
            entry["model"] = model
        entries.append(entry)

    for run_id, ev in events.items():          # runs with no status file yet
        if run_id in seen:
            continue
        counts = ev.get("counts") or {}
        entry = {
            "run_id": run_id,
            "run_status": _resolve_run_status(None, ev, now),
            "total": ev.get("scope_item_count"),
            "completed": counts.get("completed"),
            "failed": counts.get("failed"),
            "updated_at": ev.get("updated_at"),
            "age_seconds": _age_seconds(ev.get("updated_at"), now),
        }
        if ev.get("model"):
            entry["model"] = ev["model"]
        entries.append(entry)

    def sort_key(e: dict):
        dt = _parse_iso(e.get("updated_at"))
        return (dt or datetime.min.replace(tzinfo=timezone.utc), e["run_id"])

    entries.sort(key=sort_key, reverse=True)
    return entries


# ---------------------------------------------------------------------------
# Incremental responses.jsonl aggregation
# ---------------------------------------------------------------------------

@dataclass
class _RunAgg:
    by_cell: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_record: Dict[str, dict] = field(default_factory=dict)   # record_id -> {cell, status}
    failures: Dict[str, dict] = field(default_factory=dict)    # record_id -> entry, insertion = recency
    records: int = 0            # every responses.jsonl line, incl. superseded attempts
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    anon_seq: int = 0           # synthetic keys for records missing record_id


@dataclass
class _Cursor:
    ino: int = -1                           # st_ino at first read (replacement detection)
    offset: int = 0
    tail: bytes = b""                       # bytes after the last seen newline
    runs: Dict[str, _RunAgg] = field(default_factory=dict)


class BreakdownReader:
    """Incremental, append-aware aggregator over responses.jsonl.

    Each request stats the file and parses ONLY newly appended bytes (in
    bounded ``CHUNK_BYTES`` slices, so a cold first read of a multi-GB backlog
    never materialises the whole file); the trailing partial line (writer
    mid-append) is buffered until its newline arrives. A size decrease or an
    inode change means truncation/rotation/replacement -> full rebuild.

    Counts are last-record-wins per ``record_id`` (``--resume`` re-attempts
    append a second record with the same id; only the latest reflects the
    item's current state), while token/cost/retry totals sum over ALL records
    — superseded failed attempts cost real money and must stay visible.

    Handlers never see live aggregate objects: ``breakdown()`` deep-copies the
    response payload while holding the lock, so concurrent ingestion can never
    mutate a dict mid-``json.dumps``.
    """

    def __init__(self) -> None:
        self._cursors: Dict[Path, _Cursor] = {}
        self._lock = threading.Lock()       # ThreadingHTTPServer => concurrent requests

    def breakdown(self, path: Path, run_id: str) -> Optional[dict]:
        """JSON-ready payload for run_id, or None if the file has no records."""
        with self._lock:
            agg = self._catch_up(path).get(run_id)
            if agg is None:
                return None
            return {
                "run_id": run_id,
                "by_scenario_language": {k: dict(v) for k, v in agg.by_cell.items()},
                "failures": [dict(f) for f in reversed(list(agg.failures.values()))],
                "totals": {
                    "items": len(agg.by_record),         # distinct record_ids
                    "records": agg.records,              # all lines, incl. superseded
                    "prompt_tokens": agg.prompt_tokens,
                    "completion_tokens": agg.completion_tokens,
                    "cost_usd": round(agg.cost_usd, 6),
                    "retries": agg.retries,
                },
            }

    def _catch_up(self, path: Path) -> Dict[str, _RunAgg]:
        """Ingest appended bytes. Caller must hold self._lock."""
        try:
            st = path.stat()
        except OSError:
            self._cursors.pop(path, None)
            return {}
        cur = self._cursors.get(path)
        if cur is None or st.st_size < cur.offset or st.st_ino != cur.ino:
            cur = _Cursor(ino=st.st_ino)    # new/shrunk/replaced file: rebuild
            self._cursors[path] = cur
        if st.st_size > cur.offset:
            with path.open("rb") as fh:
                fh.seek(cur.offset)
                remaining = st.st_size - cur.offset
                while remaining > 0:
                    chunk = fh.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    cur.offset += len(chunk)
                    lines = (cur.tail + chunk).split(b"\n")
                    cur.tail = lines.pop()
                    for raw in lines:
                        self._ingest(cur, raw)
        return cur.runs

    @staticmethod
    def _ingest(cur: _Cursor, raw: bytes) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            rec = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return
        run_id = rec.get("run_id")
        if not run_id:
            return
        agg = cur.runs.setdefault(run_id, _RunAgg())

        # Money/usage totals: every record counts, even superseded attempts.
        agg.records += 1
        agg.retries += int(rec.get("retries") or 0)
        usage = rec.get("usage_total") or {}
        agg.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        agg.completion_tokens += int(usage.get("completion_tokens") or 0)
        cost = rec.get("cost_usd_total")
        if cost is None:
            cost = sum((t.get("cost_usd") or 0.0) for t in (rec.get("transcript") or []))
        agg.cost_usd += float(cost or 0.0)

        # Matrix counts: last record wins per record_id.
        rid = rec.get("record_id")
        if not rid:
            agg.anon_seq += 1
            rid = f"__line__{agg.anon_seq}"
        prev = agg.by_record.get(rid)
        if prev is not None:
            old_cell = agg.by_cell.get(prev["cell"])
            if old_cell is not None and prev["status"] in old_cell:
                old_cell[prev["status"]] -= 1
        key = f"{rec.get('scenario_ref')}|{rec.get('language')}"
        status = rec.get("status")
        agg.by_record[rid] = {"cell": key, "status": status}
        cell = agg.by_cell.setdefault(key, {"completed": 0, "partial": 0, "failed": 0})
        if status in cell:
            cell[status] += 1

        # Failures feed, keyed by record_id: a later success drops the stale
        # entry; a later failure replaces it (and becomes most-recent).
        error = rec.get("error")
        if error:
            agg.failures.pop(rid, None)
            agg.failures[rid] = {
                "item_id": rec.get("item_id"),
                "error_type": error.get("type"),
                "error_message": str(error.get("message") or "")[:MESSAGE_CLIP],
                "retries": int(rec.get("retries") or 0),
            }
            while len(agg.failures) > FAILURES_KEPT:
                agg.failures.pop(next(iter(agg.failures)))
        elif status == "completed":
            agg.failures.pop(rid, None)


def _empty_breakdown(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "by_scenario_language": {},
        "failures": [],
        "totals": {"items": 0, "records": 0, "prompt_tokens": 0,
                   "completion_tokens": 0, "cost_usd": 0.0, "retries": 0},
    }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _make_handler(rd: RunsDir, reader: BreakdownReader, html_path: Path,
                  registry: Registry, ui_dir: Optional[Path] = None,
                  index_file: Optional[Path] = None):

    class PanelHandler(BaseHTTPRequestHandler):
        server_version = "SycoPanel/1.0"

        def log_message(self, fmt: str, *args) -> None:   # noqa: A003 - polled every 2s
            pass

        # -- helpers -----------------------------------------------------
        def _send_json(self, obj, code: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _query_run_id(self, query: str) -> Optional[str]:
            vals = parse_qs(query).get("run_id") or []
            return vals[0] if vals else None

        def _read_json_body(self) -> Optional[dict]:
            """Parse the request body as JSON. {} for empty; None for malformed."""
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except (TypeError, ValueError):
                return None
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None
            return obj if isinstance(obj, dict) else None

        def _path_slug(self, path: str) -> Optional[str]:
            """Trailing segment of /api/models/<slug>; None if absent or nested."""
            rest = unquote(path[len("/api/models/"):]).strip("/")
            return rest if (rest and "/" not in rest) else None

        def _wrap(self, fn) -> None:
            """Shared try/guard so any route keeps the server alive."""
            try:
                fn()
            except BrokenPipeError:
                pass
            except Exception as e:                         # noqa: BLE001 - keep server alive
                try:
                    self._send_json({"error": "internal", "detail": repr(e)[:300]}, 500)
                except OSError:
                    pass

        # -- routes ------------------------------------------------------
        def do_GET(self) -> None:                          # noqa: N802 - http.server API
            parsed = urlparse(self.path)

            def route():
                if parsed.path in ("/", "/index.html"):
                    self._serve_index()
                elif parsed.path == "/api/meta":
                    self._send_json({"runs_dir": str(rd.root),
                                     "models_file": str(registry.models_path),
                                     "runs_root": str(registry.runs_root),
                                     "ui_dir": str(ui_dir) if ui_dir else None})
                elif parsed.path == "/api/runs":
                    self._send_json(list_runs(rd))
                elif parsed.path == "/api/status":
                    self._api_status(self._query_run_id(parsed.query))
                elif parsed.path == "/api/breakdown":
                    self._api_breakdown(self._query_run_id(parsed.query))
                elif parsed.path == "/api/models":
                    self._api_list_models()
                elif ui_dir is not None and not parsed.path.startswith("/api/"):
                    self._serve_static(parsed.path)          # SPA assets (js/*.jsx, …)
                else:
                    self._send_json({"error": "not found"}, 404)
            self._wrap(route)

        def do_POST(self) -> None:                         # noqa: N802 - http.server API
            parsed = urlparse(self.path)

            def route():
                if parsed.path == "/api/models/validate":
                    self._api_validate_model()
                elif parsed.path == "/api/models":
                    self._api_add_model()
                else:
                    self._send_json({"error": "not found"}, 404)
            self._wrap(route)

        def do_PATCH(self) -> None:                        # noqa: N802 - http.server API
            parsed = urlparse(self.path)
            self._wrap(lambda: self._api_edit_model(self._path_slug(parsed.path)))

        def do_DELETE(self) -> None:                       # noqa: N802 - http.server API
            parsed = urlparse(self.path)
            self._wrap(lambda: self._api_delete_model(self._path_slug(parsed.path)))

        def _serve_html(self) -> None:
            try:
                body = html_path.read_bytes()
            except OSError:
                self._send_json({"error": "panel.html missing next to panel.py"}, 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_index(self) -> None:
            """'/' -> the Mission Control SPA when --ui-dir is set, else legacy panel.html."""
            if ui_dir is not None and index_file is not None:
                self._serve_file(index_file)
            else:
                self._serve_html()

        def _serve_static(self, path: str) -> None:
            """Serve a file from ui_dir. The target is validated to stay inside
            ui_dir (no path is built from request input without containment)."""
            rel = unquote(path).lstrip("/")
            target = index_file if rel in ("", "index.html") else (ui_dir / rel)
            if target is None or not _contained(target, ui_dir) or not target.is_file():
                self._send_json({"error": "not found"}, 404)
                return
            self._serve_file(target)

        def _serve_file(self, p: Path) -> None:
            try:
                body = p.read_bytes()
            except OSError:
                self._send_json({"error": f"cannot read {p.name}"}, 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", _guess_ctype(p))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _api_status(self, run_id: Optional[str]) -> None:
            if not run_id:
                self._send_json({"error": "run_id query parameter required"}, 400)
                return
            path = rd.status_files().get(run_id)           # listing match, never a join
            status = _load_status(path) if path else None
            ev = rd.last_events().get(run_id)
            if status is None:
                if ev is None:
                    self._send_json({"error": f"unknown run_id: {run_id}"}, 404)
                    return
                # Run known only from runs.jsonl: synthesize a minimal status
                # payload from its last event so the panel can still render it.
                counts = ev.get("counts") or {}
                status = {
                    "run_id": run_id,
                    "total": ev.get("scope_item_count"),
                    "completed": counts.get("completed"),
                    "failed": counts.get("failed"),
                    "skipped_existing": counts.get("skipped_existing"),
                    "started_at": ev.get("started_at"),
                    "updated_at": ev.get("updated_at"),
                    "synthesized": True,
                }
                if ev.get("finished_at"):
                    status["finished_at"] = ev["finished_at"]
                if ev.get("model"):
                    status["model"] = ev["model"]
            now = datetime.now(timezone.utc)
            status["run_status"] = _resolve_run_status(status, ev, now)
            status["age_seconds"] = _age_seconds(status.get("updated_at"), now)
            total = status.get("total") or 0
            done = ((status.get("completed") or 0) + (status.get("failed") or 0)
                    + (status.get("skipped_existing") or 0))
            status["percent"] = round(100.0 * done / total, 2) if total else None
            self._send_json(status)

        def _api_breakdown(self, run_id: Optional[str]) -> None:
            if not run_id:
                self._send_json({"error": "run_id query parameter required"}, 400)
                return
            payload = reader.breakdown(rd.responses_path, run_id)
            if payload is None:
                if run_id not in rd.known_run_ids():
                    self._send_json({"error": f"unknown run_id: {run_id}"}, 404)
                    return
                payload = _empty_breakdown(run_id)         # known run, no records yet
            self._send_json(payload)

        # -- model registry routes (read + write) -----------------------
        def _api_list_models(self) -> None:
            out = []
            for e in registry.list():
                item = dict(e)
                try:
                    item["has_results"] = registry.has_results(e)
                except Exception:                          # noqa: BLE001 - never fail the list
                    item["has_results"] = False
                out.append(item)
            self._send_json({"models": out})

        def _validate_payload(self, body: dict) -> dict:
            provider = (body.get("provider") or providers.DEFAULT_PROVIDER).strip()
            model_id = (body.get("api_model_id") or "").strip()
            return validate.validate_model_sync(
                provider, model_id,
                base_url=body.get("base_url") or None,
                api_key_var=body.get("api_key_var") or None,
                max_tokens_param=body.get("max_tokens_param") or None,
            )

        @staticmethod
        def _validation_stamp(res: dict) -> dict:
            return {"at": _utcnow_iso(), "ok": res.get("ok"),
                    "model_returned": res.get("model_returned"),
                    "latency_ms": res.get("latency_ms")}

        def _api_validate_model(self) -> None:
            body = self._read_json_body()
            if body is None:
                self._send_json({"error": "invalid JSON body"}, 400)
                return
            if not (body.get("api_model_id") or "").strip():
                self._send_json({"error": "api_model_id required"}, 400)
                return
            self._send_json(self._validate_payload(body))

        def _api_add_model(self) -> None:
            body = self._read_json_body()
            if body is None:
                self._send_json({"error": "invalid JSON body"}, 400)
                return
            display_name = (body.get("display_name") or "").strip()
            model_id = (body.get("api_model_id") or "").strip()
            if not display_name or not model_id:
                self._send_json({"error": "display_name and api_model_id required"}, 400)
                return
            res = self._validate_payload(body)             # authoritative server-side check
            if not res.get("ok"):
                self._send_json({"error": "validation_failed", "validation": res}, 422)
                return
            try:
                entry = registry.add(
                    display_name=display_name, api_model_id=model_id,
                    provider=(body.get("provider") or providers.DEFAULT_PROVIDER),
                    base_url=body.get("base_url") or None,
                    api_key_var=body.get("api_key_var") or None,
                    max_tokens_param=body.get("max_tokens_param") or None,
                    last_validated=self._validation_stamp(res),
                )
            except RegistryError as e:
                self._send_json({"error": str(e)}, 400)
                return
            self._send_json({"model": entry, "validation": res}, 201)

        def _api_edit_model(self, slug: Optional[str]) -> None:
            if not slug:
                self._send_json({"error": "model slug required"}, 400)
                return
            entry = registry.get(slug)
            if entry is None:
                self._send_json({"error": f"unknown model: {slug}"}, 404)
                return
            body = self._read_json_body()
            if body is None:
                self._send_json({"error": "invalid JSON body"}, 400)
                return
            new_name = body.get("display_name")
            new_id = body.get("api_model_id")
            stamp, res = None, None
            # Re-validate ONLY when the model id actually changes.
            if new_id is not None and new_id.strip() and new_id.strip() != entry["api_model_id"]:
                res = validate.validate_model_sync(
                    entry["provider"], new_id.strip(),
                    base_url=entry.get("base_url"), api_key_var=entry.get("api_key_var"),
                    max_tokens_param=entry.get("max_tokens_param"),
                )
                if not res.get("ok"):
                    self._send_json({"error": "validation_failed", "validation": res}, 422)
                    return
                stamp = self._validation_stamp(res)
            try:
                updated = registry.update(slug, display_name=new_name,
                                          api_model_id=new_id, last_validated=stamp)
            except RegistryError as e:
                self._send_json({"error": str(e)}, 400)
                return
            self._send_json({"model": updated, "validation": res})

        def _api_delete_model(self, slug: Optional[str]) -> None:
            if not slug:
                self._send_json({"error": "model slug required"}, 400)
                return
            try:
                info = registry.delete(slug)
            except RegistryError as e:
                self._send_json({"error": str(e)}, 404)
                return
            self._send_json({"deleted": info})

    return PanelHandler


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="SycoCode local run-monitor panel.")
    ap.add_argument("--runs-dir", default="data/runs/full",
                    help="runner output dir containing status/, responses.jsonl, runs.jsonl")
    ap.add_argument("--models-file", default="config/models.json",
                    help="model registry file (read/write CRUD endpoints)")
    ap.add_argument("--runs-root", default="data/runs",
                    help="parent dir for per-model result dirs (data/runs/<slug>/)")
    ap.add_argument("--ui-dir",
                    default=str(Path(__file__).resolve().parent.parent / "SycoCode Mission Control"),
                    help="static SPA dir served same-origin at / (Mission Control). "
                         "Pass --ui-dir '' to serve the legacy panel.html instead.")
    ap.add_argument("--port", type=int, default=8377)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--open", action="store_true", help="open the panel in a browser")
    args = ap.parse_args(argv)

    rd = RunsDir(Path(args.runs_dir).resolve())
    registry = Registry(models_path=Path(args.models_file).resolve(),
                        runs_root=Path(args.runs_root).resolve())
    html_path = Path(__file__).resolve().parent / "panel.html"

    ui_dir = Path(args.ui_dir).resolve() if args.ui_dir else None
    index_file = None
    if ui_dir is not None and ui_dir.is_dir():
        htmls = sorted(ui_dir.glob("*.html"))
        index_file = htmls[0] if htmls else None
    if ui_dir is not None and index_file is None:
        print(f"mission control: no .html in {ui_dir}; falling back to legacy panel.html")
        ui_dir = None
    handler = _make_handler(rd, BreakdownReader(), html_path, registry, ui_dir, index_file)

    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    httpd.daemon_threads = True
    url = f"http://{args.host}:{args.port}/"
    print(f"mission control: watching {rd.root}")
    print(f"mission control: registry {registry.models_path}  (runs root {registry.runs_root})")
    print(f"mission control: UI {index_file if index_file else '(legacy panel.html)'}")
    print(f"mission control: serving on {url}  (Ctrl-C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nmission control: stopped")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
