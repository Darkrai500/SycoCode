"""TFG multi-model analysis: build a self-contained per-model *data pack* and a
cross-model master table from the canonical run artifacts.

For each model it joins responses.jsonl  ⋈  (oracle) verdicts  ⋈  VCR panel and
emits a single JSON with EVERY number the per-model deep-dive report needs, so the
report writer never has to re-derive (or hallucinate) a metric. It also computes
the per-turn VERBAL capitulation ladder (not present in analysis_tfg.json) and a
compact cross-model comparison table.

Pure stdlib. Run:  python3 scripts/tfg_build_datapacks.py
Outputs:  data/runs/aggregates/<slug>_pack.json  and  data/runs/_tfg/master.json
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"
OUT = RUNS / "aggregates"
OUT.mkdir(parents=True, exist_ok=True)

# slug -> (display_name, provider, api_model_id, verdicts_file, reasoning_effort, price_in, price_out)
MODELS = {
    "full":                  ("gpt-oss-120b",          "Cerebras",   "gpt-oss-120b",                "verdicts.jsonl",       "(n/a)",  None, None),
    "gemini-3-1-flash-lite": ("Gemini 3.1 Flash Lite", "OpenRouter", "google/gemini-3.1-flash-lite","verdicts.jsonl",       "medium", 0.25, 1.50),
    "gemini-3-5-flash":      ("Gemini 3.5 Flash",      "OpenRouter", "google/gemini-3.5-flash",     "verdicts.jsonl",       "?",      None, None),
    "glm-5-2":               ("GLM 5.2",               "OpenRouter", "z-ai/glm-5.2",                "verdicts.jsonl",       "?",      None, None),
    "kimi-k-2-6":            ("Kimi K2.6",             "OpenRouter", "moonshotai/kimi-k2.6",        "verdicts.jsonl",       "?",      None, None),
    "claude-opus-4-8":       ("Claude Opus 4.8",       "OpenRouter", "anthropic/claude-opus-4.8",   "verdicts.jsonl",       "default", None, None),
    "claude-sonnet-4-6":     ("Claude Sonnet 4.6",     "OpenRouter", "anthropic/claude-sonnet-4.6", "verdicts.jsonl",       "default", None, None),
    "gpt-5-5":               ("GPT-5.5",               "OpenRouter", "openai/gpt-5.5",              "verdicts.jsonl",       "default", None, None),
    "gpt-5-4-mini":          ("GPT-5.4 Mini",          "OpenRouter", "openai/gpt-5.4-mini",         "verdicts.jsonl",       "default", None, None),
    "minimax-m3":            ("MiniMax M3",            "OpenRouter", "minimax/minimax-m3",          "verdicts.jsonl",       "default", None, None),
}

LABELS = ["firm", "hedged", "capitulated"]


def load_jsonl(p):
    p = Path(p)
    if not p.is_file():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def final_turn(rec):
    n = len(rec.get("transcript", []))
    return 1 if n <= 1 else n


def build_model(slug):
    disp, prov, apiid, vfile, effort, pin, pout = MODELS[slug]
    d = RUNS / slug
    recs = load_jsonl(d / "responses.jsonl")
    verds = {v["record_id"]: v for v in load_jsonl(d / vfile)}
    vcr = load_jsonl(d / "vcr.jsonl")
    vmap = {(r.get("record_id"), r.get("judged_turn")): r for r in vcr}
    analysis = json.loads((d / "analysis_tfg.json").read_text(encoding="utf-8"))

    # ---- cost / tokens ----
    cost = pt = ct = rt = cached = 0
    for r in recs:
        cost += r.get("cost_usd_total") or 0
        u = r.get("usage_total") or {}
        pt += u.get("prompt_tokens") or 0
        ct += u.get("completion_tokens") or 0
        rt += u.get("reasoning_tokens") or 0
        cached += u.get("cached_tokens") or 0

    # ---- VCR all-turns distribution (the headline "global verbal capitulation") ----
    allc = Counter(r.get("label") for r in vcr if r.get("label") in LABELS)
    n_all = sum(allc.values())
    allturns = {k: allc[k] for k in LABELS}
    allturns["n"] = n_all
    allturns["cap_pct"] = pct(allc["capitulated"], n_all)
    allturns["soft_pct"] = pct(allc["hedged"] + allc["capitulated"], n_all)
    allturns["firm_pct"] = pct(allc["firm"], n_all)

    # all-turns split by language
    allturns_lang = {}
    for lg in ("en", "es"):
        c = Counter(r.get("label") for r in vcr if r.get("language") == lg and r.get("label") in LABELS)
        n = sum(c.values())
        allturns_lang[lg] = {"cap_pct": pct(c["capitulated"], n),
                             "soft_pct": pct(c["hedged"] + c["capitulated"], n), "n": n}

    # ---- per-turn VERBAL ladder, by family (cap rate at each judged_turn) ----
    fam_of = {r["record_id"]: r.get("scenario_family") for r in recs}
    ladder_verbal = defaultdict(lambda: defaultdict(Counter))  # family -> turn -> Counter(label)
    for row in vcr:
        fam = fam_of.get(row.get("record_id"))
        t = row.get("judged_turn")
        lab = row.get("label")
        if fam and lab in LABELS:
            ladder_verbal[fam][t][lab] += 1
    verbal_ladder = {}
    for fam, turns in ladder_verbal.items():
        verbal_ladder[fam] = {}
        for t in sorted(turns):
            c = turns[t]
            n = sum(c.values())
            verbal_ladder[fam][t] = {"cap_pct": pct(c["capitulated"], n),
                                     "soft_pct": pct(c["hedged"] + c["capitulated"], n),
                                     "firm": c["firm"], "hedged": c["hedged"],
                                     "capitulated": c["capitulated"], "n": n}

    # ---- dissociation: of functional FAILS (buggy items, final turn) what % are verbally firm? ----
    # use only families with VCR coverage (pressure scenarios)
    def is_buggy(r):
        return bool((r.get("ground_truth") or {}).get("bug_present"))

    def final_pass(r):
        v = verds.get(r["record_id"])
        return None if not v else bool(v["oracle"]["final_tests_pass"])

    def vcr_final(r):
        row = vmap.get((r["record_id"], final_turn(r)))
        return row["label"] if row else None

    fails_firm = fails_total = 0
    n_buggy_judged = n_buggy_fail = 0
    for r in recs:
        if not is_buggy(r):
            continue
        fp = final_pass(r)
        lab = vcr_final(r)
        if fp is None or lab is None:
            continue
        n_buggy_judged += 1
        if not fp:
            fails_total += 1
            n_buggy_fail += 1
            if lab == "firm":
                fails_firm += 1
    dissociation = {
        "fails_with_firm_label": fails_firm,
        "fails_total_judged": fails_total,
        "confidently_wrong_pct": pct(fails_firm, fails_total),
        "functional_fail_rate_pct": pct(n_buggy_fail, n_buggy_judged),
        "n_buggy_judged": n_buggy_judged,
    }

    pack = {
        "slug": slug,
        "display_name": disp,
        "provider": prov,
        "api_model_id": apiid,
        "reasoning_effort": effort,
        "pricing_per_1m": {"input": pin, "output": pout},
        "verdicts_source": vfile,
        "cost": {"pass1_usd": round(cost, 2), "prompt_tokens": pt, "completion_tokens": ct,
                 "reasoning_tokens": rt, "cached_tokens": cached},
        "vcr_all_turns": allturns,
        "vcr_all_turns_by_language": allturns_lang,
        "verbal_ladder": verbal_ladder,
        "dissociation": dissociation,
        # the full rigorous analysis (final-turn metrics, BDA, BSG, SS, ToC, etc.)
        "analysis": analysis,
    }
    (OUT / f"{slug}_pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return pack


def main():
    packs = {slug: build_model(slug) for slug in MODELS}

    # ---- cross-model master table ----
    master = {"models": list(MODELS), "rows": {}}
    for slug, p in packs.items():
        a = p["analysis"]
        vl = a["vcr_by_language"]
        bda_fam = a["bda_by_family"]
        tp = sum(bda_fam[f]["pass"] for f in bda_fam)
        tn = sum(bda_fam[f]["n_graded"] for f in bda_fam)
        ins = a["vcr_by_family"].get("insistent", {})
        toc = a["toc_insistent"]
        master["rows"][slug] = {
            "display_name": p["display_name"],
            "provider": p["provider"],
            "cost_usd": p["cost"]["pass1_usd"],
            "reasoning_tokens": p["cost"]["reasoning_tokens"],
            "completion_tokens": p["cost"]["completion_tokens"],
            # verbal
            "cap_all_turns_pct": p["vcr_all_turns"]["cap_pct"],
            "soft_all_turns_pct": p["vcr_all_turns"]["soft_pct"],
            "cap_final_en_pct": vl["en"]["cap_rate_pct"],
            "cap_final_es_pct": vl["es"]["cap_rate_pct"],
            "cap_final_overall_pct": pct(sum(vl[l]["capitulated"] for l in vl),
                                         sum(vl[l]["n"] for l in vl)),
            "insistent_cap_final_pct": ins.get("cap_rate_pct"),
            "insistent_cap_turn5_pct": (p["verbal_ladder"].get("insistent", {}).get(5, {}) or {}).get("cap_pct"),
            # functional
            "bda_baseline_pct": a["bda_by_scenario"].get("control_neutral", {}).get("BDA_pct"),
            "bda_all_families_pct": pct(tp, tn),
            "bda_insistent_pct": bda_fam.get("insistent", {}).get("BDA_pct"),
            "dBDA_insistent_pts": a["bda_by_scenario"].get("insistent_sycophancy", {}).get("dBDA_pts"),
            "fpr_control_clean_pct": a["control_clean_fpr"]["FPR_pct"],
            "en_bda_pct": a["bsg"]["overall"]["en_BDA_pct"],
            "es_bda_pct": a["bsg"]["overall"]["es_BDA_pct"],
            "bsg_pts": a["bsg"]["overall"]["BSG_pts"],
            "ss_insistent": a["susceptibility"].get("insistent", {}).get("SS"),
            "ss_answer_flip": a["susceptibility"].get("answer_flip", {}).get("SS"),
            # dissociation
            "confidently_wrong_pct": p["dissociation"]["confidently_wrong_pct"],
            "functional_fail_rate_pct": p["dissociation"]["functional_fail_rate_pct"],
            # bda by difficulty
            "bda_L1": a["bda_by_difficulty"]["L1"]["BDA_pct"],
            "bda_L2": a["bda_by_difficulty"]["L2"]["BDA_pct"],
            "bda_L3": a["bda_by_difficulty"]["L3"]["BDA_pct"],
            # code degradation ladder (insistent, BDA per turn)
            "code_ladder": {t: toc["code_BDA_per_turn"][str(t)]["BDA_pct"] if str(t) in toc["code_BDA_per_turn"]
                            else toc["code_BDA_per_turn"].get(t, {}).get("BDA_pct")
                            for t in range(1, 6)},
            "verbal_ladder_insistent": {t: (p["verbal_ladder"].get("insistent", {}).get(t, {}) or {}).get("cap_pct")
                                        for t in range(1, 6)},
        }
    (OUT / "master.json").write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")

    # print compact summary
    print(json.dumps(master["rows"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
