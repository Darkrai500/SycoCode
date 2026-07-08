"""Thesis figures (EN + ES) for the multi-model experimental chapter.

Reads data/runs/aggregates/{thesis_metrics.json, master.json} and renders two
language-localised (EN/ES) figures for the report:
  - thesis_quadrant : capability (BDA) x fragility (SS), bubble area ~ cost
  - thesis_ss_heatmap : Susceptibility Score by model x bug category

Outputs to docs/figures/report_en/ and docs/figures/report_es/.
Run: .venv/bin/python scripts/tfg_thesis_figures.py
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TFG = ROOT / "data" / "runs" / "aggregates"
TM = json.loads((TFG / "thesis_metrics.json").read_text(encoding="utf-8"))
MASTER = json.loads((TFG / "master.json").read_text(encoding="utf-8"))["rows"]

COLOR = {"full": "#0072B2", "glm-5-2": "#009E73", "gemini-3-1-flash-lite": "#CC79A7",
         "gemini-3-5-flash": "#D55E00", "kimi-k-2-6": "#E69F00",
         "claude-opus-4-8": "#762A83", "claude-sonnet-4-6": "#9970AB", "gpt-5-5": "#56B4E9",
         "gpt-5-4-mini": "#44AA99", "minimax-m3": "#882255"}
# order by SS ascending (robustness)
ORDER = sorted(TM, key=lambda s: TM[s]["ss"]["overall"])

STR = {
    "en": {
        "qx": "Capability — Bug Detection Accuracy (%)",
        "qy": "Fragility — Susceptibility Score (SS)",
        "qt": "Capability × fragility across the ten models",
        "qnote": "bubble area ∝ generation cost",
        "fragile": "capable but fragile",
        "robust": "less capable, firmer",
        "hx": "bug category", "hy": "model",
        "ht": "Susceptibility Score by model and bug category",
        "cb": "SS (difficulty-weighted flip rate)",
    },
    "es": {
        "qx": "Competencia — Bug Detection Accuracy (%)",
        "qy": "Fragilidad — Susceptibility Score (SS)",
        "qt": "Capacidad × fragilidad en los diez modelos",
        "qnote": "área de burbuja ∝ coste de generación",
        "fragile": "capaz pero frágil",
        "robust": "menos capaz, más firme",
        "hx": "categoría de bug", "hy": "modelo",
        "ht": "Susceptibility Score por modelo y categoría de bug",
        "cb": "SS (flip ponderado por dificultad)",
    },
}

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 200, "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "font.family": "DejaVu Sans",
})


def outdirs():
    en = ROOT / "docs" / "figures" / "report_en"
    es = ROOT / "docs" / "figures" / "report_es"
    en.mkdir(parents=True, exist_ok=True)
    es.mkdir(parents=True, exist_ok=True)
    return {"en": en, "es": es}


def quadrant(lang, outdir):
    s = STR[lang]
    fig, ax = plt.subplots(figsize=(8.4, 6.0))
    xs = [TM[m]["bda"]["overall"] * 100 for m in ORDER]
    ys = [TM[m]["ss"]["overall"] for m in ORDER]
    cost = [MASTER[m]["cost_usd"] for m in ORDER]
    sizes = [120 + (c ** 0.9) * 20 for c in cost]
    # per-model label offsets (dx, dy, ha) to de-collide the GLM/Gemini cluster
    OFF = {"full": (-10, 10, "right"), "kimi-k-2-6": (10, 8, "left"),
           "gemini-3-5-flash": (14, 9, "left"), "glm-5-2": (-12, -22, "right"),
           "gemini-3-1-flash-lite": (14, -16, "left"), "gpt-5-5": (-10, 8, "right"),
           "claude-opus-4-8": (12, 6, "left"), "claude-sonnet-4-6": (12, -4, "left")}
    for m, x, y, sz in zip(ORDER, xs, ys, sizes):
        ax.scatter(x, y, s=sz, color=COLOR[m], alpha=0.85, edgecolor="black", lw=0.8, zorder=3)
        dx, dy, ha = OFF.get(m, (9, 7, "left"))
        ax.annotate(f"{TM[m]['display_name']} (\\${MASTER[m]['cost_usd']:.0f})".replace("\\$", "$"),
                    (x, y), textcoords="offset points", xytext=(dx, dy), ha=ha,
                    fontsize=9, fontweight="bold")
    ax.margins(x=0.18)
    ax.axvline(float(np.mean(xs)), color="#bbb", ls="--", lw=1)
    ax.axhline(float(np.mean(ys)), color="#bbb", ls="--", lw=1)
    ax.text(0.985, 0.97, s["fragile"], transform=ax.transAxes, ha="right", va="top",
            fontsize=10, color="#b00", style="italic")
    ax.text(0.015, 0.03, s["robust"], transform=ax.transAxes, ha="left", va="bottom",
            fontsize=10, color="#070", style="italic")
    ax.set_xlabel(s["qx"]); ax.set_ylabel(s["qy"])
    ax.set_title(f"{s['qt']}\n", fontsize=13)
    ax.text(0.5, 1.005, s["qnote"], transform=ax.transAxes, ha="center", va="bottom",
            fontsize=9, color="#666", style="italic")
    fig.tight_layout()
    p = outdir / "thesis_quadrant.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(fig)
    print("wrote", p.relative_to(ROOT))


def heatmap(lang, outdir):
    s = STR[lang]
    cats = sorted({c for m in TM for c in TM[m]["ss_by_category"]})
    M = np.array([[TM[m]["ss_by_category"].get(c, {}).get("SS") or np.nan for c in cats] for m in ORDER])
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    im = ax.imshow(M, cmap="YlOrRd", vmin=0, vmax=0.5, aspect="auto")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([c.replace("_", "\n") for c in cats], fontsize=8.5)
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([TM[m]["display_name"] for m in ORDER])
    for i in range(len(ORDER)):
        for j in range(len(cats)):
            v = M[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        color="black" if v < 0.33 else "white", fontsize=8.5)
    ax.set_xlabel(s["hx"]); ax.set_ylabel(s["hy"]); ax.set_title(s["ht"])
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02); cb.set_label(s["cb"], fontsize=9)
    fig.tight_layout()
    p = outdir / "thesis_ss_heatmap.png"
    fig.savefig(p, bbox_inches="tight", facecolor="white"); plt.close(fig)
    print("wrote", p.relative_to(ROOT))


if __name__ == "__main__":
    od = outdirs()
    for lang in ("en", "es"):
        quadrant(lang, od[lang])
        heatmap(lang, od[lang])
    print("done")
