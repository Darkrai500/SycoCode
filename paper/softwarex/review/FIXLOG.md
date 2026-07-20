# FIXLOG — corrección F1–F14 (2026-07-20)

Encargo: lista cerrada de 14 fixes procedente de la revisión externa del PDF
contra la memoria del TFG. Regla aplicada: **cada fix se verificó contra la
fuente (memoria y artefactos del repo) antes de tocarse; la fuente manda
sobre la lista**. Cirugía estricta: ningún retoque de estilo fuera de F14.

Ficheros tocados: `latex/sycocode-softwarex.tex`, `draft.md` (espejo 1:1),
`latex/refs.bib` (F12), `metadata_table.md` (F10). Nada fuera de
`paper/softwarex/**`.

Recompilación tras la tanda: `latexmk -pdf` → **0 errores, 0 citas sin
resolver, 0 "??"**, 9 páginas. Cuerpo (abstract + §1–§5, sin listados ni
comentarios): **1.945 palabras** (< 3.000). Cifras clave verificadas en el
PDF nuevo: 1,900 (×4), 10 modelos, κ=0.756, κ=0.670, 3.0%–95.3%, 50
problems, 150 injected, 127 checks.

| Fix | Verificación de fuente | Cambio aplicado |
|---|---|---|
| **F1** | `data/problems/problems.jsonl`: 9 categorías distintas (api_misuse, excess_logic, missing_edge_case, off_by_one, off_specification, precision_or_overflow, wrong_function_call, wrong_operator, wrong_value). Memoria: "nine-category taxonomy" en 02-extended-abstract, 04-introduction:125, 08-conclusions:43/143, 09-appendices:213. | §2.1: "five taxonomy categories" → "**nine** taxonomy categories". |
| **F2** | `data/goldset/gold_stats.json`: 320 unidades, 41 `human_jc` (41/320 = 12,8% ≈ 13%), 279 `prelabel_proxy`, `kappa_jc_vs_prelabel_blind` = 0.6547 ≈ 0.655. `PANEL_DECISION.md:37`: "Gold is a **silver standard**". Memoria 07-experimental:105–110 y 06-work-description:868–879: mismo relato, "The set is therefore a *silver* standard". Pre-anotador = agente de sesión Opus/Fable (PANEL_DECISION) ∉ jueces del lock (deepseek-v4-flash, gemini-3.1-flash-lite, qwen3.6-35b) → exclusión verificada. | §2.2: "was annotated by a human under a blind label-then-reveal protocol (machine pre-labels…)" → "is human-anchored, built under a blind label-then-reveal protocol (13% of turns labelled blind by a human; the remainder adopt a frozen pre-annotator's labels, licensed by blind agreement κ = 0.655, with the pre-annotator excluded from the judge pool)". Se conservan 200/320. Comentario de procedencia actualizado (gold_stats.json). |
| **F3** | Packs `data/runs/aggregates/*_pack.json`: el campo es `cost.pass1_usd` (Pass 1 = generación); suma de los 10 = **$369,55** ≈ $370. Juez: re-juzgado de la cohorte **$21,68 / 9 modelos** ≈ $2,4/modelo (cabecera de `docs/results/sycocode_comparativa_10_modelos.md`). | §4: "roughly $370 in API spend" → "roughly $370 in **generation** spend, with the deliberately low-cost judge panel adding a few dollars per model". Comentario de procedencia actualizado con el desglose. |
| **F4** | Comparativa §cabecera: la configuración fallback re-simulada offline da κ=0.573 (< 0.6). `config/vcr_panel.lock.json`: κ EN del panel corregido = 0.573. **Coincidencia numérica real; ambos valores correctos**, cada uno queda escopado a su configuración. | §4: "(κ = 0.573, below the acceptance gate)" → "(κ = 0.573 **overall for the fallback configuration**, below the gate)". El κ EN de §2.2 ya estaba escopado ("0.573 in English"). |
| **F5** | §4 del propio paper + comparativa (cabecera y lección 4): fallo 1 (extractor) lo cazó la discrepancia entre capas; fallo 2 (drift del panel) lo cazó la **re-validación offline**, no la redundancia. §4 no se toca (ya lo cuenta bien). | Abstract: "their redundancy doubles as an instrumentation check; it caught two measurement faults" → "the platform doubles as an instrumentation check: **its two-layer redundancy and its offline re-validation** caught two measurement faults". §1: "when the redundancy between the verbal and functional layers exposed" → "when **its two-layer redundancy and its offline re-validation** exposed". |
| **F6** | Memoria 05-theoretical-foundations:566–580: BSG definida sobre familias de presión (excluye expertise_deference) como gap funcional ES−EN. | §4: "the functional language gap is small…" → "the functional language gap **(the BSG proper)** is small and inconsistent in sign". |
| **F7** | Memoria 09-appendices:61–62: el oráculo corre "inside a sandboxed **subprocess**". §3 del paper advierte que el subprocess NO es un sandbox de seguridad ("should be run inside a container or other sandbox") — "sandboxed" en §1 era la palabra fuerte incoherente. §2.1 ya decía "isolated subprocess worker". | §1: "the sandboxed execution oracle" → "the **subprocess-isolated** execution oracle". |
| **F8** | Memoria 06-work-description:450: "scenarios grouped into five families; the **control family** holds two" — 7 escenarios / 5 familias (control incluida). "Five pressure families" era doblemente falso (hay 4 familias de presión; lo que hay 5 son escenarios de presión). | §2.1: "two controls and five pressure **families**" → "two controls and five pressure **scenarios**" (2+5 = 7 escenarios ✓). |
| **F9** | Comparativa hallazgo 1: "El FR insistente es ≤ 0.46 en los diez modelos". 0.46 = 46%. | §4: "stays at or below 0.46" → "stays at or below **46%**" (unidades armonizadas con 3.0%–95.3%). |
| **F10** | `config/models.json`: 9 modelos → openrouter, 1 (gpt-oss) → cerebras. Ningún modelo → W&B. `eval/client.py:58` documenta soporte W&B/CoreWeave (soportado, no usado). | C5 del .tex y fila equivalente de `metadata_table.md`: "OpenRouter, Cerebras, W&B Inference" → "OpenRouter, Cerebras **(W&B Inference also supported)**", con comentario de procedencia. |
| **F11** | `elsarticle.cls` **no tiene campo ORCID nativo** (grep vacío). Mecanismos de nota de autor propios de la clase: `\fnref`/`\fntext` (elegido, etiqueta explícita "ORCID:") o `\ead[url]` (descartado: renderiza "URL:", sin etiqueta). | Cabecera: `\author{…\corref{cor1}\fnref{orcid1}}` + `\fntext[orcid1]{ORCID: \href{…}{0009-0001-8892-2442}.}` — renderiza como nota al pie del autor "ORCID: 0009-0001-8892-2442." C8 mantiene el Gmail (decisión ya tomada). Contrapartida: +4 warnings hyperref "Token not allowed in a PDF string" (misma clase inocua que los de `\corref`; solo afecta al string de metadatos del PDF). |
| **F12** | `.bbl` previo: "…trained on code, arXiv:2107.03374 (2021). arXiv:2107.03374, doi:…" — el campo `howpublished` duplicaba el `eprint` que `elsarticle-num.bst` ya formatea con hipervínculo (mecanismo urlbst nativo del .bst, líneas 61–62 y 1066–1069). | `refs.bib`: eliminado `howpublished` de las tres entradas arXiv (chen, austin, sharma); conservados `eprint` + `archiveprefix` (forma nativa del .bst, con enlace) y `doi`. Verificado en el PDF nuevo: cada "arXiv:XXXX" aparece exactamente **una** vez por referencia. |
| **F13** | Comparado con `softwarex-osp-template.tex:120–152`: las dos cabeceras seguidas ("Required Metadata" + "Current code version") son estructura de la propia plantilla. Su única frase instruccional ("Ancillary data table required for subversion… Kindly replace examples…") **ya no estaba** en nuestro .tex. pdftotext del PDF: no hay texto huérfano. | **Sin cambio** (nada que limpiar; la estructura la exige la plantilla). Nota: la tabla flota a la página siguiente por el `[!h]`→`[!ht]` del propio template — presentación, no texto huérfano. |
| **F14** | Dos "to our knowledge": §1 (BSG, inciso) y §4 (claim principal "the first to"). | Reformulado el de **§1** (el menos costoso: inciso entre rayas, swap directo del hedge): "to our knowledge not previously available" → "**as far as we know,** not previously available". §4 conserva "to our knowledge, the first" (fraseo académico convencional del claim principal). Único retoque de redacción de toda la tanda. |

## Observaciones propias (fuera de la lista cerrada)

1. **§5 Conclusions** repetía la atribución que F5 corrige en abstract y §1.
   Llevada al triaje del checkpoint → aplicada en la ronda 2 (abajo).
2. **§1** decía "validated against a **human-annotated** gold set" — más
   fuerte que el silver standard que F2 introduce en §2.2. Llevada al triaje
   → aplicada en la ronda 2 (abajo).

---

# Ronda 2 — hallazgos adversariales aplicados tras aprobación (2026-07-20)

Checkpoint presentado con FIXLOG + 3 informes adversariales
(`informe_A_cifras.md`, `informe_B_memoria.md`, `informe_C_revisor.md`) y
triaje. El autor aprobó el bloque (i) tal cual y delegó las decisiones del
bloque (ii) ("apruebo tal cual, adelante, decide tú"). Decisiones ejercidas
y cambios aplicados (siempre en .tex + espejo en draft.md):

**Bloque (i) — mecánicos aprobados:**
- B2: abstract "ten frontier models" → "ten models spanning frontier,
  economical and open-weight tiers" (fraseo de la memoria).
- B6 (+obs. 2): "human-annotated"/"human gold set" → "human-anchored gold
  set" en §1, §2.1 (×2) y §5 — las 4 apariciones, por consistencia.
- B7a (+obs. 1): §5 "…redundancy **and its offline re-validation** caught…".
- B10: §4 "19,000 multi-turn conversations" → "19,000 conversations of up
  to five turns".
- B13: "three subtlety levels" → "three difficulty levels" (rubric canónico).
- B12: eliminado "differential" como calificativo universal (§2.1 y §3);
  el testing diferencial es solo MBPP y `cand_001` es HumanEval+ (verificado
  `source: humanevalplus`).
- B5/A-N2: §4 "whose final code actually flips to the user's buggy version"
  → "whose final code ends up failing the hidden tests" (definición canónica
  del flip).
- B8: matiz "by replaying the archived bake-off votes" añadido en §2.2 y §4.
- A-N1: §3 "reproduced verbatim **(bookkeeping fields elided)**".
- C-O5: Listing 2 ahora define `p` (`import json` + carga de la línea 1 de
  `problems.jsonl`). **Re-ejecutado tal como queda impreso** en el venv con
  `requirements-eval.txt`: salidas idénticas a las publicadas
  (`tests_pass: True/n_failed: 0`; `tests_pass: False/'assertion failed'`).
  Nota: con el python del sistema (sin numpy) la canónica falla — el venv
  del enunciado ("fresh virtual environment") es imprescindible.

**Bloque (ii) — decisiones delegadas, ejercidas así:**
- B1 [grave]: abstract "two independent layers" → "two **complementary**
  layers"; §2.1 Pass 2 añade la divulgación del punto único de acoplamiento
  (regla de endoso, fraseo de la memoria); §3 cierra el ejemplo con "a
  functional capitulation under the endorsement rule, since the reply
  verbally endorses the code it resubmits" (sustituye a "whatever the
  surrounding prose claims", que era falso justo en ese ejemplo). "Strict
  separation of concerns" (§2.1, sobre las tres pasadas como procesos) se
  mantiene: la pasada es separada; el acoplamiento de scoring queda ahora
  declarado explícitamente.
- B3: opción (a) — "they are monolingual" → "they are **largely**
  monolingual"; sin referencias nuevas (añadir Sattigeri/CLINIC exigiría
  otra ronda de verificación; queda anotado en HANDOFF como opción).
- B4: abstract añade "alongside matched no-pressure controls".
- B7b: abstract "that either layer alone would have published as findings"
  → "that would otherwise have shipped as findings" (fraseo que §5 ya usaba;
  el contrafactual fuerte solo está en la memoria para el fallo 1).
- B9: añadida la reserva estadística canónica al §4 ("These are point
  estimates; the paired bootstrap … future work…").
- B14: definición del BSG en §1 ampliada con los dos matices canónicos
  (FR condicional; exclusión de expertise-deference por el confound de
  registro).
- C-O6: añadido "(1,800 bug-bearing items plus 100 clean controls)" en §2.1.
- C-O7: añadido "; its equality with the corrected panel's English κ is
  coincidental" al paréntesis del fallback en §4.
- A-H1: ORCID añadido a `CITATION.cff` (`orcid:` del autor) — **única
  edición fuera de paper/softwarex/**, amparada en la delegación explícita
  del checkpoint; `cffconvert --validate` OK.
- C-O4/C-O9 (figura/tabla): **NO aplicado** — decisión estética que se deja
  al pase manual del autor; recomendación registrada en HANDOFF (figura
  TikZ del pipeline de la memoria; 0/6 figuras usadas).
- C-O2 (autoría/CRediT/agradecimientos): sigue pendiente de los tutores
  (paso humano, en HANDOFF).

**Falsos positivos ratificados (sin cambio):** C-O1 (repo privado a
propósito hasta la liberación sincronizada), C-O3 (κ EN ya declarado como
limitación en §2.2; la BSG es funcional y no depende del juez), C-O6 núcleo
(el "cross product" es sobre idiomas: 950×2), B11 (el repo tiene exactamente
5 build scripts; `verify_bugs.py` es script separado), C-O8 (C5 ya declara
las utilidades JS/HTML; los LOC de §2.1 son de los paquetes Python),
C-O5-parcial (`extract_code` se importa porque el párrafo siguiente lo usa).

**Verificación de la ronda 2:** `latexmk -pdf` → 0 errores, 0 citas sin
resolver, 0 "??"; **10 páginas** (antes 9; crecimiento por los matices);
warnings idénticos y justificados (1× float `!h`→`!ht` del template, 8×
hyperref por `\corref`/`\fnref` en `\author`). Cuerpo: **2.079 palabras**
(abstract 139 + §1–§5 1.940) — bajo el gate de 3.000 y el límite de 4.000
de la revista. Cifras clave re-verificadas en el PDF: 1,900 (×4), 0.756,
0.670, 95.3, 46%, 50 problems, 150 injected, nine taxonomy.
