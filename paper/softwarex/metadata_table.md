# Code Metadata Table — SycoCode (SoftwareX Original Software Publication)

> **NO AUTORITATIVO.** La tabla que se envía es la del manuscrito
> (`latex/sycocode-softwarex.tex`, `\label{tab:codemetadata}`). Este fichero es
> su espejo comentado: sirve para dejar por escrito de dónde sale cada valor y
> cómo se comprobó. Si los dos divergen, manda el `.tex`.
>
> Reescrito el 2026-07-31 para alinearlo con el esquema **C1–C8 de la plantilla
> oficial** (`latex/softwarex-osp-template.tex`). La versión anterior usaba un
> esquema propio de nueve filas (con "Reproducible Capsule" y las licencias en
> C4) que **no** coincidía con la plantilla ni con el manuscrito.

Datos del repo en la rama `softwarex-prep` (base v1.0, commit `4050b9b`; fixes
de publicación en `f367fb4`; tag anotado local `v1.0.0`).

| Nr | Code metadata description | Value | Cómo se comprobó |
|----|---------------------------|-------|------------------|
| C1 | Current code version | v1.0.0 | Tag anotado **publicado** el 2026-07-31 en `5d8ee0f`. Se recortó: antes apuntaba a `f367fb4`, que todavía tenía el fichero de licencia como `LICENSE` sin extensión y por tanto no cumplía la guía. Nunca se había empujado, así que moverlo no reescribe nada público. |
| C2 | Permanent GitHub link to code/repository used for this code version | https://github.com/Darkrai500/SycoCode/tree/v1.0.0 | Repo **PÚBLICO** desde el 2026-07-31. Verificado sin token: `README.md` y `LICENSE.txt` devuelven 200 sobre el tag en `raw.githubusercontent.com`, y los documentos internos devuelven 404. Se enlaza el tag y no la raíz porque la fila pide el enlace "used for this code version": `/tree/v1.0.0` es inmutable, la raíz sigue a `main`. |
| C3 | Legal Code License | MIT | **`LICENSE.txt`** en la raíz (renombrado el 2026-07-31 desde `LICENSE`, que es lo que exige la guía). Dataset aparte en CC BY 4.0 (`LICENSE-DATASET`); upstream conserva su licencia (`LICENSE-APACHE`, `THIRD_PARTY_NOTICES.md`). Los cuatro ficheros existen y GitHub sigue detectando MIT. |
| C4 | Code versioning system used | git | — |
| C5 | Software code languages, tools, and services used | Python (≥3.11), JavaScript (annotation utilities), HTML; JSON Schema; APIs HTTP compatibles con OpenAI (OpenRouter, Cerebras; W&B Inference también soportado) | `wc -l` el 2026-07-31: `eval/` 4.171, `scripts/` 4.862, `tests/` 907 = 9.940 líneas Python, idéntico a lo declarado en §2.1. Servicios: `config/models.json` (9 × OpenRouter + 1 × Cerebras); W&B soportado en `eval/client.py`. |
| C6 | Compilation requirements, operating environments & dependencies | Sin compilación (Python puro). Probado en macOS (Apple Silicon) y Linux (x86-64); Python ≥3.11, verificado en 3.12.13. Pins en `requirements-eval.txt` / `requirements-data.txt`. Tests y dry-run 100% offline; los runs reales necesitan API keys vía `.env` | **macOS — evidencia fresca del 2026-07-31**: venv nuevo + `pip install -r requirements-eval.txt` (httpx 0.28.1, rich 15.0.0, openpyxl 3.1.5, numpy 2.0.2 instalados) y los 6 scripts de test en verde, exit 0, **127 checks** (41+21+19+18+14+14), en macOS 26.5.2 arm64 / Python 3.12.13. `python -m eval --dry-run` devuelve 1.900 ítems / 3.400 peticiones, que es lo que dice §3. **Linux — evidencia documental**: la campaña de 10 modelos corrió en un VPS Linux aprovisionado con Docker (`README.md` §Engineering notes, línea 235). **Windows: sin evidencia en el repo → no se declara.** |
| C7 | If available Link to developer documentation/manual | `README.md`, `eval/README.md`, `docs/methodology/` | Los tres existen (verificado 2026-07-31). `DATASHEET.md` documenta el dataset y lo cita §Data availability. |
| C8 | Support email for questions | jcnegrin2003@gmail.com | Confirmado por el autor 2026-07-19; Gmail y no el institucional a propósito (decisión F11: durabilidad tras la graduación). |

## Fila omitida deliberadamente

La plantilla trae además una sección "Current executable software version"
(tabla S1–S8). Se omite: SycoCode se distribuye solo como código fuente, no
hay artefacto ejecutable separado, y la tabla C1–C8 ya cubre la release. La
omisión está comentada en el `.tex`, al final, antes de `\end{document}`.

## Verificación de la Tabla 2 del manuscrito (los diez modelos)

Re-verificada el 2026-07-31 contra `data/runs/aggregates/master.json`:
**60/60 celdas coinciden** (campos `bda_all_families_pct`,
`bda_insistent_pct`, `cap_all_turns_pct`, `insistent_cap_turn5_pct`,
`fpr_control_clean_pct`, `cost_usd` × 10 modelos) y `cost_usd` suma
**$369.55**, que es el "$370" de §4.
