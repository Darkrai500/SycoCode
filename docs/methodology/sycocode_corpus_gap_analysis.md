# SycoCode — Análisis de gaps del corpus bibliográfico

> **Status:** v0.1
> **Fecha:** 2026-04-25
> **Owner:** Juan Carlos Negrín (TFG, EPS-UAH)
> **Propósito:** auditar si el corpus bibliográfico (~28 entradas tras Fase B)
> respalda las decisiones del documento `sycocode_dataset_design.md`, e
> identificar las referencias adicionales que deben ingerirse para que la
> memoria pueda citar todas las afirmaciones que el diseño ya da por
> establecidas.

---

## 1. Método

Para cada sección con respaldo bibliográfico (`[DECIDED]` o `[TO RESEARCH]`)
del design doc, se ha comprobado:

1. Si el reclamo descansa sobre un paper concreto, ¿está ese paper en el
   corpus actual?
2. Si el reclamo invoca una práctica o convención (e.g., "translation
   parity", "bug taxonomy"), ¿hay alguna referencia canónica que la
   justifique en el corpus?
3. Si la respuesta a (1) o (2) es no, se ha hecho una búsqueda dirigida en
   arXiv y Semantic Scholar para identificar el candidato ideal.

El cruce se ha hecho contra el registro de ingesta de la biblioteca de
referencias del proyecto (28 entradas con tier y colección).

---

## 2. Cobertura del corpus actual

| Tema del design doc | Papers en corpus | Estado |
|---|---|---|
| Sycophancy seminal | 8 (Sharma 2023, Perez 2022, Wei 2023, Bai 2022, Gao 2022, Laban 2023, Denison 2024, Rimsky 2023) | ✅ Sólido |
| Sycophancy benchmarks | 11 (SycEval, SYCON-Bench, ELEPHANT, BrokenMath, PENDULUM, VISE, Psychosis-bench, Social Sycophancy Scale, EchoBench, SYAUDIO, Reese LLM-Judge psychosis) | ✅ Sólido |
| Mecanístico / mitigación | 6 (SPT, Vennemeyer, Kim, Cheng×2, Batzner) | ✅ Sólido |
| Multi-turn pressure | 3 (SYCON-Bench, FlipFlop, Noshin) | ✅ Cubre §7.2 |
| Persona / authority | 2 (ELEPHANT, Sharma) | ✅ Cubre §7.2 |
| Cross-lingual | 1 (Sattigeri Beacon→Hindi) | ⚠️ Insuficiente |
| Infrastructure / tooling | 1 (lm-evaluation-harness) | ⚠️ Insuficiente |
| **Foundational code-gen (HumanEval/MBPP/EvalPlus)** | 0 | ❌ **Gap crítico** |
| **Bilingual NL→code methodology** | 0 | ❌ **Gap crítico** |
| **Bug taxonomy / mutation testing** | 0 | ❌ **Gap crítico** |
| **Reproducibilidad (datasheets / data cards)** | 0 | ❌ **Gap crítico** |

---

## 3. Gaps confirmados y referencias propuestas

### 3.1. Foundational code-generation benchmarks — `[Tier S/A]`

El design doc construye Layer 1 sobre HumanEval, MBPP y EvalPlus, pero
ninguno de los tres papers está en el corpus. Citar el dataset que se
está usando es obligatorio.

| Paper | arXiv | Cites | Tier | Por qué |
|---|---|---|---|---|
| Chen et al. 2021 — *Evaluating LLMs Trained on Code* (HumanEval) | 2107.03374 | 9203 | S | Fuente primaria de `problems.jsonl` |
| Austin et al. 2021 — *Program Synthesis with LLMs* (MBPP) | 2108.07732 | 3466 | S | Fuente primaria alternativa |
| Liu et al. 2023 — *EvalPlus* | 2305.01210 | — | S | §3.3 lo invoca como mitigación de contaminación |
| Jain et al. 2024 — *LiveCodeBench* | 2403.07974 | 1350 | A | Refuerza el argumento de contaminación con benchmark contamination-free |
| Riddell et al. 2024 — *Quantifying Contamination* | 2403.04811 | 58 | A | Cuantifica el problema afirmado en §3.3 |

### 3.2. Bilingual / cross-lingual code-generation — `[Tier S/A]`

El gap más serio del corpus actual: solo Sattigeri (un paper de
extensión a Hindi). Para sostener la metodología EN/ES de SycoCode hace
falta literatura específica sobre cómo se construyen benchmarks de
código en múltiples lenguas naturales.

| Paper | arXiv | Tier | Por qué |
|---|---|---|---|
| **Peng et al. 2024 — HumanEval-XL** | 2402.16694 | S | **Es el paradigma de SycoCode**: 23 lenguas naturales × 12 lenguajes de programación, datos paralelos, 22 080 prompts. Incluye español. |
| Cassano et al. 2022 — MultiPL-E | 2208.08227 | A | Metodología canónica para extender un benchmark a múltiples lenguajes (de programación). |
| Zheng et al. 2023 — CodeGeeX / HumanEval-X | 2303.17568 | A | HumanEval traducido a mano a 5 PLs — antecedente directo. |
| Xu et al. 2025 — Cross-Lingual Pitfalls | 2505.18673 | A | Genera bilingual question pairs para revelar weaknesses; metodología útil para BSG. |
| Agrawal et al. 2024 — *Translation Errors in XNLI* | 2402.02080 | A | Translation parity protocol — exactamente lo que §7.2 pide. |
| Mayor-Rocher et al. 2025 — *Spanish Varieties* | 2504.20049 | B | Variedades dialectales del español, refuerza la calibración cultural en BSG. |

### 3.3. Bug taxonomy y mutation testing — `[Tier S/A]`

§3.3 del design doc tiene un `[OPEN]` explícito sobre la taxonomía de
bugs y §3 ejecuta una "manual bug injection method" sin grounding
metodológico. Las siguientes referencias resuelven ambos.

| Paper | Cite | Tier | Por qué |
|---|---|---|---|
| **Tambon et al. 2024 — Bugs in LLM-generated code** | arXiv 2403.08937, EmpSE, 98 cites | S | Taxonomía empírica de 10 patrones de bugs en código generado por LLMs (Misinterpretations, Silly Mistake, Missing Corner Case, Wrong Input Type, Hallucinated Object, etc.). Base directa para el enum de §3.3. |
| Jia & Harman 2011 — *Mutation Testing Survey* | IEEE TSE, 1816 cites | S | Referencia canónica que fundamenta la metodología de bug injection como variante de mutation testing. |
| Papadakis et al. 2019 — *Mutation Testing Advances* | Adv Comp, 491 cites | A | Follow-up moderno; cubre los 10 años posteriores al survey de Jia&Harman. |
| Thung, Lo & Jiang 2012 — *Automatic Defect Categorization* | WCRE, 122 cites | B | Operacionaliza Orthogonal Defect Classification (IBM ODC); útil como esqueleto de taxonomía. |
| Siddiq et al. 2024 — *The Fault in our Stars* | arXiv 2404.10155 | B | Audit de calidad en benchmarks de code-gen; refuerza por qué hay que verificar `verified_failing`. |

### 3.4. Reproducibilidad y dataset documentation — `[Tier S/A]`

§1 del design doc abre con la pregunta "¿puede alguien clonar el repo
en dos años y reproducir todo?" — y §6 fija JSONL/Parquet con esa
misma intención. Sin embargo no hay ni una sola cita que respalde el
marco de documentación de datasets que el diseño ya está siguiendo.

| Paper | arXiv | Tier | Por qué |
|---|---|---|---|
| **Gebru et al. 2018 — Datasheets for Datasets** | 1803.09010 | S | Cita obligada para el reclamo de reproducibilidad de §1 y §6. Marco original (electronics-style datasheet). |
| Pushkarna et al. 2022 — *Data Cards* | 2204.01075 | A | Versión más operativa; encaja directamente con la separación Layer 1/2/3 del diseño. |
| Bender & Friedman 2018 — *Data Statements for NLP* | (40 cites, no arXiv) | A | NLP-specific; refuerza la documentación bilingüe. |

---

## 4. Decisiones estructurales propuestas

### 4.1. Nuevas colecciones en la biblioteca de referencias

Las dos colecciones existentes (`02-Benchmarks` para sycophancy,
`06-Infrastructure` para tooling) no encajan con los grupos 3.1–3.4. Se
proponen dos colecciones nuevas:

- **`07-CodeGen-Foundations`** — para los grupos 3.1 y 3.2 (HumanEval,
  MBPP, EvalPlus, MultiPL-E, HumanEval-X, HumanEval-XL, LiveCodeBench,
  Cross-Lingual Pitfalls, Translation Errors XNLI, Spanish Varieties,
  Quantifying Contamination, Fault in our Stars).
- **`08-Methodology`** — para los grupos 3.3 y 3.4 (Tambon, Jia&Harman,
  Papadakis, Thung-Lo-Jiang, Gebru, Pushkarna, Bender&Friedman).

### 4.2. Plan de ingesta por fases

- **Fase Tier S (5 papers)** — bloqueante para que el design doc pueda
  citarse sin huecos. Se ingiere ya:
    1. Chen 2021 — HumanEval → `07-CodeGen-Foundations`
    2. Austin 2021 — MBPP → `07-CodeGen-Foundations`
    3. Liu 2023 — EvalPlus → `07-CodeGen-Foundations`
    4. Peng 2024 — HumanEval-XL → `07-CodeGen-Foundations`
    5. Gebru 2018 — Datasheets for Datasets → `08-Methodology`
- **Fase Tier A/B (~14 papers)** — segunda ronda en otra sesión, con
  luz verde explícita por grupo.

---

## 5. Mapeo a los `[OPEN]` del design doc

| Item `[OPEN]` o `[TO RESEARCH]` | Resuelto por |
|---|---|
| §3.3 — Bug taxonomy enum | Tambon 2024 (10 patrones) + Thung-Lo-Jiang (ODC) |
| §3.3 — Source mix HumanEval/MBPP/EvalPlus | Riddell 2024 + LiveCodeBench (cuantifican contaminación) |
| §3 — Bug-injection methodology | Jia & Harman 2011 + Papadakis 2019 (mutation testing como marco) |
| §4.5 — Multi-turn pressure design | Ya cubierto por SYCON-Bench, SycEval, BrokenMath en corpus |
| §4.6 — Persona authority | Ya cubierto por ELEPHANT, Sharma 2023 |
| §7.2 — Bilingual benchmark conventions | Peng 2024 (HumanEval-XL) + Agrawal 2024 + Cassano 2022 |
| §1, §6 — Reproducibilidad | Gebru 2018 + Pushkarna 2022 + Bender&Friedman 2018 |

---

## 6. Change log

| Versión | Fecha | Cambio |
|---|---|---|
| 0.1 | 2026-04-25 | Análisis inicial. Identificadas 4 áreas con gap, 19 papers candidatos (5 Tier S, ~14 Tier A/B). Plan de ingesta por fases. |
