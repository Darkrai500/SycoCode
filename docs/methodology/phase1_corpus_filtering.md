# Fase B · paso 1 — Primer corte del corpus (informe)

> **Estado:** primer corte cerrado el **2026-05-13**.
> **Resultado:** **174** candidatos a partir de los 591 problemas crudos (HumanEval+ 118 · MBPP sanitized 56 · HumanEval 0).
> **Siguiente:** segunda iteración del filtro (174 → ~50) con *rationale* por problema.

## 1. Contexto

La memoria fija un dataset de **50 problemas** con 3 bugs cada uno, cubriendo las **9 categorías** de la Tabla 2.1 (§2.4). Para llegar a esos 50 el *pipeline de selección* tiene tres pasos:

1. **Descarga local** del pool (HumanEval 164 + HumanEval+ 164 + MBPP sanitized 367 → 591 problemas crudos, deduplicación inter-fuentes pendiente). *Cerrado antes de hoy.*
2. **Primer corte** por criterios de admisión, *ground truth* limpia y diversidad categórica. **Este informe.**
3. **Corte final** a 50 problemas con *rationale* documentado y muestreo estratificado por categoría. *Pendiente.*

## 2. Entradas y deliverables

**Pool de partida** (en `data/raw/`):

| Fuente | Fichero | Revisión | N |
|---|---|---|---|
| HumanEval | `humaneval/humaneval.jsonl` | `7dce605` | 164 |
| HumanEval+ | `humanevalplus/humanevalplus.jsonl` | `d32357c` | 164 |
| MBPP sanitized | `mbpp_sanitized/mbpp_sanitized.jsonl` | `4bb6404` | 367 |
| **Total bruto** | | | **695** |
| **Tras dedupe HumanEval ⇒ HumanEval+** | | | **531 únicos** |

**Deliverables (en `data/problems/`):**

- `candidates_phase1.jsonl` — 174 líneas JSON, una por candidato. Campos: `candidate_id` (`cand_001`…`cand_174`), `source`, `original_id`, `task_brief` (EN), `admitted_categories` (≥2 de las 9), `rationale` (≤2 frases EN), `concerns` (opcional).
- `candidates_phase1_coverage.md` — Tabla A (cobertura por categoría) y Tabla B (distribución por fuente).
- `candidates_phase1_notes.md` — criterios aplicados, banderas rojas, *watchlist* y hallazgos.

## 3. Resultado en una mirada

### Distribución por fuente

| Fuente (slug en `data/raw/`) | Candidatos |
|---|---|
| `humanevalplus` | 118 |
| `mbpp_sanitized` | 56 |
| `humaneval` | 0 |
| **Total** | **174** |

`humaneval` queda a cero por construcción: HumanEval+ mirror los 164 prompts con tests más estrictos y la regla de deduplicación se resuelve siempre a su favor.

### Cobertura por categoría (Tabla 2.1)

| Categoría | Candidatos que la admiten |
|---|---|
| `missing_edge_case` | 149 |
| `wrong_operator` | 121 |
| `off_by_one` | 96 |
| `off_specification` | 86 |
| `wrong_value` | 34 |
| `wrong_function_call` | 20 |
| `precision_or_overflow` | 12 |
| `excess_logic` | **2** 🚩 |
| `api_misuse` | **2** 🚩 |
| **Total category-slots** | **522** |

Media de categorías admitidas por candidato: **3.0** (un candidato suma a varias filas).

### Banderas rojas

- **`excess_logic` (2)** y **`api_misuse` (2)** están por debajo del umbral de 10 fijado en el *brief*. Es un déficit intrínseco: HumanEval/MBPP tienen canónicas deliberadamente concisas (poco margen para `excess_logic`) y baja superficie de stdlib (poco margen para `api_misuse`). La Tabla 2.1 sitúa ambas en L2–L3, así que el déficit es de nivel medio/alto, no de superficie.
- **`wrong_function_call` (20)** y **`precision_or_overflow` (12)** son finas pero por encima del umbral.

**Acción para el paso 3:** (a) reanotar conservadoramente candidatos con tres categorías donde `excess_logic`/`api_misuse` también encajen plausiblemente, o (b) admitir 2-3 MBPP adicionales con uso ligero de stdlib (`bisect`, `collections.Counter`, `itertools.groupby`) donde `api_misuse` sea natural. Decisión de diseño explícita pendiente.

## 4. Decisiones de criterio (resumen)

1. **Determinismo y *oracle quality*** — fuera dependencias de tiempo, RNG, red o librerías no-stdlib. Fuera `HumanEval/32` (semilla aleatoria) y `HumanEval/162` (md5).
2. **Rango de sensibilidad sycofántica** — fuera los one-liners triviales sin "dirección errónea" plausible (`square_perimeter`, `is_upper`, `volume_cube`) y fuera los problemas demasiado algorítmicos donde la sycophancy se confundiría con capacidad cruda (`MBPP/734 sum_Of_Subarray_Prod`, `MBPP/302 lps`).
3. **≥2 categorías por candidato** — borderline mono-categoría descartados.
4. **Canónicas rotas o discutibles fuera** — `MBPP/605 prime_num`, `MBPP/765 is_polite`, `MBPP/138 is_Sum_Of_Powers_Of_Two` excluidos para no contaminar el ground truth.
5. **Deduplicación inter-fuentes** — HumanEval ↔ HumanEval+ siempre a favor de HumanEval+. MBPP semánticamente equivalente a un HumanEval+ se descarta. Donde MBPP aporta tests distintos al HumanEval+ (`monotonic` ↔ `is_Monotonic`, `next_smallest` ↔ `second_smallest`) se conservan ambos.

Detalle completo en `data/problems/candidates_phase1_notes.md`.

## 5. Watchlist — 7 candidatos para revisión humana antes del paso 3

| ID | Origen | Función | Duda |
|---|---|---|---|
| `cand_028` | HumanEval/34 | `unique` | Canónica `sorted(list(set(l)))`; bug ladder ambicioso obligatorio para aportar valor. |
| `cand_032` | HumanEval/44 | `change_base` | Contrato para `n=0` ambiguo (canónica devuelve cadena vacía). |
| `cand_077` | HumanEval/110 | `exchange` | Verificar si HumanEval+ estresa el borde `even2 == odd1`. |
| `cand_091` | HumanEval/125 | `split_words` | Tercera rama devuelve conteo de dígitos → rompe uniformidad de tipo. |
| `cand_124` | MBPP/625 | `swap_List` | In-place vs copia: el test enmascara la distinción. |
| `cand_133` | MBPP/767 | `get_pairs_count` | Verificar conteo ordenado vs no-ordenado del spec. |
| `cand_169` | MBPP/452 | `loss_amount` | Definición de "loss" (sale > cost) semánticamente discutible. |

## 6. Hallazgos secundarios

- **HumanEval+ atrapa exactamente lo que HumanEval no.** Casos como `HumanEval/22 (filter_integers)` y `HumanEval/92 (any_int)` (gotcha `isinstance(x, int)` con booleanos) son target ideal: HumanEval pasa, HumanEval+ falla — la dirección natural para inyectar bugs.
- **Duplicación intra-MBPP.** `MBPP/758` ↔ `MBPP/779` (mismo `unique_sublists`); `MBPP/12 sort_matrix` ↔ `MBPP/805 max_sum_list` (ambos `max(lists, key=sum)`). Se conserva uno de cada par.
- **Canónicas MBPP sutilmente rotas.** `MBPP/605 prime_num` (`True` en `n=2` por el `for/else`), `MBPP/126 sum` (shadowing del builtin + off-by-one en `range(1, min(a,b))`), `MBPP/138`. Excluidas aquí, pero anotables como un futuro "natural bug corpus" para otro estudio.

## 7. Próximos pasos

1. **Resolver la watchlist** (§5): cada item se confirma o se descarta.
2. **Decisión de diseño**: ¿admitir candidatos extra con stdlib ligera para cubrir `excess_logic`/`api_misuse`, o reanotar los existentes? Documentar en la página de decisiones de dataset.
3. **Paso 3 del pipeline**: reducir 174 → 50, con *rationale* por problema y estratificación que garantice ≥1 candidato por categoría (incluyendo las dos infrarrepresentadas), cobertura del subset de FPR (`include_in_fpr_subset: true` en 15 problemas) y diversidad algorítmica (listas, strings, dicts, matemáticas, control flow).
4. Tras los 50 fijados → inyección manual de 3 bugs por problema (Frente A del hub).

## Apéndice — Procedencia

- **Subagente ejecutor:** `problem-filterer` (definido en `.claude/agents/problem-filterer.md`).
- **Fuentes inmutables:** `data/raw/` con las revisiones citadas en §2.
- **Deliverables versionables:** `data/problems/candidates_phase1*` (este informe los referencia, no los duplica).
- **Reproducibilidad:** todo el corte es determinista y replicable invocando al subagente con el mismo *brief* sobre los mismos *jsonl* crudos.
