"""VCR-2 gold-set annotation app — local, disposable, label-then-reveal.

Single-file stdlib HTTP server (no deps, no DB, no auth). One response (group)
per screen: anchor bug + verbal-only conversation (code stripped, D8); judged
turns carry a {Firm, Hedged, Capitulated} selector. The evaluated model is
NEVER shown. Blind labeling first: the commit is append-only and immutable;
only after the commit are the Fable pre-labels revealed, discrepancies are
flagged, and the FINAL label defaults to the annotator's blind label (an
explicit "adopt" action records an override event — the blind event is never
rewritten).

Insistent scenario: full-transcript view, one selector per judged turn
(T2..T5), a single confirm commits all four turns at once (revealing
turn-by-turn would bias later turns of the same transcript).

Usage:
  PYTHONPATH=. python3 scripts/gold_annotator.py                 # JC, localhost
  PYTHONPATH=. python3 scripts/gold_annotator.py --bind 0.0.0.0  # phone on LAN
  PYTHONPATH=. python3 scripts/gold_annotator.py --annotator annotator_b --no-reveal \
      --out data/goldset/annotations_b.jsonl                 # blind-only mode

Resume: state is rebuilt from the append-only annotations file at startup.
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere, no PYTHONPATH
from eval.vcr_protocols import LABELS, RUBRIC_V11

_BUG_RE = re.compile(r"CENTRAL BUG \(anchor\): (.*?)\n\nCONVERSATION:\n", re.DOTALL)
_TURN_RE = re.compile(
    r"(?m)^(?:USER \(turn (?P<ut>\d+)\): |\[T(?P<jt>\d+)\] ASSISTANT \(turn \d+\)  <-- CLASSIFY: |ASSISTANT \(turn (?P<at>\d+)\): )")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def parse_payload(text: str) -> tuple[str, list[dict]]:
    """-> (bug_description, [{role, turn, judged, text}, ...]) from a payload .md."""
    m = _BUG_RE.search(text)
    bug = m.group(1).strip() if m else "(?)"
    convo = text[m.end():] if m else text
    marks = list(_TURN_RE.finditer(convo))
    turns = []
    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(convo)
        body = convo[mk.end():end].strip()
        if mk.group("ut"):
            turns.append({"role": "user", "turn": int(mk.group("ut")), "judged": False, "text": body})
        elif mk.group("jt"):
            turns.append({"role": "assistant", "turn": int(mk.group("jt")), "judged": True, "text": body})
        else:
            turns.append({"role": "assistant", "turn": int(mk.group("at")), "judged": False, "text": body})
    return bug, turns


class State:
    def __init__(self, args):
        self.lock = threading.Lock()
        self.annotator = args.annotator
        self.reveal = not args.no_reveal
        self.out = Path(args.out)
        self.units = [json.loads(l) for l in Path(args.pool).read_text(encoding="utf-8").splitlines() if l.strip()]
        self.by_unit = {u["unit_id"]: u for u in self.units}
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        self.order = manifest["display_order"]
        self.groups = {g["group_id"]: g for g in manifest["groups"]}
        self.group_units = {}
        for u in self.units:
            self.group_units.setdefault(u["group_id"], []).append(u)

        self.prelabels = {}
        ppath = Path(args.prelabels)
        files = sorted(ppath.glob("*.jsonl")) if ppath.is_dir() else ([ppath] if ppath.is_file() else [])
        for f in files:
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    self.prelabels[r["unit_id"]] = r

        self.blind = {}      # unit_id -> blind_commit event
        self.final = {}      # unit_id -> final label (override only)
        if self.out.exists():
            for line in self.out.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                ev = json.loads(line)
                if ev["event"] == "blind_commit":
                    self.blind[ev["unit_id"]] = ev
                elif ev["event"] == "override":
                    self.final[ev["unit_id"]] = ev["final_label"]

    def _append(self, ev: dict) -> None:
        self.out.parent.mkdir(parents=True, exist_ok=True)
        with self.out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            f.flush()

    def group_done(self, gid: str) -> bool:
        return all(u["unit_id"] in self.blind for u in self.group_units[gid])

    def next_group(self) -> str | None:
        for gid in self.order:
            if not self.group_done(gid):
                return gid
        return None

    def progress(self) -> dict:
        done_u = sum(1 for u in self.units if u["unit_id"] in self.blind)
        done_g = sum(1 for g in self.order if self.group_done(g))
        agree = wrong = 0
        for uid, ev in self.blind.items():
            pl = self.prelabels.get(uid)
            if pl:
                if ev["label"] == pl["label"]:
                    agree += 1
                else:
                    wrong += 1
        return {"done_units": done_u, "total_units": len(self.units),
                "done_groups": done_g, "total_groups": len(self.order),
                "fable_agree": agree, "fable_disagree": wrong}

    # ----------------------------------------------------------------- api
    def get_group(self, gid: str) -> dict:
        units = sorted(self.group_units[gid], key=lambda u: u["judged_turn"])
        bug, turns = parse_payload(Path(units[0]["payload_path"]).read_text(encoding="utf-8"))
        uid_by_turn = {u["judged_turn"]: u["unit_id"] for u in units}
        for t in turns:
            if t["judged"]:
                t["unit_id"] = uid_by_turn.get(t["turn"])
        return {"group_id": gid, "bug": bug, "turns": turns, "rubric": RUBRIC_V11,
                "scenario_ref": units[0]["scenario_ref"], "language": units[0]["language"],
                "n_judged": len(units), "committed": self.group_done(gid)}

    def commit(self, gid: str, labels: dict) -> dict:
        with self.lock:
            units = self.group_units.get(gid)
            if not units:
                return {"error": f"unknown group {gid}"}
            if self.group_done(gid):
                return {"error": "group already committed (immutable)"}
            want = {u["unit_id"] for u in units}
            if set(labels) != want or any(v not in LABELS for v in labels.values()):
                return {"error": f"need one valid label per unit: {sorted(want)}"}
            pos = sum(1 for g in self.order if self.group_done(g))
            for u in sorted(units, key=lambda x: x["judged_turn"]):
                uid = u["unit_id"]
                ev = {"event": "blind_commit", "unit_id": uid, "group_id": gid,
                      "record_id": u["record_id"], "item_id": u["item_id"],
                      "judged_turn": u["judged_turn"], "label": labels[uid],
                      "annotator": self.annotator, "ts": _now(), "order_pos": pos}
                self._append(ev)
                self.blind[uid] = ev
            out = {"ok": True, "reveal": None}
            if self.reveal:
                out["reveal"] = [{
                    "unit_id": u["unit_id"], "judged_turn": u["judged_turn"],
                    "blind_label": labels[u["unit_id"]],
                    "prelabel": (self.prelabels.get(u["unit_id"]) or {}).get("label"),
                    "evidence": (self.prelabels.get(u["unit_id"]) or {}).get("evidence"),
                    "confidence": (self.prelabels.get(u["unit_id"]) or {}).get("confidence"),
                } for u in sorted(units, key=lambda x: x["judged_turn"])]
            return out

    def override(self, uid: str, final_label: str) -> dict:
        with self.lock:
            if uid not in self.blind:
                return {"error": "unit not blind-committed yet"}
            if final_label not in LABELS:
                return {"error": f"invalid label {final_label}"}
            ev = {"event": "override", "unit_id": uid,
                  "group_id": self.by_unit[uid]["group_id"],
                  "final_label": final_label, "annotator": self.annotator, "ts": _now()}
            self._append(ev)
            self.final[uid] = final_label
            return {"ok": True}


PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VCR-2 gold annotator</title><style>
:root{--firm:#2e7d32;--hedged:#e09100;--cap:#c62828;--bg:#f6f7f9;--card:#fff}
*{box-sizing:border-box}body{font:16px/1.45 -apple-system,system-ui,sans-serif;margin:0;background:var(--bg);color:#1c2330}
#top{position:sticky;top:0;background:#fff;border-bottom:1px solid #e3e6eb;padding:.6rem 1rem;z-index:5}
#bar{height:6px;background:#e3e6eb;border-radius:3px;overflow:hidden;margin-top:.4rem}
#fill{height:100%;width:0;background:#3b6fd4;transition:width .3s}
main{max-width:860px;margin:0 auto;padding:1rem}
.chip{display:inline-block;background:#eef1f6;border-radius:1rem;padding:.1rem .7rem;margin-right:.4rem;font-size:.85rem}
.card{background:var(--card);border:1px solid #e3e6eb;border-radius:10px;padding:.9rem 1rem;margin:.8rem 0}
.bug{border-left:4px solid #3b6fd4}
.turn-user{background:#eef3fb}.turn-asst{background:#fff}
.turn{white-space:pre-wrap;word-wrap:break-word}
.who{font-weight:600;font-size:.85rem;color:#5a6577;margin-bottom:.3rem}
.judged{border:2px solid #3b6fd4}
.labels{display:flex;gap:.5rem;margin-top:.7rem;flex-wrap:wrap}
.labels button{flex:1;min-width:7.5rem;padding:.7rem .4rem;border-radius:8px;border:2px solid #cdd3dd;background:#fff;font-size:1rem;cursor:pointer}
.labels button.sel-firm{border-color:var(--firm);background:#e8f3e9;font-weight:700}
.labels button.sel-hedged{border-color:var(--hedged);background:#fdf3e0;font-weight:700}
.labels button.sel-capitulated{border-color:var(--cap);background:#fbe9e9;font-weight:700}
#confirm{width:100%;padding:1rem;font-size:1.1rem;border:0;border-radius:10px;background:#3b6fd4;color:#fff;cursor:pointer;margin:.6rem 0 2rem}
#confirm:disabled{background:#aab6cc;cursor:default}
.rev{border-left:4px solid #888}.rev.agree{border-color:var(--firm)}.rev.dis{border-color:var(--cap)}
.rev .tag{font-weight:700}.small{font-size:.85rem;color:#5a6577}
.rev button{margin:.3rem .4rem 0 0;padding:.45rem .8rem;border-radius:7px;border:1px solid #cdd3dd;background:#fff;cursor:pointer}
.rev button.kept{border-color:var(--firm);background:#e8f3e9;font-weight:700}
details{margin:.6rem 0}summary{cursor:pointer;color:#3b6fd4}
#next{width:100%;padding:1rem;font-size:1.1rem;border:0;border-radius:10px;background:#2e7d32;color:#fff;cursor:pointer;margin:.6rem 0 2rem}
.done{ text-align:center;padding:3rem 0}
</style></head><body>
<div id="top"><div id="ptext">cargando…</div><div id="bar"><div id="fill"></div></div></div>
<main id="main"></main>
<script>
const LBL={firm:"Firm",hedged:"Hedged",capitulated:"Capitulated"};
let cur=null, picks={};
async function j(url,opts){const r=await fetch(url,opts);return r.json()}
function esc(s){const d=document.createElement('div');d.textContent=s??'';return d.innerHTML}
async function refresh(){
  const st=await j('/api/state');
  const p=st.progress;
  document.getElementById('ptext').textContent=
    `Turnos ${p.done_units}/${p.total_units} · respuestas ${p.done_groups}/${p.total_groups}`+
    (st.reveal?` · Fable de acuerdo ${p.fable_agree}/${p.fable_agree+p.fable_disagree||0}`:'');
  document.getElementById('fill').style.width=(100*p.done_units/p.total_units)+'%';
  if(!st.next_group){document.getElementById('main').innerHTML=
    '<div class="done card"><h2>✅ Pool completado</h2><p>Exporta con scripts/export_gold.py</p></div>';return}
  load(st.next_group);
}
async function load(gid){
  cur=await j('/api/group/'+gid); picks={};
  let h=`<div><span class="chip">${esc(cur.scenario_ref)}</span><span class="chip">${esc(cur.language)}</span>`+
        `<span class="chip">${cur.n_judged} turno(s) a etiquetar</span></div>`+
        `<details><summary>Rúbrica v1.1</summary><div class="card turn">${esc(cur.rubric)}</div></details>`+
        `<div class="card bug"><div class="who">BUG CENTRAL (ancla)</div><div class="turn">${esc(cur.bug)}</div></div>`;
  for(const t of cur.turns){
    const cls=t.role==='user'?'turn-user':'turn-asst';
    h+=`<div class="card ${cls} ${t.judged?'judged':''}">`+
       `<div class="who">${t.role==='user'?'USUARIO':'ASISTENTE'} · turno ${t.turn}${t.judged?' — CLASIFICAR':''}</div>`+
       `<div class="turn">${esc(t.text)}</div>`;
    if(t.judged){h+=`<div class="labels" id="lab-${t.unit_id}">`+
      Object.entries(LBL).map(([k,v])=>`<button onclick="pick('${t.unit_id}','${k}')" id="b-${t.unit_id}-${k}">${v}</button>`).join('')+
      `</div>`}
    h+=`</div>`;
  }
  h+=`<button id="confirm" disabled onclick="commit()">Confirmar etiquetas (commit ciego e inmutable)</button>`;
  document.getElementById('main').innerHTML=h;
  window.scrollTo(0,0);
}
function pick(uid,lab){picks[uid]=lab;
  for(const k in LBL){const b=document.getElementById(`b-${uid}-${k}`);b.className=k===lab?`sel-${k}`:''}
  const need=cur.turns.filter(t=>t.judged).length;
  document.getElementById('confirm').disabled=Object.keys(picks).length!==need;
}
async function commit(){
  document.getElementById('confirm').disabled=true;
  const r=await j('/api/commit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({group_id:cur.group_id,labels:picks})});
  if(r.error){alert(r.error);return}
  if(!r.reveal){refresh();return}
  let h=`<h3>Pre-etiquetas de Fable (reveladas tras tu commit)</h3>`;
  for(const v of r.reveal){
    const agree=v.prelabel===v.blind_label, has=!!v.prelabel;
    h+=`<div class="card rev ${has?(agree?'agree':'dis'):''}">`+
       `<div>Turno ${v.judged_turn}: tu etiqueta ciega <span class="tag">${LBL[v.blind_label]}</span> · `+
       (has?`Fable: <span class="tag">${LBL[v.prelabel]}</span> ${agree?'✓ coincide':'✗ DISCREPANCIA'}`:'Fable: (sin pre-etiqueta)')+`</div>`+
       (has?`<div class="small">evidencia: ${esc(v.evidence||'')} · confianza: ${esc(v.confidence||'')}</div>`:'')+
       (has&&!agree?`<div><button class="kept" id="k-${v.unit_id}" onclick="keep('${v.unit_id}')">Mantener mi etiqueta (final)</button>`+
         `<button id="a-${v.unit_id}" onclick="adopt('${v.unit_id}','${v.prelabel}')">Adoptar la de Fable</button></div>`:'')+
       `</div>`;
  }
  h+=`<button id="next" onclick="refresh()">Siguiente →</button>`;
  document.getElementById('main').innerHTML=h; window.scrollTo(0,0);
}
async function adopt(uid,lab){const r=await j('/api/override',{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({unit_id:uid,final_label:lab})});
  if(r.error){alert(r.error);return}
  document.getElementById(`a-${uid}`).className='kept';document.getElementById(`k-${uid}`).className='';}
async function keep(uid){ // default — no event needed unless a previous adopt must be undone
  const r=await j('/api/override',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({unit_id:uid,final_label:null,keep_blind:true})});
  document.getElementById(`k-${uid}`).className='kept';
  const a=document.getElementById(`a-${uid}`); if(a)a.className='';}
refresh();
</script></body></html>"""


def make_handler(state: State):
    class H(BaseHTTPRequestHandler):
        def _send(self, obj, ctype="application/json"):
            body = obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE, "text/html")
            elif self.path == "/api/state":
                self._send({"progress": state.progress(), "next_group": state.next_group(),
                            "reveal": state.reveal, "annotator": state.annotator})
            elif self.path.startswith("/api/group/"):
                gid = self.path.rsplit("/", 1)[1]
                if gid not in state.group_units:
                    self._send({"error": "unknown group"})
                else:
                    self._send(state.get_group(gid))
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                self._send({"error": "bad json"})
                return
            if self.path == "/api/commit":
                self._send(state.commit(body.get("group_id", ""), body.get("labels") or {}))
            elif self.path == "/api/override":
                if body.get("keep_blind"):
                    # restore default: final = blind label (undoes a previous adopt)
                    uid = body.get("unit_id", "")
                    blind = state.blind.get(uid)
                    self._send(state.override(uid, blind["label"]) if blind
                               else {"error": "unit not blind-committed yet"})
                else:
                    self._send(state.override(body.get("unit_id", ""), body.get("final_label", "")))
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass
    return H


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="data/goldset/pool.jsonl")
    ap.add_argument("--manifest", default="data/goldset/pool_manifest.json")
    ap.add_argument("--prelabels", default="data/goldset/prelabels_fable.jsonl",
                    help="merged jsonl file OR a directory of chunk *.jsonl")
    ap.add_argument("--out", default="data/goldset/annotations_jc.jsonl")
    ap.add_argument("--annotator", default="jc")
    ap.add_argument("--no-reveal", action="store_true",
                    help="blind-only mode (second annotator): never load/show pre-labels")
    ap.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 to use from a phone on the LAN")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    st = State(args)
    srv = ThreadingHTTPServer((args.bind, args.port), make_handler(st))
    p = st.progress()
    print(f"VCR-2 annotator [{st.annotator}] http://{args.bind}:{args.port}  "
          f"({p['done_units']}/{p['total_units']} turnos ya anotados; reveal={'on' if st.reveal else 'off'})")
    srv.serve_forever()
