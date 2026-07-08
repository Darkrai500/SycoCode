"""Extract a few illustrative transcript snippets per model for the TFG reports,
so writers quote REAL conversations (no fabrication). For each model picks, when
available: (a) an insistent capitulation (final turn labelled 'capitulated',
prefer ES), and (b) a 'confidently wrong' case (final code FAILS but verbal firm).
Renders compact markdown to data/runs/aggregates/examples/<slug>.md.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"
OUT = RUNS / "aggregates" / "examples"
OUT.mkdir(parents=True, exist_ok=True)

MODELS = {
    "full": "verdicts.jsonl", "gemini-3-1-flash-lite": "verdicts.local.jsonl",
    "gemini-3-5-flash": "verdicts.jsonl", "glm-5-2": "verdicts.jsonl", "kimi-k-2-6": "verdicts.jsonl",
    "claude-opus-4-8": "verdicts.jsonl", "claude-sonnet-4-6": "verdicts.jsonl", "gpt-5-5": "verdicts.jsonl",
    "gpt-5-4-mini": "verdicts.jsonl", "minimax-m3": "verdicts.jsonl",
}
DISP = {"full": "gpt-oss-120b", "gemini-3-1-flash-lite": "Gemini 3.1 Flash Lite",
        "gemini-3-5-flash": "Gemini 3.5 Flash", "glm-5-2": "GLM 5.2", "kimi-k-2-6": "Kimi K2.6",
        "claude-opus-4-8": "Claude Opus 4.8", "claude-sonnet-4-6": "Claude Sonnet 4.6", "gpt-5-5": "GPT-5.5",
        "gpt-5-4-mini": "GPT-5.4 Mini", "minimax-m3": "MiniMax M3"}


def load(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def clip(s, n):
    s = (s or "").strip().replace("\r", "")
    return s if len(s) <= n else s[:n].rstrip() + " […]"


def final_turn(rec):
    n = len(rec.get("transcript", []))
    return 1 if n <= 1 else n


def _user_text(turn):
    ums = turn.get("user_messages") or []
    return " ".join((m.get("content") or "") for m in ums if isinstance(m, dict))


def _asst_text(turn):
    a = turn.get("assistant")
    if isinstance(a, dict):
        return a.get("content") or ""
    return a or ""


def render(rec, verd, vcr_label, kind):
    gt = rec.get("ground_truth") or {}
    lines = [f"### {kind} — `{rec['scenario_ref']}` · {rec['language'].upper()} · `{rec['bug_ref']}`",
             f"- **Bug:** {clip(gt.get('bug_description'), 220)}  *(nivel {gt.get('bug_level')}, {gt.get('bug_category')})*",
             f"- **Oráculo (código final):** {'PASA' if (verd and verd['oracle']['final_tests_pass']) else 'FALLA'}"
             f" · **VCR (turno final):** {vcr_label}", ""]
    turns = rec.get("transcript", [])
    if turns:
        lines += [f"**Asistente (turno 1):** {clip(_asst_text(turns[0]), 750)}", ""]
    if len(turns) >= 2:
        last = turns[-1]
        lines += [f"**Usuario (última presión, turno {last.get('turn')}):** {clip(_user_text(last), 400)}", ""]
        lines += [f"**Asistente (turno final):** {clip(_asst_text(last), 950)}", ""]
    return "\n".join(lines)


def pick_for_model(slug):
    d = RUNS / slug
    recs = load(d / "responses.jsonl")
    verds = {v["record_id"]: v for v in load(d / MODELS[slug])}
    vcr = load(d / "vcr.jsonl")
    vmap = {(r.get("record_id"), r.get("judged_turn")): r for r in vcr}

    def lab(r):
        row = vmap.get((r["record_id"], final_turn(r)))
        return row.get("label") if row else None

    def buggy(r):
        return bool((r.get("ground_truth") or {}).get("bug_present"))

    def fpass(r):
        v = verds.get(r["record_id"])
        return None if not v else bool(v["oracle"]["final_tests_pass"])

    insist = [r for r in recs if r["scenario_family"] == "insistent" and buggy(r)]
    # (a) capitulation, prefer ES, prefer code also broke
    caps = [r for r in insist if lab(r) == "capitulated"]
    caps.sort(key=lambda r: (r["language"] != "es", fpass(r) is not False))
    cap = caps[0] if caps else None
    # (b) confidently wrong: final FAIL but verbal firm, prefer ES
    cw = [r for r in insist if fpass(r) is False and lab(r) == "firm"]
    cw.sort(key=lambda r: (r["language"] != "es",))
    conf = cw[0] if cw else None

    parts = [f"# Ejemplos cualitativos — {DISP[slug]} (`{slug}`)\n"]
    if cap:
        parts.append(render(cap, verds.get(cap["record_id"]), "capitulated", "Capitulación insistente"))
    if conf and (not cap or conf["record_id"] != cap["record_id"]):
        parts.append(render(conf, verds.get(conf["record_id"]), "firm", "‘Confidently wrong’ (rompe código, discurso firme)"))
    (OUT / f"{slug}.md").write_text("\n\n".join(parts), encoding="utf-8")
    print(f"{slug}: cap={'Y' if cap else 'N'} conf_wrong={'Y' if conf else 'N'} -> examples/{slug}.md")


if __name__ == "__main__":
    for s in MODELS:
        pick_for_model(s)
