"""TFG figure suite for the 5-model SycoCode sycophancy comparison.

Reads data/runs/aggregates/{master.json, <slug>_pack.json} and renders a cohesive,
publication-quality figure set to docs/figures/. Pure matplotlib (Agg).

Run:  .venv/bin/python scripts/tfg_make_figures.py
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager  # noqa: F401
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TFG = ROOT / "data" / "runs" / "aggregates"
FIG = ROOT / "docs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

master = json.loads((TFG / "master.json").read_text(encoding="utf-8"))
rows = master["rows"]
packs = {s: json.loads((TFG / f"{s}_pack.json").read_text(encoding="utf-8")) for s in rows}

# robustness ordering (insistent verbal capitulation ascending)
ORDER = sorted(rows, key=lambda s: rows[s]["insistent_cap_final_pct"])
NAMES = [rows[s]["display_name"] for s in ORDER]

# Okabe-Ito colorblind-safe palette, one stable colour per model
COLOR = {
    "full":                  "#0072B2",  # blue
    "glm-5-2":               "#009E73",  # green
    "kimi-k-2-6":            "#E69F00",  # orange
    "gemini-3-1-flash-lite": "#CC79A7",  # pink
    "gemini-3-5-flash":      "#D55E00",  # vermillion
    "claude-opus-4-8":       "#762A83",  # dark purple (Anthropic)
    "claude-sonnet-4-6":     "#9970AB",  # medium purple (Anthropic)
    "gpt-5-5":               "#56B4E9",  # sky blue (OpenAI)
    "gpt-5-4-mini":          "#44AA99",  # teal (OpenAI mini)
    "minimax-m3":            "#882255",  # wine (MiniMax)
}
COLORS = [COLOR[s] for s in ORDER]

plt.rcParams.update({
    "figure.dpi": 140, "savefig.dpi": 160, "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.labelsize": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "-",
    "axes.axisbelow": True, "font.family": "DejaVu Sans",
})
FOOT = "SycoCode · 1900 ítems (50 problemas × bug × 7 escenarios × EN/ES) · mismo panel VCR y oráculo · scripts/analyze_full_corpus.py"


def _foot(fig):
    fig.text(0.005, 0.005, FOOT, fontsize=6.5, color="#888", ha="left", va="bottom")


def _labels(ax, bars, fmt="{:.1f}", dy=0.5, fs=9):
    for b in bars:
        h = b.get_height()
        if h is None:
            continue
        ax.text(b.get_x() + b.get_width() / 2, h + dy, fmt.format(h),
                ha="center", va="bottom", fontsize=fs)


def save(fig, name):
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    p = FIG / name
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", p.relative_to(ROOT))


# ---------------------------------------------------------------- Fig 1: verbal capitulation headline
def fig1():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.2))
    x = np.arange(len(ORDER))
    # A: all-turns vs final-turn overall
    allt = [rows[s]["cap_all_turns_pct"] for s in ORDER]
    fin = [rows[s]["cap_final_overall_pct"] for s in ORDER]
    w = 0.38
    b1 = axA.bar(x - w/2, allt, w, label="todos los turnos (2400)", color=COLORS, alpha=0.55, edgecolor="white")
    b2 = axA.bar(x + w/2, fin, w, label="turno final (1500 presión)", color=COLORS, edgecolor="white")
    _labels(axA, b1, dy=0.4, fs=8); _labels(axA, b2, dy=0.4, fs=8)
    axA.set_title("Capitulación verbal global")
    axA.set_ylabel("% capitulado"); axA.set_xticks(x); axA.set_xticklabels(NAMES, rotation=18, ha="right")
    axA.legend(fontsize=8, frameon=False)
    # B: EN vs ES final turn
    en = [rows[s]["cap_final_en_pct"] for s in ORDER]
    es = [rows[s]["cap_final_es_pct"] for s in ORDER]
    b3 = axB.bar(x - w/2, en, w, label="EN", color="#4C72B0", edgecolor="white")
    b4 = axB.bar(x + w/2, es, w, label="ES", color="#DD8452", edgecolor="white")
    _labels(axB, b3, dy=0.4, fs=8); _labels(axB, b4, dy=0.4, fs=8)
    axB.set_title("Capitulación verbal por idioma (turno final)")
    axB.set_ylabel("% capitulado"); axB.set_xticks(x); axB.set_xticklabels(NAMES, rotation=18, ha="right")
    axB.legend(fontsize=9, frameon=False)
    fig.suptitle("Capa verbal (VCR): ¿el modelo cede el discurso bajo presión?", fontsize=14, fontweight="bold")
    _foot(fig); save(fig, "fig01_capitulacion_headline.png")


# ---------------------------------------------------------------- Fig 2: baseline vs all-families BDA
def fig2():
    fig, ax = plt.subplots(figsize=(10, 5.4))
    y = np.arange(len(ORDER))
    base = [rows[s]["bda_baseline_pct"] for s in ORDER]
    allf = [rows[s]["bda_all_families_pct"] for s in ORDER]
    h = 0.38
    ax.barh(y + h/2, base, h, label="control neutro (sin presión)", color=COLORS, edgecolor="white")
    ax.barh(y - h/2, allf, h, label="todas las familias (con presión)", color=COLORS, alpha=0.5, edgecolor="white")
    for i, s in enumerate(ORDER):
        ax.text(base[i] + 0.8, y[i] + h/2, f"{base[i]:.1f}", va="center", fontsize=9)
        ax.text(allf[i] + 0.8, y[i] - h/2, f"{allf[i]:.1f}", va="center", fontsize=9, color="#555")
    ax.set_yticks(y); ax.set_yticklabels(NAMES); ax.set_xlabel("BDA (%) — código final pasa los tests (ítems con bug)")
    ax.set_title("Competencia funcional: BDA en reposo vs bajo presión")
    ax.legend(fontsize=9, frameon=False, loc="lower right"); ax.set_xlim(0, 100)
    _foot(fig); save(fig, "fig02_bda_baseline.png")


# ---------------------------------------------------------------- Fig 3: insistent verbal ladder
def fig3():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    turns = [2, 3, 4, 5]
    for s, c in zip(ORDER, COLORS):
        vl = rows[s]["verbal_ladder_insistent"]
        ys = [vl[str(t)] if str(t) in vl else vl.get(t) for t in turns]
        ax.plot(turns, ys, "-o", color=c, lw=2.4, ms=7, label=rows[s]["display_name"])
        ax.text(5.05, ys[-1], f"{ys[-1]:.0f}", color=c, va="center", fontsize=9, fontweight="bold")
    ax.set_xticks(turns); ax.set_xlabel("turno de la escalera insistente"); ax.set_ylabel("% capitulado (verbal)")
    ax.set_title("Dosis–respuesta verbal: capitulación a lo largo de la presión insistente")
    ax.legend(fontsize=9, frameon=False, loc="upper left"); ax.set_ylim(-2, 100); ax.set_xlim(1.8, 5.4)
    _foot(fig); save(fig, "fig03_insistente_verbal.png")


# ---------------------------------------------------------------- Fig 4: insistent code ladder
def fig4():
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    turns = [1, 2, 3, 4, 5]
    for s, c in zip(ORDER, COLORS):
        cl = rows[s]["code_ladder"]
        ys = [cl[str(t)] if str(t) in cl else cl.get(t) for t in turns]
        ax.plot(turns, ys, "-o", color=c, lw=2.4, ms=7, label=rows[s]["display_name"])
        ax.text(5.05, ys[-1], f"{ys[-1]:.0f}", color=c, va="center", fontsize=9, fontweight="bold")
    ax.set_xticks(turns); ax.set_xlabel("turno de la escalera insistente"); ax.set_ylabel("BDA (%) — código pasa tests")
    ax.set_title("Colapso funcional: degradación del código bajo presión insistente")
    ax.legend(fontsize=9, frameon=False, loc="upper right"); ax.set_ylim(-2, 100); ax.set_xlim(0.7, 5.4)
    _foot(fig); save(fig, "fig04_insistente_codigo.png")


# ---------------------------------------------------------------- Fig 5: dBDA heatmap by scenario
def fig5():
    scen = ["code_review_sycophancy", "expertise_deference_senior", "expertise_deference_student",
            "answer_flip_sycophancy", "insistent_sycophancy"]
    slabels = ["code_review", "expertise\n(senior)", "expertise\n(student)", "answer_flip", "insistent"]
    M = np.zeros((len(ORDER), len(scen)))
    for i, s in enumerate(ORDER):
        bsc = packs[s]["analysis"]["bda_by_scenario"]
        for j, sc in enumerate(scen):
            M[i, j] = bsc.get(sc, {}).get("dBDA_pts") or 0
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    im = ax.imshow(M, cmap="RdYlGn", vmin=-85, vmax=10, aspect="auto")
    ax.set_xticks(range(len(scen))); ax.set_xticklabels(slabels, fontsize=9)
    ax.set_yticks(range(len(ORDER))); ax.set_yticklabels(NAMES)
    for i in range(len(ORDER)):
        for j in range(len(scen)):
            v = M[i, j]
            ax.text(j, i, f"{v:+.0f}", ha="center", va="center",
                    color="black" if v > -45 else "white", fontsize=9, fontweight="bold")
    ax.set_title("ΔBDA por escenario de presión (puntos vs control neutro)")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.set_label("ΔBDA (pp)")
    _foot(fig); save(fig, "fig05_dbda_heatmap.png")


# ---------------------------------------------------------------- Fig 6: bilingual gap
def fig6():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.2))
    x = np.arange(len(ORDER)); w = 0.38
    # A: functional BDA EN vs ES
    en = [rows[s]["en_bda_pct"] for s in ORDER]; es = [rows[s]["es_bda_pct"] for s in ORDER]
    b1 = axA.bar(x - w/2, en, w, label="EN", color="#4C72B0", edgecolor="white")
    b2 = axA.bar(x + w/2, es, w, label="ES", color="#DD8452", edgecolor="white")
    _labels(axA, b1, dy=0.5, fs=8); _labels(axA, b2, dy=0.5, fs=8)
    axA.set_title("BDA funcional por idioma (todos los ítems con bug)")
    axA.set_ylabel("BDA %"); axA.set_xticks(x); axA.set_xticklabels(NAMES, rotation=18, ha="right")
    axA.legend(fontsize=9, frameon=False); axA.set_ylim(0, 100)
    # B: BSG points (EN-ES), diverging
    bsg = [rows[s]["bsg_pts"] for s in ORDER]
    cols = ["#2a9d8f" if v >= 0 else "#e76f51" for v in bsg]
    bb = axB.bar(x, bsg, 0.5, color=cols, edgecolor="white")
    for b, v in zip(bb, bsg):
        axB.text(b.get_x() + b.get_width()/2, v + (0.15 if v >= 0 else -0.15),
                 f"{v:+.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    axB.axhline(0, color="#333", lw=0.8)
    axB.set_title("Brecha bilingüe funcional BSG = BDA(EN) − BDA(ES)")
    axB.set_ylabel("puntos (>0: EN mejor)"); axB.set_xticks(x); axB.set_xticklabels(NAMES, rotation=18, ha="right")
    fig.suptitle("Brecha bilingüe: ¿se rinde distinto en español que en inglés?", fontsize=14, fontweight="bold")
    _foot(fig); save(fig, "fig06_brecha_bilingue.png")


# ---------------------------------------------------------------- Fig 7: confidently wrong (dissociation)
def fig7():
    fig, ax = plt.subplots(figsize=(10, 5.4))
    x = np.arange(len(ORDER))
    cw = [rows[s]["confidently_wrong_pct"] for s in ORDER]
    ff = [rows[s]["functional_fail_rate_pct"] for s in ORDER]
    w = 0.38
    b1 = ax.bar(x - w/2, cw, w, label="% de fallos funcionales con discurso FIRME", color=COLORS, edgecolor="white")
    b2 = ax.bar(x + w/2, ff, w, label="tasa de fallo funcional global", color=COLORS, alpha=0.45, edgecolor="white")
    _labels(ax, b1, dy=0.6, fs=8); _labels(ax, b2, dy=0.6, fs=8)
    ax.set_title("Disociación verbal × funcional: el ‘confidently wrong’")
    ax.set_ylabel("%"); ax.set_xticks(x); ax.set_xticklabels(NAMES, rotation=18, ha="right")
    ax.legend(fontsize=8.5, frameon=False); ax.set_ylim(0, 100)
    _foot(fig); save(fig, "fig07_confidently_wrong.png")


# ---------------------------------------------------------------- Fig 8: capable-but-fragile quadrant
def fig8():
    fig, ax = plt.subplots(figsize=(9.5, 6.6))
    xs = [rows[s]["bda_baseline_pct"] for s in ORDER]
    ys = [rows[s]["insistent_cap_final_pct"] for s in ORDER]
    cost = [rows[s]["cost_usd"] for s in ORDER]
    sizes = [120 + (c ** 0.9) * 22 for c in cost]
    # per-model label offsets to de-collide the low-capitulation bottom cluster
    OFF = {"full": (-8, 10, "right"), "claude-sonnet-4-6": (-6, -20, "right"),
           "claude-opus-4-8": (-8, 12, "right"), "gpt-5-5": (12, -6, "left"),
           "glm-5-2": (-8, 10, "right"), "gemini-3-5-flash": (-10, 8, "right")}
    for s, xx, yy, ss, c in zip(ORDER, xs, ys, sizes, COLORS):
        ax.scatter(xx, yy, s=ss, color=c, alpha=0.85, edgecolor="black", lw=0.8, zorder=3)
        dx, dy, ha = OFF.get(s, (10, 8, "left"))
        ax.annotate(f"{rows[s]['display_name']}\n(${rows[s]['cost_usd']:.0f})",
                    (xx, yy), textcoords="offset points", xytext=(dx, dy), ha=ha,
                    fontsize=9, fontweight="bold")
    xm = float(np.mean(xs)); ym = float(np.mean(ys))
    ax.axvline(xm, color="#bbb", ls="--", lw=1); ax.axhline(ym, color="#bbb", ls="--", lw=1)
    ax.text(0.985, 0.82, "capaz pero frágil", transform=ax.transAxes, ha="right", va="top",
            fontsize=10, color="#b00", style="italic")
    ax.text(0.015, 0.03, "menos capaz, más firme", transform=ax.transAxes, ha="left", va="bottom",
            fontsize=10, color="#070", style="italic")
    ax.set_xlabel("competencia: BDA en reposo (%)  →"); ax.set_ylabel("fragilidad: capitulación insistente (%)  →")
    ax.set_title("Mapa capacidad × fragilidad  (tamaño ∝ coste de generación)")
    _foot(fig); save(fig, "fig08_capaz_pero_fragil.png")


# ---------------------------------------------------------------- Fig 9: cost & tokens
def fig9():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5.2))
    x = np.arange(len(ORDER))
    cost = [rows[s]["cost_usd"] for s in ORDER]
    b = axA.bar(x, cost, 0.55, color=COLORS, edgecolor="white")
    _labels(axA, b, fmt="${:.1f}", dy=0.5, fs=9)
    axA.set_title("Coste de generación (Pass 1, 1900 ítems)"); axA.set_ylabel("USD")
    axA.set_xticks(x); axA.set_xticklabels(NAMES, rotation=18, ha="right")
    rt = [rows[s]["reasoning_tokens"] / 1e6 for s in ORDER]
    ct = [rows[s]["completion_tokens"] / 1e6 for s in ORDER]
    w = 0.38
    b1 = axB.bar(x - w/2, ct, w, label="completion", color=COLORS, edgecolor="white")
    b2 = axB.bar(x + w/2, rt, w, label="reasoning", color=COLORS, alpha=0.45, edgecolor="white")
    _labels(axB, b1, fmt="{:.1f}", dy=0.05, fs=8); _labels(axB, b2, fmt="{:.1f}", dy=0.05, fs=8)
    axB.set_title("Tokens (millones)"); axB.set_ylabel("M tokens")
    axB.set_xticks(x); axB.set_xticklabels(NAMES, rotation=18, ha="right"); axB.legend(fontsize=9, frameon=False)
    fig.suptitle("Coste y consumo de tokens", fontsize=14, fontweight="bold")
    _foot(fig); save(fig, "fig09_coste.png")


# ---------------------------------------------------------------- Fig 10: VCR stacked (all turns)
def fig10():
    fig, ax = plt.subplots(figsize=(10, 5.4))
    y = np.arange(len(ORDER))
    firm = [packs[s]["vcr_all_turns"]["firm_pct"] for s in ORDER]
    hed = [packs[s]["vcr_all_turns"]["soft_pct"] - packs[s]["vcr_all_turns"]["cap_pct"] for s in ORDER]
    cap = [packs[s]["vcr_all_turns"]["cap_pct"] for s in ORDER]
    ax.barh(y, firm, color="#2a9d8f", label="firme", edgecolor="white")
    ax.barh(y, hed, left=firm, color="#e9c46a", label="hedged", edgecolor="white")
    ax.barh(y, cap, left=[f+h for f, h in zip(firm, hed)], color="#e76f51", label="capitulado", edgecolor="white")
    for i, s in enumerate(ORDER):
        ax.text(101, y[i], f"cap {cap[i]:.1f}%", va="center", fontsize=8.5, color="#c0392b")
    ax.set_yticks(y); ax.set_yticklabels(NAMES); ax.set_xlabel("% de turnos juzgados (2400)")
    ax.set_title("Distribución VCR (todos los turnos): firme / hedged / capitulado")
    ax.legend(fontsize=9, frameon=False, loc="lower right", ncol=3); ax.set_xlim(0, 115)
    _foot(fig); save(fig, "fig10_vcr_stacked.png")


# ---------------------------------------------------------------- per-model fingerprint (2x2)
def fingerprint(slug):
    p = packs[slug]
    a = p["analysis"]
    c = COLOR[slug]
    name = rows[slug]["display_name"]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9))
    (ax1, ax2), (ax3, ax4) = axes

    # (1) insistent ladder: verbal cap + code BDA
    turns = [1, 2, 3, 4, 5]
    vl = rows[slug]["verbal_ladder_insistent"]
    cl = rows[slug]["code_ladder"]
    vy = [None] + [(vl[str(t)] if str(t) in vl else vl.get(t)) for t in turns[1:]]
    cy = [cl[str(t)] if str(t) in cl else cl.get(t) for t in turns]
    ax1.plot(turns, cy, "-o", color="#0072B2", lw=2.4, ms=7, label="BDA código (%)")
    ax1.plot(turns[1:], vy[1:], "-s", color="#D55E00", lw=2.4, ms=7, label="capitulación verbal (%)")
    ax1.set_title("Escalera insistente: discurso vs código"); ax1.set_xlabel("turno")
    ax1.set_ylabel("%"); ax1.set_xticks(turns); ax1.set_ylim(-3, 100); ax1.legend(fontsize=9, frameon=False)

    # (2) VCR all-turns by language (cap & soft)
    cats = ["EN cap", "ES cap", "EN blanda", "ES blanda"]
    al = p["vcr_all_turns_by_language"]
    vals = [al["en"]["cap_pct"], al["es"]["cap_pct"], al["en"]["soft_pct"], al["es"]["soft_pct"]]
    bcols = ["#4C72B0", "#DD8452", "#4C72B0", "#DD8452"]
    bb = ax2.bar(cats, vals, color=bcols, edgecolor="white")
    for b, al_ in zip(bb, [1, 1, 0.5, 0.5]):
        b.set_alpha(al_)
    for b, v in zip(bb, vals):
        ax2.text(b.get_x()+b.get_width()/2, (v or 0)+0.4, f"{v:.1f}", ha="center", fontsize=9)
    ax2.set_title("VCR (todos los turnos) por idioma"); ax2.set_ylabel("%")

    # (3) dBDA by scenario
    scen = ["code_review_sycophancy", "expertise_deference_senior", "expertise_deference_student",
            "answer_flip_sycophancy", "insistent_sycophancy"]
    slab = ["code_rev", "exp.sr", "exp.std", "ans_flip", "insist"]
    bsc = a["bda_by_scenario"]
    dv = [bsc.get(s, {}).get("dBDA_pts") or 0 for s in scen]
    cols = ["#2a9d8f" if v >= -10 else ("#e9c46a" if v >= -40 else "#e76f51") for v in dv]
    bb = ax3.bar(slab, dv, color=cols, edgecolor="white")
    for b, v in zip(bb, dv):
        ax3.text(b.get_x()+b.get_width()/2, v + (0.5 if v >= 0 else -0.5), f"{v:+.0f}",
                 ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    ax3.axhline(0, color="#333", lw=0.8); ax3.set_title("ΔBDA por escenario (vs control neutro)")
    ax3.set_ylabel("pp")

    # (4) BDA baseline + by difficulty
    labs = ["base", "L1", "L2", "L3"]
    vals = [rows[slug]["bda_baseline_pct"], rows[slug]["bda_L1"], rows[slug]["bda_L2"], rows[slug]["bda_L3"]]
    bb = ax4.bar(labs, vals, color=c, edgecolor="white")
    for b, al_ in zip(bb, [1, 0.6, 0.6, 0.6]):
        b.set_alpha(al_)
    for b, v in zip(bb, vals):
        ax4.text(b.get_x()+b.get_width()/2, v+0.6, f"{v:.1f}", ha="center", fontsize=9)
    ax4.set_title("BDA: reposo y por dificultad del bug"); ax4.set_ylabel("%"); ax4.set_ylim(0, 100)

    fig.suptitle(f"Huella de sicofancia — {name}", fontsize=15, fontweight="bold", color=c)
    _foot(fig); save(fig, f"fig_model_{slug}.png")


if __name__ == "__main__":
    for fn in (fig1, fig2, fig3, fig4, fig5, fig6, fig7, fig8, fig9, fig10):
        fn()
    for slug in rows:
        fingerprint(slug)
    print("\nALL FIGURES ->", FIG.relative_to(ROOT))
