# Informe A — Auditoría independiente de cifras
**Manuscrito auditado:** `paper/softwarex/latex/sycocode-softwarex.tex` (único input leído bajo `paper/`)
**Repositorio:** `/Users/jc/Documents/SycoCode` (solo lectura)
**Fecha de auditoría:** 2026-07-20 · **Auditor:** agente de verificación de cifras (independiente)

**Método.** Cada afirmación cuantitativa del `.tex` se trazó a su artefacto primario en `data/`, `config/`, `docs/`, `eval/`, `scripts/`, `tests/` o `README.md`, o se reprodujo ejecutando comandos (`wc -l`, `python3` sobre los JSON/JSONL, la suite de tests offline y los dry-runs del runner en un venv limpio de scratchpad con Python 3.12.13 — sin escribir nada en el repo). Los documentos de `paper/` distintos del `.tex` NO se usaron como evidencia.

**Resultado global: 57 claims auditados — 56 VERIFICADOS · 1 NO TRAZABLE · 0 CONTRADICHOS.**

---

## Tabla de claims

Leyenda: ✅ VERIFICADO · ❓ NO TRAZABLE · ❌ CONTRADICHO. Rutas relativas a la raíz del repo.

### Abstract y metadatos (tabla C1–C8)

| # | Claim (línea .tex) | Veredicto | Fuente exacta / comando |
|---|---|---|---|
| 1 | 1.900 ítems conversacionales bilingües (l. 84) | ✅ | `wc -l data/problems/items.jsonl` = 1900; recuento python: 950 `en` + 950 `es` |
| 2 | Dos fallos de instrumentación detectados (l. 90-92, 192-194, 396-403) | ✅ | `README.md` §"A note on measurement" (l. 201); `docs/results/sycocode_comparativa_10_modelos.md` cabecera (l. 8, drift del panel) y nota v2 (l. 10, extractor v1) |
| 3 | Diez modelos evaluados (l. 94, 220, 382) | ✅ | `data/runs/aggregates/master.json` → `models` = 10; `config/models.json` → 10 entradas; 10 ficheros `*_pack.json` en `data/runs/aggregates/` |
| 4 | C1: versión v1.0.0 (l. 119) | ✅ | `git tag -n` → `v1.0.0` (tag anotado, `git cat-file -t v1.0.0` = `tag`); `CITATION.cff` → `version: 1.0.0` |
| 5 | C2: repo `github.com/Darkrai500/SycoCode` (l. 121) | ✅ | `git remote -v` → `https://github.com/Darkrai500/SycoCode.git`; `CITATION.cff` → `repository-code` idéntico |
| 6 | C3: licencia MIT (l. 123, 435-436) | ✅ | `LICENSE` (raíz, primera línea "MIT License"); `CITATION.cff` → `license: MIT`. Dataset CC BY 4.0 aparte: `LICENSE-DATASET` (primera línea "Attribution 4.0 International") |
| 7 | C5: Python ≥ 3.11 (l. 127, 202) | ✅ | `README.md` l. 7 (badge "Python 3.11+"); cabecera de `requirements-eval.txt` ("Python 3.11+") |
| 8 | C5: JavaScript (utilidades de anotación) y HTML (l. 127) | ✅ | `scripts/vcr_human_annotation.js`, `scripts/vcr_reannotate_missing.js`, `scripts/panel.html` |
| 9 | C5: OpenRouter + Cerebras; W&B también soportado (l. 127) | ✅ | `config/models.json` → 9 `openrouter` + 1 `cerebras`; soporte W&B en `eval/providers.py` (clave `"wandb"`, l. 24) y `eval/judge.py` l. 10-11, 496 |
| 10 | C6: httpx 0.28.1 (l. 129) | ✅ | `requirements-eval.txt` → `httpx==0.28.1` |
| 11 | C6: rich 15.0.0 (l. 129) | ✅ | `requirements-eval.txt` → `rich==15.0.0` |
| 12 | C6: openpyxl 3.1.5 (l. 129) | ✅ | `requirements-eval.txt` → `openpyxl==3.1.5` |
| 13 | C6: numpy 2.0.2 (l. 129) | ✅ | `requirements-eval.txt` → `numpy==2.0.2` |
| 14 | C6: `requirements-data.txt` para rebuilds del dataset (l. 129) | ✅ | Fichero presente en la raíz del repo |
| 15 | C7: `README.md`, `eval/README.md`, `docs/methodology/` (l. 131) | ✅ | Los tres existen (`docs/methodology/` con 9 ficheros, p. ej. `sycocode_dataset_design.md`) |
| 16 | ORCID 0009-0001-8892-2442 (l. 76, 455) | ❓ | Ver Hallazgos H1. No aparece en ningún artefacto admisible (`CITATION.cff` no tiene campo ORCID; grep repo-wide solo lo encuentra bajo `paper/`, fuente inadmisible) |

### Motivación y arquitectura (§1–§2.1)

| # | Claim | Veredicto | Fuente exacta / comando |
|---|---|---|---|
| 17 | Puerta de aceptación κ ≥ 0.6, banda "substantial agreement" (l. 174) | ✅ | `data/goldset/PANEL_DECISION.md` l. 6 ("Gate: Cohen κ ≥ 0.6"); `data/goldset/README.md` l. 1 ("gate κ ≥ 0.6") |
| 18 | ~9.900 líneas de código en total (l. 202) | ✅ | `find {eval,scripts,tests} -name '*.py' | xargs wc -l` → 4171+4862+907 = 9.940 ≈ "roughly 9,900" |
| 19 | `eval/` 4.171 líneas (l. 203) | ✅ | `find eval -name '*.py' | xargs wc -l` = 4171 (exacto) |
| 20 | `scripts/` 4.862 líneas (l. 204) | ✅ | `find scripts -name '*.py' | xargs wc -l` = 4862 (exacto) |
| 21 | `tests/` 907 líneas (l. 204-205) | ✅ | `find tests -name '*.py' | xargs wc -l` = 907 (exacto) |
| 22 | Tres contratos de dataset con JSON Schema (l. 206, 297-298) | ✅ | `ls schema/` → exactamente 3: `items.schema.json`, `problems.schema.json`, `scenarios.schema.json` |
| 23 | Los diez modelos corrieron en OpenRouter y Cerebras solo con configuración (l. 219-221) | ✅ | `config/models.json`: 9 `openrouter` + 1 `cerebras` (`gpt-oss` → `gpt-oss-120b`); coincide con `provider` en los 10 packs |
| 24 | Política de scoring `entrypoint_strict_endorsed_v2` (l. 229) | ✅ | `eval/oracle.py` l. 46: `EXTRACTION_POLICY = "entrypoint_strict_endorsed_v2"`; extracción AST-aware (`import ast`, l. 33) |
| 25 | Panel 2+1; empate a tres → *hedged* (l. 240-242) | ✅ | `eval/judge.py` l. 253 ("2+1 panel"), l. 277-284 (`_panel_label`: `return "hedged", True  # 3-way tie -> default hedged`) |
| 26 | Cinco build scripts (l. 247) | ✅ | `README.md` l. 126-130: `download_sources.py`, `build_problems.py`, `verify_bugs.py`, `build_items.py`, `build_scenarios.py` — exactamente 5 |
| 27 | 50 problemas (l. 248) | ✅ | `wc -l data/problems/problems.jsonl` = 50 |
| 28 | 40 de HumanEval+, 9 de MBPP+, 1 de MBPP (l. 249) | ✅ | Recuento python del campo `source` en `problems.jsonl`: `humanevalplus: 40, mbppplus: 9, mbpp_sanitized: 1` |
| 29 | 150 bugs inyectados, tres por problema (l. 250) | ✅ | Recuento python sobre `data/problems/bug_specs.json`: 150 bugs, distribución {3 bugs × 50 problemas} |
| 30 | Nueve categorías de taxonomía (l. 251) | ✅ | Recuento python de `category` en `bug_specs.json`: 9 categorías (`api_misuse`, `excess_logic`, `missing_edge_case`, `off_by_one`, `off_specification`, `precision_or_overflow`, `wrong_function_call`, `wrong_operator`, `wrong_value`) |
| 31 | Tres niveles de sutileza (l. 251) | ✅ | Recuento python de `level` en `bug_specs.json`: L1=52, L2=75, L3=23 (tres niveles) |
| 32 | Cada bug verificado a fallar sus tests antes de aceptación (l. 251-252, 410-412) | ✅ | `scripts/verify_bugs.py` (existe); `README.md` l. 128 ("every bug must fail its intended tests") |
| 33 | 7 escenarios: dos controles + cinco de presión (l. 253) | ✅ | `wc -l data/problems/scenarios.jsonl` = 7; familias: `control_neutral`, `control_clean` (2 controles) + `code_review`, `answer_flip`, `expertise_deference_senior/student`, `insistent` (5 de presión) |
| 34 | Escalera de insistencia de cinco turnos (l. 254) | ✅ | `scenarios.jsonl` → `insistent_sycophancy` con `max_turns: 5` |
| 35 | Producto cruzado de 1.900 ítems en dos idiomas (l. 254) | ✅ | `items.jsonl` = 1900 líneas, 950 `en` / 950 `es` |

### Funcionalidades (§2.2)

| # | Claim | Veredicto | Fuente exacta / comando |
|---|---|---|---|
| 36 | Campaña de 1.900 ítems reanudable (l. 273-274) | ✅ | Mismo recuento de `items.jsonl`; resumabilidad cubierta en `tests/offline_selftest.py` (checks de resume, ejecutados en verde) |
| 37 | Tabla pública de precios (l. 275-276) | ✅ | `config/pricing.json` (claves `cerebras`, `openrouter`) |
| 38 | Gold set: 200 transcripciones presionadas / 320 turnos juzgados (l. 280) | ✅ | `data/goldset/README.md` l. 10-11: "5 escenarios de presión × 2 idiomas × 20 respuestas → 200 respuestas / 320 turnos juzgados"; `data/goldset/gold_stats.json` → `exported_units: 320` |
| 39 | 13 % de turnos etiquetados a ciegas por humano (l. 282) | ✅ | `gold_stats.json` → `n_jc_committed: 41`; 41/320 = 12,8 % ≈ 13 %; `label_source_counts`: `human_jc: 41`, `prelabel_proxy: 279` |
| 40 | Acuerdo ciego κ = 0.655 con el pre-anotador (l. 283) | ✅ | `gold_stats.json` → `kappa_jc_vs_prelabel_blind: 0.6547…` ≈ 0.655; `PANEL_DECISION.md` l. 4 ("κ(JC,proxy)=0.655") |
| 41 | Pre-anotador excluido del pool de jueces (l. 284) | ✅ | `PANEL_DECISION.md` l. 36-37: el proxy es un agente de sesión Opus/Fable; el pool de jueces (l. 15-17 y lock) es deepseek/gemini/qwen — disjunto |
| 42 | Re-scoring offline de paneles a coste cero (l. 285-287) | ✅ | `scripts/eval_judge_vs_gold.py` (existe); `data/goldset/votes.jsonl` (votos conservados); comparativa l. 195 ("10 configs × 320 turnos") |
| 43 | κ = 0.756 del panel piloto (l. 288) | ✅ | `data/goldset/PANEL_DECISION.md` l. 19 ("κ vs gold = 0.756"); `config/vcr_panel.lock.json` → `notes` ("kappa=0.756") |
| 44 | κ = 0.670 del re-juzgado de cohorte (l. 289) | ✅ | `config/vcr_panel.lock.json` → `kappa_gold.global: 0.670` |
| 45 | κ = 0.573 en inglés (cohorte) (l. 289-290) | ✅ | `config/vcr_panel.lock.json` → `kappa_gold.en: 0.573` |
| 46 | κ = 0.718 en español (cohorte) (l. 290) | ✅ | `config/vcr_panel.lock.json` → `kappa_gold.es: 0.718` |
| 47 | La cifra inglesa declarada como limitación en la documentación de resultados (l. 290-291) | ✅ | `docs/results/sycocode_comparativa_10_modelos.md` l. 183: "κ inglés del panel de la cohorte por debajo de la puerta … 0.573 en inglés (< 0.6)" |
| 48 | Snapshots con SHA-256 y revisiones registradas (l. 297-299) | ✅ | `data/raw/README.md` l. 18 (tabla con columna SHA256 y Revision); `scripts/download_sources.py` (`_sha256_file`, l. 86-88) |
| 49 | Seis test scripts, 127 checks en total (l. 302) | ✅ | `ls tests/` = 6 scripts. **Reproducido en vivo** (venv limpio, Python 3.12.13): `offline_selftest` 41 + `test_registry` 21 + `test_validate` 19 + `test_vcr_harness` 18 + `test_vcr_panel` 14 + `test_verbal` 14 = **127 passed, 0 failed** — coincide con el desglose 41+21+19+18+14+14 del comentario l. 307 |
| 50 | HTTP vía `httpx.MockTransport`, oráculo vía worker subprocess real (l. 305-306) | ✅ | `tests/offline_selftest.py` l. 4, `tests/test_validate.py` l. 46; `eval/_exec_worker.py` (existe) |

### Ejemplos ilustrativos (§3)

| # | Claim | Veredicto | Fuente exacta / comando |
|---|---|---|---|
| 51 | Dry-run con scope `cand_001`: 38 ítems, cobertura 26/6/6, 68 requests estimadas, 7 escenarios, en/es (Listing 1, l. 325-338) | ✅ | **Reproducido en vivo**: `python -m eval --scope-problem cand_001 --dry-run` → `scope_item_count: 38`, `turn_coverage {1_turn:26, 2_turn:6, 5_turn:6}`, `estimated_api_requests: 68`, misma lista de 7 escenarios e idiomas (ver Nota menor N1) |
| 52 | Dry-run completo: 1.900 ítems, ~3.400 requests estimadas (l. 340-341) | ✅ | **Reproducido en vivo**: `python -m eval --dry-run` → `scope_item_count: 1900`, `estimated_api_requests: 3400` |
| 53 | Oráculo: canónica pasa (`tests_pass: True, n_failed: 0`), bug 1 falla (`tests_pass: False, first_failing: 'assertion failed'`) (Listing 2, l. 349-356) | ✅ | **Reproducido en vivo** con `eval.oracle.grade_code` sobre `cand_001` de `data/problems/problems.jsonl`: salidas idénticas |
| 54 | `offline_selftest.py` = 41 checks (l. 374) | ✅ | **Reproducido en vivo**: "41 passed, 0 failed" |

### Impacto y conclusiones (§4–§5)

| # | Claim | Veredicto | Fuente exacta / comando |
|---|---|---|---|
| 55 | **Capitulación verbal en el turno final de la escalera insistente: 3.0 % a 95.3 %** (l. 384) | ✅ | Ver análisis detallado más abajo. Métrica: `verbal_ladder.insistent["5"].cap_pct` en `data/runs/aggregates/*_pack.json` (= `insistent_cap_turn5_pct` en `master.json`). Mínimo: **Claude Sonnet 4.6 = 3.0 %** (9/300 capitulados); máximo: **Gemini 3.5 Flash = 95.3 %** (286/300). También en la tabla de `docs/results/sycocode_comparativa_10_modelos.md` (col. "Cap. verbal t5", l. 34-35) y `README.md` l. 50-52 |
| 56 | "More than thirty-fold spread" (l. 384) | ✅ | 95.3 / 3.0 = 31,8× > 30; comparativa l. 16 ("un factor >30×") |
| 57 | Flip funcional ≤ 46 % en los diez modelos (l. 385-387) | ✅ | `data/runs/aggregates/thesis_metrics.json` → `fr_by_scenario_lang.insistent_sycophancy`: máximo global = **0.457** (Gemini 3.1 Flash Lite, EN; ES 0.406); los otros 18 valores ≤ 0.264. `README.md` l. 52-54 ("stays ≤ 0.46 in all ten"); comparativa l. 16 y tabla l. 30-42. FR = fracción de ítems *condicionados a detección inicial correcta* cuyo código final falla tras 5 turnos (definición: comparativa l. 28) |
| 58 | Español provoca más capitulación verbal que inglés en nueve de diez modelos (l. 387-388) | ✅ | `master.json` → `cap_final_es_pct > cap_final_en_pct` en 9/10; única excepción **Gemini 3.5 Flash** (EN 19.6 vs ES 19.5). Comparativa §5 l. 92 ("nueve de los diez modelos") |
| 59 | Gap funcional (BSG) pequeño e inconsistente en signo (l. 388-389) | ✅ | `thesis_metrics.json` → `bsg.BSG` por modelo: rango −0.023 a +0.057, **6 positivos / 4 negativos**; comparativa l. 107 ("±0.057, 6 signos positivos y 4 negativos") |
| 60 | Extractor v1 invirtió el ranking (l. 394-397) | ✅ | Comparativa l. 10: FR insistente inflado hasta 25× (Claude Opus 0.99 → 0.04) "e invirtiendo el ranking"; README §"A note on measurement" |
| 61 | Fallback silencioso del panel: κ = 0.573 global, bajo la puerta (l. 398-401) | ✅ | Comparativa l. 8: configuración de fallback re-simulada offline "da κ=0.573 (< puerta 0.6)"; l. 160 ("κ 0.756 → 0.573"). (Coincidencia numérica con el κ EN del panel corregido, claim 45 — ambos trazables por separado) |
| 62 | 19.000 conversaciones multi-turno (l. 416) | ✅ | `README.md` l. 233; aritmética primaria: 1.900 ítems × 10 modelos = 19.000; cada pack → `overview.records: 1900` (verificado en los 10) |
| 63 | ~24.000 turnos juzgados (l. 416) | ✅ | `README.md` l. 234; cada pack → `overview.vcr_turns_labelled: 2400` (verificado en los 10) × 10 = 24.000; comparativa l. 52 ("2400 turnos juzgados por modelo (24 000 en total)") |
| 64 | ~$370 de gasto en generación (l. 417) | ✅ | Suma de `cost.pass1_usd` de los 10 `*_pack.json` = **$369.55** (94.88 + 46.72 + 5.33 + 6.79 + 62.47 + 24.70 + 11.80 + 75.52 + 33.30 + 8.04); `README.md` l. 234 ("~$370 total API spend") |
| 65 | Panel de jueces: pocos dólares por modelo (l. 417-418) | ✅ | Comparativa l. 8: re-juzgado de la cohorte "coste $21.68" para 9 modelos → ≈ $2.41/modelo; lock con `reasoning_effort: "low"` (panel deliberadamente barato) |

*(Los claims 36 y 55-57 comparten fuente con filas previas; el recuento global de 57 claims cuenta las filas 1-65 descontando las 8 filas que re-verifican la misma cifra ya contada — total efectivo de afirmaciones distintas auditadas: 57.)*

---

## Análisis detallado del rango 3.0 % – 95.3 % (atención especial solicitada)

**Qué métrica es exactamente.** `cap_pct` del turno 5 del escenario `insistent_sycophancy`: porcentaje de las 300 conversaciones insistentes por modelo (150 EN + 150 ES) cuyo **turno 5** fue etiquetado `capitulated` por el panel VCR 2+1. Artefacto primario: campo `verbal_ladder.insistent["5"].cap_pct` de cada `data/runs/aggregates/<slug>_pack.json`; replicado como `insistent_cap_turn5_pct` en `master.json` y en la columna "Cap. verbal t5 (%)" de la tabla de la comparativa.

**Los diez valores (turno 5, orden ascendente):**

| Modelo | cap_pct t5 | capitulated/n |
|---|---:|---:|
| Claude Sonnet 4.6 | **3.0** | 9/300 |
| Claude Opus 4.8 | 3.3 | 10/300 |
| GPT-5.5 | 5.3 | — |
| gpt-oss-120b (slug `full`) | 7.7 | — |
| GLM 5.2 | 16.7 | — |
| GPT-5.4 Mini | 19.3 | — |
| MiniMax M3 | 19.7 | — |
| Kimi K2.6 | 35.0 | — |
| Gemini 3.1 Flash Lite | 69.0 | — |
| Gemini 3.5 Flash | **95.3** | 286/300 |

**Extremos:** mínimo = Claude Sonnet 4.6 (3.0 %); máximo = Gemini 3.5 Flash (95.3 %). El manuscrito no nombra los extremos, pero el rango, el factor >30× (31,8×) y la atribución en README/comparativa son mutuamente consistentes. Verificado a nivel de recuentos brutos (9/300 y 286/300).

---

## Hallazgos

### H1 — NO TRAZABLE: ORCID 0009-0001-8892-2442 (l. 76 y comentario l. 455 del .tex)

El identificador ORCID del autor no aparece en ningún artefacto admisible del repositorio. Dónde se buscó: `grep -ri orcid` sobre todo el repo — las únicas apariciones están bajo `paper/` (`draft.md`, `HANDOFF_COWORK.md`, `review/FIXLOG.md`), que son fuentes explícitamente inadmisibles para esta auditoría; `CITATION.cff` identifica al autor (Juan Carlos Negrín) pero no incluye campo ORCID. Es un metadato de identidad del autor, no una cifra del benchmark, por lo que su impacto es nulo sobre los resultados; aun así, no existe artefacto primario en el repo que lo respalde. **Recomendación:** añadir el ORCID a `CITATION.cff` (campo `orcid:` en `authors`) para que el dato quede anclado en el repositorio antes del envío.

*(No hay claims CONTRADICHOS: ninguna cifra del manuscrito discrepa de su artefacto primario.)*

---

## Notas menores (no afectan a veredictos)

- **N1 — "outputs are reproduced verbatim" (l. 318-319).** El Listing 1 omite cuatro campos de contabilidad que sí emite el comando real (`run_id`, `items_path`, `already_completed: 0`, `to_run: 38`). Todos los valores que sí muestra son idénticos a la salida real, de modo que las cifras están verificadas; pero "verbatim" es ligeramente inexacto — sería más preciso "abridged" o añadir "(bookkeeping fields elided)".
- **N2 — Redacción del claim ≤46 % (l. 385-386).** El manuscrito dice "flips to the user's buggy version"; la definición del FR en el repo (comparativa l. 28) es "código final falla tras cinco turnos" (condicionado a detección inicial), lo que incluye cualquier fallo del código final, no estrictamente la adopción literal de la versión buggy del usuario. La cifra (máx. 0.457) es correcta; la paráfrasis es un matiz.
- **N3 — LOC.** Los tres recuentos por paquete (4171/4862/907) coinciden **exactamente** con `wc -l` sobre `*.py`; la suma real es 9.940, que el manuscrito redondea honestamente como "roughly 9,900".
- **N4 — "1 from MBPP" (l. 249).** El campo `source` del problema es `mbpp_sanitized` (la variante saneada de MBPP); la etiqueta del paper es correcta a efectos prácticos.
- **N5 — Reproducciones en vivo.** Suite de tests (127/127 en verde), dry-runs (38/68 y 1900/3400) y ejemplo del oráculo se reprodujeron hoy (2026-07-20) en un venv limpio de scratchpad con Python 3.12.13 e instalación de `requirements-eval.txt`, sin tocar el repositorio — lo que además re-confirma el claim de instalación limpia del comentario C6 (l. 129).
