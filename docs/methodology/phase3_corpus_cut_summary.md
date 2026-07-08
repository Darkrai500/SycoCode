# SycoCode — Resumen de sesión: corte final del corpus (Fase B · paso 3)

> **Propósito de este documento.** Resumen largo y autocontenido de todo lo
> hecho en la sesión del **25/05/2026** para cerrar la selección de problemas del
> benchmark. Pensado para ponerme al día a mí mismo (Claude) en un chat normal:
> contiene contexto suficiente para entender el estado del TFG sin haber visto la
> sesión original. No reemplaza a `candidates_phase3_notes.md` (el informe
> técnico completo); lo resume y lo sitúa en el proyecto.

---

## 0. Contexto del TFG (para un chat sin memoria)

**SycoCode** es el TFG de Juan Carlos Negrín (EPS-UAH, Grado en Ingeniería en
Sistemas de Información): un **benchmark bilingüe (ES/EN) de *sycophancy* en LLMs
aplicada a generación de código**. La hipótesis: los asistentes de código tienden
a "ceder" (capitular) ante la presión o la insistencia del usuario aunque el
código tenga un bug real, y eso es medible y puede diferir entre español e
inglés.

**Arquitectura del dataset (3 capas):**
- `problems.jsonl` — banco de problemas, cada uno con 3 bugs inyectados (b1, b2, b3).
- `scenarios.jsonl` — plantillas de prompt por escenario × idioma (7 escenarios:
  5 de presión + 2 de control).
- `items.jsonl` — producto cartesiano resuelto por script (~1.830 unidades evaluables).

**Métricas:** FR (Flip Rate), ΔBDA, FPR/AFR, **SS (Susceptibility Score, ponderada
por dificultad del bug)**, ToC (Turn of Capitulation), **BSG (Bilingual
Sycophancy Gap)** y un SycophancyIndex compuesto.

**Taxonomía de bugs — 9 categorías (cerrada como enum):**
`off_by_one`, `wrong_operator`, `wrong_value`, `wrong_function_call`,
`missing_edge_case`, `excess_logic`, `off_specification`, `api_misuse`,
`precision_or_overflow`.

**Por qué importa la cobertura de categorías:** SS se calcula **por categoría**.
Si una categoría queda vacía o demasiado fina, SS no es computable/fiable ahí. Por
eso el corte de problemas no puede ser un simple ranking de calidad.

---

## 1. Qué era la Fase B · paso 3

El **pipeline de selección de problemas** tiene este recorrido real (no fue el
174→50 directo que se planteó al principio):

| Etapa | Entrada → salida | Criterio | Fichero |
|---|---|---|---|
| Descarga | — → 591 crudos | HumanEval 164 + MBPP-sanitized 427 | `data/raw/**` |
| Paso 1 / 2 (candidatos) | 591 → **174** | dedupe + ≥2 categorías por candidato | `candidates_phase1.jsonl` |
| Reanotación | 174 → 174 | re-puntuación bajo criterio estricto C | `reannotated/candidates_phase1_reannotated.jsonl` |
| **Paso 2 (calidad)** | 174 → **90** | `quality_score ≥ 6.5` + 2 cuotas duras | `candidates_phase2.jsonl` |
| **Paso 3 (compuesto)** ← *esta sesión* | 90 → **50** | criterio multi-eje | `candidates_phase3.jsonl` |

El **paso 3** es el último paso **reversible** antes de la inyección manual de
bugs. La tarea: cortar de 90 a exactamente 50 con un criterio multi-eje
defendible, añadiendo un `phase3_rationale` por problema.

---

## 2. El criterio (multi-eje, NO ranking de calidad)

La justificación de cabecera del informe:

> *Se aplicó un criterio multi-eje (umbral de calidad, cobertura de categorías,
> diversidad de fuente, diferenciación estructural) en lugar de un ranking de
> calidad puro, porque el benchmark depende de la computabilidad conjunta de FR,
> ΔBDA y SS en todas las categorías de bug.*

**Por qué no ranking puro:** un top-50 por `quality_score` habría retenido solo
**2 problemas MBPP (~4 %)** —los dos únicos MBPP con q ≥ 7.5—, lo que es
prácticamente 100 % HumanEval+ y **colapsa la narrativa de mitigación de
contaminación** (uno de los aportes del TFG). El criterio compuesto sacrifica
deliberadamente algo de calidad HE+ para sostener diversidad de fuente y cobertura.

**Los cuatro ejes:**
1. **Umbral de calidad** — heredado: todos los 90 ya tenían `quality_score ≥ 6.5`.
   No se subió el umbral ni se re-puntuó nada.
2. **Cobertura de categorías** — las 9 categorías deben quedar no vacías; cuotas
   duras heredadas + *floors* propuestos para las minoritarias.
3. **Diversidad de fuente** — MBPP fijado en 10/50 (20 %), por encima del
   proporcional.
4. **Diferenciación estructural** — cada cluster estructural del paso 2 resuelto a
   **≤ 2 representantes**.

---

## 3. Decisiones tomadas

### 3.1 Mezcla de fuente: 40 HumanEval+ / 10 MBPP

- Pool de entrada (90): 75 HE+ / 15 MBPP.
- Proporcional a 50 ≈ 42/8. **Elegí 40/10** → MBPP al 20 % (por encima del 16.7 %
  del pool).
- ⚠️ **Desviación del diseño original.** El Mapa global registraba "35 HumanEval +
  15 MBPP" como *mix* decidido. El corte final es **40/10**, no 35/15. Motivo:
  el paso 2 ya había dejado solo 15 MBPP viables y **5 de ellos eran duplicados
  estructurales o sub-7.0 con tests débiles**; mantenerlos habría reintroducido
  basura y violado el eje de diferenciación. El brief del paso 3 daba autoridad
  explícita sobre el ratio y fijaba el proporcional (~42/8) como referencia.
  **El usuario revisó esta desviación y la aprobó** ("no así está bien").
  Reversible a 42/8 si en el futuro se prioriza calidad sobre diversidad.

### 3.2 Floors de categorías minoritarias = 5 cada una

| Categoría | En pool (90) | Floor propuesto | Aterriza en (50) |
|---|---|---|---|
| `precision_or_overflow` | 9 | 5 | **8** |
| `wrong_value` | 11 | 5 | **8** |
| `wrong_function_call` | 12 | 5 | **10** |

Los tres *floors* son protectores, no vinculantes: los portadores son en su
mayoría q8.0/q7.5 HE+ y sobreviven por mérito. `wrong_function_call` tuvo la
retención más baja en el paso 2 (46 %) y se marcó como categoría a enriquecer
activamente en fases posteriores.

### 3.3 Cuotas duras (intactas, heredadas del paso 2)

- `excess_logic` (n=1): **cand_005** (`intersperse`, q8.5).
- `api_misuse` (n=3): **cand_017** (`sort_numbers`), **cand_064** (`is_bored`),
  **cand_129** (`left_insertion`, MBPP).

### 3.4 Resolución de clusters estructurales (≤ 2 representantes)

| Cluster | Conservados | Descartados |
|---|---|---|
| Primalidad | cand_026, cand_067 (+ cand_022 factorización, tratado como distinto) | cand_104 |
| Monotonía / ordenación | cand_038, cand_098 | cand_092, cand_008 |
| Palíndromo | cand_009 (construye), cand_051 (cuenta cambios) | cand_034, cand_050 |
| Brackets | cand_037 | cand_096 |
| Triángulo | cand_049 (Heron) | cand_114 (Pitágoras) |
| Búsqueda binaria (MBPP) | cand_128 (first occ.), cand_129 (cuota) | cand_136 (last occ.) |
| Max-product (MBPP) | cand_171 (subarray, Kadane) | cand_174 (subsecuencia, LIS) |
| Palabras-número inglés | cand_017 (cuota) | cand_073 |
| Suma sobre rango | cand_137 | cand_040 (trivial cd5), cand_155 (tests débiles) |
| Potencia / cuadrado mínimo (MBPP) | cand_154 + cand_160 (ambos, distintos) | — |

---

## 4. Composición final (90 → 50)

### Por fuente
| Fuente | Pre (90) | Post (50) |
|---|---|---|
| `humanevalplus` | 75 | **40** |
| `mbpp_sanitized` | 15 | **10** |

### Por categoría (slots; cada problema admite varias)
| Categoría | Pre (90) | Post (50) |
|---|---|---|
| `wrong_operator` | 67 | 35 |
| `missing_edge_case` | 61 | 33 |
| `off_by_one` | 45 | 28 |
| `off_specification` | 31 | 14 |
| `wrong_function_call` | 12 | 10 |
| `wrong_value` | 11 | 8 |
| `precision_or_overflow` | 9 | 8 |
| `api_misuse` | 3 | 3 |
| `excess_logic` | 1 | 1 |

### Los 50 supervivientes

**HumanEval+ (40):** cand_001, cand_003, cand_004, cand_005, cand_007, cand_009,
cand_016, cand_017, cand_018, cand_019, cand_020, cand_022, cand_026, cand_033,
cand_037, cand_038, cand_042, cand_043, cand_044, cand_046, cand_047, cand_049,
cand_051, cand_055, cand_061, cand_064, cand_067, cand_069, cand_074, cand_080,
cand_081, cand_082, cand_090, cand_097, cand_098, cand_101, cand_102, cand_103,
cand_107, cand_118.

**MBPP-sanitized (10):** cand_120, cand_128, cand_129, cand_131, cand_133,
cand_137, cand_138, cand_154, cand_160, cand_171.

---

## 5. Los 40 descartados (agrupados por razón)

- **Duplicado / echo estructural (13):** cand_104, cand_092, cand_008, cand_034,
  cand_050, cand_096, cand_114, cand_073, cand_040, cand_063 (HE+) + cand_136,
  cand_174, cand_155 (MBPP).
- **Calidad marginal en categoría saturada (24):** 11 a q7.5 (cand_011, cand_012,
  cand_054, cand_071, cand_078, cand_079, cand_083, cand_084, cand_088, cand_099,
  cand_115) + 13 a q7.0 (cand_010, cand_021, cand_027, cand_039, cand_057,
  cand_062, cand_077, cand_094, cand_106, cand_109, cand_111, cand_113, cand_116).
- **Suelo de calidad / balance de fuente (3):** cand_032 (HE+ q6.5), cand_124
  (MBPP q6.5), cand_168 (MBPP q6.5).

---

## 6. Self-check de restricciones duras (todas ✔)

- Conteo = **50 exacto** (40 HE+ + 10 MBPP); 40 descartados.
- **Sin candidatos nuevos**: subconjunto estricto de los 90.
- **Cuotas íntegras**: cand_005 / cand_017 / cand_064 / cand_129 presentes y sin tocar.
- **9 categorías no vacías** (mínimo `excess_logic` = 1, cuota).
- **MBPP > 0** (10, 20 %).
- **Sin regresiones de calidad**: mínimo `quality_score` retenido = 6.5 (cand_133).
- **Esquema preservado**: solo se añadió `phase3_rationale`; `quality_score`,
  `admitted_categories`, `rationale`, `quality_breakdown` copiados verbatim
  (verificado por script contra `candidates_phase2.jsonl`).

---

## 7. Riesgos conocidos del corte

- **Categorías más finas:** `excess_logic` (1) y `api_misuse` (3) viven solo por
  cuota → SS frágil ahí (déficit heredado del corpus, no introducido). Siguientes
  más finas: `wrong_value` y `precision_or_overflow` (8).
- **3 *watchlist keeps* del paso 2 descartados:** cand_032, cand_077, cand_124
  (ninguno regresión de calidad). **cand_077 es el más discutible** — el paso 2 lo
  elogió como "excelente sonda de sycophancy"; se descartó como q7.0 mono-eje en
  las dos categorías más saturadas. cand_133 (la cuarta) **sí** se conserva.
- **Trade calidad-por-diversidad:** retener 10 MBPP (mayoría tr6, dos en q6.5)
  desplaza ~11 HE+ q7.5 con mejores tests. Intencional (eje 3).
- **Echo residual más fino:** par MBPP cand_128 ↔ cand_129 (*first-occurrence* vs
  *left-insertion-point*), inevitable porque cand_129 es cuota.

---

## 8. Artefactos producidos en esta sesión

**Repositorio (rama `master`):**
- `data/problems/candidates_phase3.jsonl` — 50 filas, esquema verbatim + `phase3_rationale`.
- `data/problems/candidates_phase3_notes.md` — informe técnico completo (criterio,
  floors, clusters, 40 descartes uno a uno, self-check, riesgos).
- **Commit `c6de415`** — "Add phase 3 composite cut: 90 → 50 final problems"
  (mensaje terso; el detalle vive en las notas).
- `docs/phase3_corpus_cut_summary.md` — **este documento** (creado en el working tree; sin commitear todavía).

**Notion (workspace SycoCode — TFG):**
- **Nueva página** "Corte final del corpus — SycoCode (Fase B · paso 3)" →
  `36bab5f9dd598179ba81cf6b90d8fe51`.
- **Mapa global del TFG** (`34dab5f9dd5981259c76ed22c7939502`) actualizado: línea
  de fases, *mix* final 40/10 con nota de desviación, paso 3 del pipeline ✅,
  próximos pasos, footer (25/05).
- **Página del primer corte** (`35fab5f9dd598190910ae54b8f5a3425`) con puntero al corte final.

**Memoria de Claude Code (file-based):**
- `project_sycocode.md` actualizado a estado 25/05/2026 (selección cerrada, mix
  40/10 con motivo de la desviación, IDs de páginas Notion nuevas).

---

## 9. Siguiente hito (Fase B continúa)

Con los 50 fijados, lo siguiente es la **construcción real del dataset**:
1. **Inyección manual de 3 bugs por problema** (b1, b2, b3), cada uno con
   `verified_failing: true` → *ground truth* determinista, sin LLM-as-judge.
2. **Asignación de nivel L1/L2/L3** por complejidad de razonamiento (rúbrica v1.0
   ya cerrada).
3. **Selección del subset de FPR**: 15 problemas marcados `include_in_fpr_subset: true`.
4. Después: plantillas `scenarios.jsonl` EN/ES y `build_items.py` para materializar la Capa 3.

> Nota de proceso: el usuario trabaja por **fases con prompts operativos** y espera
> **pausa + report entre fases**, no encadenar automáticamente.

---

*TFG SycoCode · Juan Carlos Negrín · resumen de sesión 25/05/2026.*
</content>
