#!/usr/bin/env python3
"""Sensitivity of the functional results to the code-attribution rule.

Recomputes, from the public replay ledgers in ``data/replay/`` only (no
response text), the quantities reported in Section 4.2 and Supplementary S6 of
the article:

* flip rate, pairwise model contrasts and BSG under the documented rule and
  the three alternative attribution rules (capitulated only, never, every
  extracted block), with the same estimators, bootstrap and Holm families as
  ``scripts/revision_analysis.py``;
* the split of the 1,215 flips by scenario type (single-turn / multi-turn),
  origin of the failing final code and last verbal label (the 320 pilot turns
  take the label of the human reference in ``data/reeval/``).

Read-only: makes no model call, executes no corpus code and writes only
``--out`` (and ``--tables`` if given). It first checks that the documented rule
reproduces the released ``data/replay/statistics.json`` exactly and stops
otherwise. Needs NumPy only. From the repository root:

    python scripts/policy_sensitivity.py --out data/replay/policy_sensitivity.json

``--tables DIR`` also writes the LaTeX table bodies used in the supplement.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

RULES = [("historical", "As run"), ("cap_only", "Capitulated only"),
         ("no_requotes", "No quotes"), ("all_extracted", "All blocks")]
NAMES = [("claude-opus-4-8", "Claude Opus 4.8"), ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
         ("gemini-3-1-flash-lite", "Gemini 3.1 Flash Lite"), ("gemini-3-5-flash", "Gemini 3.5 Flash"),
         ("glm-5-2", "GLM 5.2"), ("gpt-5-4-mini", "GPT-5.4 Mini"), ("gpt-5-5", "GPT-5.5"),
         ("full", "gpt-oss-120b"), ("kimi-k-2-6", "Kimi K2.6"), ("minimax-m3", "MiniMax M3")]
DISPLAY = dict(NAMES)


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    return float(np.corrcoef(rx, ry)[0, 1])


def final_source(turns):
    """Turn whose adopted block set the final state under the documented rule."""
    source = None
    for t in sorted(turns, key=lambda t: t["turn"]):
        if t["extraction_reason"] != "last_block_with_entrypoint":
            continue
        if t["block_pass"] or not t["requote"] or t["label"] in ("hedged", "capitulated"):
            source = t
    return source


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", type=Path, default=Path(__file__).resolve().parents[1],
                    help="Repository checkout to read (default: the one holding this script).")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tables", type=Path, help="Directory for the LaTeX table bodies.")
    a = ap.parse_args()

    sys.path.insert(0, str(a.release / "scripts"))  # also under python -I
    import revision_analysis as ra  # noqa: E402

    replay = a.release / "data/replay"
    items = defaultdict(list)
    for r in read_gz(replay / "item_ledger.jsonl.gz"):
        items[r["model"]].append(r)
    turns = defaultdict(list)
    for t in read_gz(replay / "turn_ledger.jsonl.gz"):
        turns[t["record_id"]].append(t)
    saved = json.loads((replay / "statistics.json").read_text())
    problems = sorted({r["problem"] for rows in items.values() for r in rows})
    B, seed = saved["config"]["B"], saved["config"]["seed"]

    def unweighted_pairs():
        """Pairwise contrasts under the documented rule without severity weights."""
        inf = ra.Inference(problems, B, seed)
        conds = {slug: ra.metric(items[slug])[1] for slug in ra.MODELS}
        ps = []
        for x, y in itertools.combinations(ra.MODELS, 2):
            xx = {r["item_id"]: r for r in conds[x]}
            yy = {r["item_id"]: r for r in conds[y]}
            pairs = [dict(xx[k], diff=xx[k]["flip"] - yy[k]["flip"]) for k in sorted(xx.keys() & yy.keys())]
            ps.append(inf.estimate(pairs, lambda r: r["diff"], paired_test=True)["p_cluster_signflip"])
        return sum(p < 0.05 for p in ra.holm(ps))

    def run(rule):
        inf = ra.Inference(problems, B, seed)
        conds, fr, bsg = {}, {}, {}
        for slug in ra.MODELS:
            _, cond = ra.metric(items[slug], rule)
            conds[slug] = cond
            fr[slug] = inf.estimate(cond, lambda r: r["flip"])
            pairs = ra.paired_language([r for r in cond if r["family"] in ra.RETAINED])
            bsg[slug] = inf.estimate(pairs, lambda r: r["diff"], paired_test=True)
        for slug, p in zip(ra.MODELS, ra.holm([bsg[s]["p_cluster_signflip"] for s in ra.MODELS])):
            bsg[slug]["p_holm"] = p
        pw = []
        for x, y in itertools.combinations(ra.MODELS, 2):
            xx = {r["item_id"]: r for r in conds[x]}
            yy = {r["item_id"]: r for r in conds[y]}
            pairs = [dict(xx[k], diff=xx[k]["flip"] - yy[k]["flip"]) for k in sorted(xx.keys() & yy.keys())]
            pw.append(dict(a=x, b=y, **inf.estimate(pairs, lambda r: r["diff"], lambda r: ra.WEIGHTS[r["level"]], True)))
        for r, p in zip(pw, ra.holm([r["p_cluster_signflip"] for r in pw])):
            r["p_holm"] = p
        return fr, bsg, pw

    results = {rule: run(rule) for rule, _ in RULES}

    # ---- the documented rule must reproduce the released statistics ----
    fr0, bsg0, pw0 = results["historical"]
    for slug in ra.MODELS:
        s = saved["models"][slug]
        if not (abs(s["fr"]["estimate"] - fr0[slug]["estimate"]) < 1e-12
                and np.allclose(s["fr"]["ci95"], fr0[slug]["ci95"])
                and abs(s["bsg_common_support"]["estimate"] - bsg0[slug]["estimate"]) < 1e-12
                and np.allclose(s["bsg_common_support"]["ci95"], bsg0[slug]["ci95"])
                and abs(s["bsg_common_support"]["p_holm_within_10_models"] - bsg0[slug]["p_holm"]) < 1e-12):
            raise SystemExit(f"Released statistics not reproduced for {slug}")
    sig0 = {(r["a"], r["b"]) for r in pw0 if r["p_holm"] < 0.05}
    if sig0 != {(r["a"], r["b"]) for r in saved["pairwise_models"] if r["p_holm_within_45_pairs"] < 0.05}:
        raise SystemExit("Released pairwise contrasts not reproduced")
    sign0 = {(r["a"], r["b"]): np.sign(r["estimate"]) for r in pw0}
    base = [fr0[s]["estimate"] for s in ra.MODELS]

    out = {"inputs": {name: sha(replay / name) for name in ("item_ledger.jsonl.gz", "turn_ledger.jsonl.gz", "statistics.json")},
           "config": {"B": B, "seed": seed, "clusters": len(problems)},
           "reproduces_released_statistics": True, "rules": {}}
    in_all = set(sig0)
    for rule, _ in RULES:
        fr, bsg, pw = results[rule]
        frs = [fr[s]["estimate"] for s in ra.MODELS]
        order = [s for _, s in sorted(zip(frs, ra.MODELS))]
        sig = {(r["a"], r["b"]) for r in pw if r["p_holm"] < 0.05}
        est = {(r["a"], r["b"]): r["estimate"] for r in pw}
        in_all &= sig
        out["rules"][rule] = {
            "fr_pct": {s: round(100 * fr[s]["estimate"], 2) for s in ra.MODELS},
            "order_low_to_high": order,
            "spearman_vs_as_run": round(spearman(base, frs), 3),
            "max_abs_fr_change_pp": round(100 * max(abs(x - y) for x, y in zip(frs, base)), 2),
            "pairs_significant": len(sig),
            "as_run_pairs_kept": len(sig & sig0),
            "as_run_pairs_lost": sorted(map(list, sig0 - sig)),
            "pairs_new": sorted(map(list, sig - sig0)),
            "sign_reversals_among_kept": int(sum(bool(np.sign(est[k]) != sign0[k]) for k in sig & sig0)),
            "bsg_pp": {s: round(100 * bsg[s]["estimate"], 2) for s in ra.MODELS},
            "bsg_ci95_pp": {s: [round(100 * v, 2) for v in bsg[s]["ci95"]] for s in ra.MODELS},
            "bsg_pairs": {s: bsg[s]["n"] for s in ra.MODELS},
            "bsg_p_holm": {s: round(bsg[s]["p_holm"], 4) for s in ra.MODELS},
            "bsg_significant_after_holm": [s for s in ra.MODELS if bsg[s]["p_holm"] < 0.05],
        }
    out["as_run_pairs_significant_under_all_four_rules"] = len(in_all)
    # The released contrasts weight failures by bug severity (1/2/3); for reference:
    out["as_run_pairs_significant_without_severity_weights"] = int(unweighted_pairs())
    h, n = out["rules"]["historical"]["bsg_pp"], out["rules"]["no_requotes"]["bsg_pp"]
    shift = {s: round(n[s] - h[s], 2) for s in ra.MODELS}
    out["bsg_no_quotes_minus_as_run_pp"] = shift
    out["bsg_no_quotes_minus_as_run_mean_pp"] = round(float(np.mean([n[s] - h[s] for s in ra.MODELS])), 2)
    out["bsg_no_quotes_models_moving_towards_english"] = sum(v < 0 for v in shift.values())

    # ---- flips by scenario type, origin of the final code and last verbal label ----
    overlay = {}
    reference = a.release / "data/reeval/human_reference_v1.jsonl"
    for line in reference.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            overlay[(r["record_id"], int(r["judged_turn"]))] = r["reference_label"]
    c = Counter()
    for slug in ra.MODELS:
        for r in items[slug]:
            judged = [t["turn"] for t in turns[r["record_id"]] if t["label"] is not None]
            if judged and (r["record_id"], max(judged)) in overlay:
                r["final_label"] = overlay[(r["record_id"], max(judged))]
        _, cond = ra.metric(items[slug])
        for r in cond:
            kind = "multi" if r["family"] in ra.MULTI else "single"
            c[f"{kind}::eligible"] += 1
            if not r["flip"]:
                continue
            if r["final_label"] not in ra.LABELS:
                raise SystemExit(f"Flip without a final verbal label: {r['record_id']}")
            src = final_source(turns[r["record_id"]])
            origin = "no_code" if src is None else ("user_code" if src["requote"] else "own_code")
            for key in ("flips", r["final_label"], origin):
                c[f"{kind}::{key}"] += 1
    out["flips"] = dict(sorted(c.items()))

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

    if a.tables:
        def write(name, lines):
            (a.tables / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

        rows = []
        for rule, label in RULES:
            x = out["rules"][rule]
            frs = x["fr_pct"]
            lo, hi = x["order_low_to_high"][0], x["order_low_to_high"][-1]
            n_bsg = len(x["bsg_significant_after_holm"])
            rows.append(" & ".join([
                label, f"{frs[lo]:.2f}--{frs[hi]:.2f}", DISPLAY[lo], DISPLAY[hi],  # two decimals, as stored: rounding these again to one would double-round 4.649 to 4.7
                "--" if rule == "historical" else f"{x['spearman_vs_as_run']:.2f}",
                str(x["pairs_significant"]),
                "--" if rule == "historical" else str(x["as_run_pairs_kept"]),
                str(n_bsg)]) + "\\\\")
        write("s6_policy_holds", rows)

        rows = []
        for slug, label in NAMES:
            cells = []
            for rule, _ in RULES:
                x = out["rules"][rule]
                mark = "$^{\\S}$" if slug in x["bsg_significant_after_holm"] else ""
                cells.append(f"{x['bsg_pp'][slug]:.2f}{mark} ({x['bsg_pairs'][slug]})")
            rows.append(" & ".join([label, *cells]) + "\\\\")
        write("s6_policy_bsg", rows)

        rows = []
        tot = Counter()
        for kind, label in (("single", "Single-turn"), ("multi", "Multi-turn")):
            vals = [c[f"{kind}::{k}"] for k in ("eligible", "flips", "user_code", "own_code", "no_code",
                                               "firm", "hedged", "capitulated")]
            tot.update(dict(enumerate(vals)))
            rows.append(" & ".join([label, *(f"{v:,}" for v in vals)]) + "\\\\")
        rows.append("\\hline")
        rows.append(" & ".join(["All", *(f"{tot[i]:,}" for i in range(8))]) + "\\\\")
        write("s6_flip_split", rows)

    for rule, label in RULES:
        x = out["rules"][rule]
        print(f"{label:17s} FR {min(x['fr_pct'].values()):5.2f}-{max(x['fr_pct'].values()):5.2f}  "
              f"rho {x['spearman_vs_as_run']:.3f}  pairs {x['pairs_significant']} "
              f"(kept {x['as_run_pairs_kept']}, reversals {x['sign_reversals_among_kept']})  "
              f"BSG significant: {x['bsg_significant_after_holm'] or 'none'}")
    print("as-run pairs significant under all four rules:", len(in_all),
          "| without severity weights:", out["as_run_pairs_significant_without_severity_weights"])
    print("BSG no quotes minus as run, mean pp:", out["bsg_no_quotes_minus_as_run_mean_pp"])
    print("flips:", out["flips"])


if __name__ == "__main__":
    main()
