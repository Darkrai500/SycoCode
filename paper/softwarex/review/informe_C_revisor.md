# Informe de revisión — Revisor C (SoftwareX, Original Software Publication)

**Manuscrito:** "SycoCode: an execution-grounded bilingual benchmark and evaluation platform for measuring sycophancy in LLM code generation" — J. C. Negrín de la Fe (PDF de 9 páginas).
**Fecha de revisión:** 2026-07-20.
**Base de la revisión:** exclusivamente el PDF compilado, los requisitos públicos del formato OSP de SoftwareX y verificaciones externas por red (Crossref, DataCite, GitHub) realizadas por este revisor.

---

## (a) Resumen en 3 líneas

El manuscrito describe una plataforma de evaluación de la adulación (sycophancy) en generación de código LLM, con oráculo de ejecución más panel de jueces, y en general está bien enfocado al software, dentro del límite de palabras y con la estructura OSP correcta.
Sin embargo, el enlace GitHub "permanente" de la tabla de metadatos (C2) devuelve 404 —el código no es accesible para el revisor ni para ningún lector— y el manuscrito contiene dos placeholders "[TODO: ...]" en las secciones CRediT y Acknowledgements que revelan que la propia autoría está sin resolver.
Además, el ejemplo del Listing 2 no es reproducible tal como está impreso (variable `p` nunca definida, salidas truncadas pese a afirmarse "reproduced verbatim") y la Sección 4 imprime cifras de resultados sin soporte alguno visible en el PDF. Las 8 referencias, en cambio, verifican correctamente DOI a DOI.

## (b) VEREDICTO: **REJECT** (rechazo en su estado actual)

El rechazo se sustenta en dos defectos bloqueantes independientes: (1) el repositorio de código es inaccesible, lo que hace inevaluable un Original Software Publication, cuyo objeto de revisión es el software; y (2) el manuscrito se ha enviado con marcadores TODO visibles que documentan una autoría no acordada con los tutores, lo que además de denotar un envío prematuro plantea una cuestión ética de autoría que debe resolverse antes de cualquier evaluación. Una versión corregida (repositorio público, autoría resuelta, ejemplos autocontenidos y resultados soportados o retirados) podría ser reevaluada como envío nuevo.

## (c) Objeciones numeradas

### O1 — BLOQUEANTE: el repositorio de código declarado en C2 no es accesible

Cita textual (Tabla 1, C2): "`https://github.com/Darkrai500/SycoCode`".

Verificación de este revisor (2026-07-20): la URL devuelve **HTTP 404** tanto en la web (`curl -L https://github.com/Darkrai500/SycoCode`) como en la API (`https://api.github.com/repos/Darkrai500/SycoCode` → `{"message": "Not Found"}`). El usuario `Darkrai500` sí existe, pero el repositorio es privado o inexistente; una búsqueda pública en GitHub (`/search/repositories?q=SycoCode`) devuelve **0 resultados**. SoftwareX exige que el código esté disponible en un repositorio abierto y accesible en el momento de la revisión; sin él, es imposible verificar la arquitectura (Sección 2.1), la licencia MIT declarada (C3), la documentación referida en C7 ("`README.md`, `eval/README.md` and `docs/methodology/` in the repository") o afirmaciones como "Both corrections are documented in the repository, and the superseded numbers are archived rather than erased" (Sección 4) y "A fresh clone can therefore verify the platform end-to-end before spending anything" (Sección 3): hoy no puede hacerse ningún "fresh clone". La contribución que el paper dice ser —"The software contribution is the platform itself" (Sección 1)— no es inspeccionable.

**Gravedad: bloqueante.**

### O2 — BLOQUEANTE: placeholders TODO y autoría sin resolver en el manuscrito enviado

Cita textual (sección CRediT authorship contribution statement): "**[TODO: pendiente de confirmar autoría con los tutores (Antonio García Cabot, David de Fitero Domínguez) — borrador provisional solo con el estudiante:]**".

Cita textual (sección Acknowledgements): "**[TODO: redactar según la decisión de autoría: supervisión del TFG por Antonio García Cabot (tutor) y David de Fitero Domínguez (co-tutor), Universidad de Alcalá; financiación si aplica.]**".

Dos marcas de trabajo pendiente, en español, en un manuscrito en inglés supuestamente listo para revisión. No es solo un defecto de pulido: el propio texto declara que la lista de autores es un "borrador provisional" y que dos supervisores están pendientes de confirmación, es decir, la autoría —y la posible financiación— están sin resolver. Elsevier exige que la autoría esté acordada antes del envío; esto debe resolverse antes de que el manuscrito pueda siquiera evaluarse.

**Gravedad: bloqueante.**

### O3 — MAYOR: el instrumento incumple su propia puerta de validación en inglés

Cita textual (Sección 1): "the panel is validated against a human-annotated gold set using Cohen's κ [7] with an acceptance gate of **κ ≥ 0.6**".

Cita textual (Sección 2.2): "The shipped panel measures κ = 0.756 for the pilot configuration and κ = 0.670 for the cohort re-judge (**0.573 in English**, 0.718 in Spanish; the English figure is declared as a limitation in the results documentation)".

La capa verbal del panel, tal como se distribuye, queda **por debajo de la puerta de aceptación κ ≥ 0.6 en inglés**, uno de los dos únicos idiomas de una plataforma cuyo argumento de venta es precisamente la comparación bilingüe (el "Bilingual Sycophancy Gap"). Que la limitación esté "declared ... in the results documentation" (en un repositorio que además es inaccesible, véase O1) no la subsana en el manuscrito: la mitad inglesa de la medida discursiva no supera el criterio de calidad que el propio software impone, y el paper no discute qué validez tiene entonces el BSG verbal ni la afirmación "Spanish elicits more verbal capitulation than English in nine of ten models" (Sección 4), que descansa sobre esa capa.

**Gravedad: mayor.**

### O4 — MAYOR: cifras de resultados de investigación sin ningún soporte visible en el PDF

Citas textuales (Sección 4, Impact): "final-turn verbal capitulation spans **3.0% to 95.3%** — a more than thirty-fold spread"; "the fraction of initially-correct answers whose final code actually flips to the user's buggy version **stays at or below 46%** for all ten models"; "**Spanish elicits more verbal capitulation than English in nine of ten models**"; "The full ten-model campaign ... ran unattended for roughly **$370** in generation spend".

Ninguna de estas cifras tiene tabla, figura o referencia citable en el manuscrito: el PDF no contiene ni una sola tabla de resultados ni figura. Son afirmaciones empíricas concretas propias de un paper de resultados, impresas sin evidencia inspeccionable; el único soporte invocado es el repositorio ("documented in the repository"), que devuelve 404 (O1). En un OSP, la sección Impact puede ilustrar el uso del software, pero si se imprimen números, deben ser verificables. Estos pasajes —junto con la afirmación de novedad de investigación "SycoCode's measurements are, to our knowledge, the first to separate what a pressured model *says* from what its *code does*, bilingually, on executable ground truth" (Sección 4)— pertenecen a un artículo de resultados y, tal como están, deben retirarse o soportarse.

**Gravedad: mayor.**

### O5 — MAYOR: los ejemplos ilustrativos no son reproducibles tal como están impresos

Cita textual (Sección 3): "The examples below were executed on the published code in a fresh virtual environment (Python 3.12); **outputs are reproduced verbatim**".

Cita textual (Listing 2): "`grade_code(p["harness"], p["canonical_solution"], p["entry_point"])`".

Tres problemas concretos: (i) la variable **`p` no se define en ninguna parte** del manuscrito — no se muestra cómo cargar "the first problem's harness" (¿desde `data/problems/items.jsonl`? ¿con qué código?), de modo que el listado no puede ejecutarse tal cual; el `extract_code` importado en la primera línea ni siquiera se usa en el listado; (ii) las salidas del Listing 2 están truncadas con elipsis ("`# -> {'tests_pass': True, 'n_failed': 0, ...}`"), lo que contradice frontalmente el "reproduced verbatim" que las precede; (iii) no se imprime ningún paso de instalación (el `pip install` de `requirements-eval.txt` solo se alude en la celda C6 de la tabla de metadatos, nunca en la Sección 3). Y como condición previa a todo lo anterior, "the published code" no está publicado (O1): hoy ningún lector puede reproducir ni el Listing 1.

**Gravedad: mayor.**

### O6 — MENOR: la aritmética del dataset no se deriva de los números impresos

Cita textual (Sección 2.1): "50 problems ... 150 injected bugs (three per problem ...); 7 conversational scenarios (two controls and five pressure scenarios, including a five-turn insistence ladder); and the **1,900-item cross product** over two languages".

Un "cross product" literal de esas cantidades da 50 × 3 × 7 × 2 = 2.100 (o 150 × 7 × 2 = 2.100), no 1.900. El dry run del Listing 1 imprime `"scope_item_count": 38` por problema (38 × 50 = 1.900, autoconsistente), pero la regla de composición que produce 19 ítems por problema y lengua (26/6/6 por número de turnos) nunca se enuncia, y el término "cross product" es, tal como está impreso, incorrecto. El lector no puede reconstruir el tamaño del dataset a partir del texto.

**Gravedad: menor.**

### O7 — MENOR: κ = 0.573 aparece con dos papeles distintos sin aclaración

Cita textual (Sección 2.2): "κ = 0.670 for the cohort re-judge (**0.573 in English**, 0.718 in Spanish ...)".

Cita textual (Sección 4): "the offline re-validation against the gold set detected the drift and quantified the damage (**κ = 0.573 overall** for the fallback configuration, below the gate)".

El mismo valor exacto, 0.573, se atribuye en la página 5 al re-juicio inglés del panel *enviado* y en la página 7 al agregado *global* de una configuración fallback *descartada*. O es una coincidencia numérica notable que merece aclaración explícita, o una de las dos cifras es un error de copia; en cualquiera de los casos, tal como está, siembra dudas sobre el rigor del reporte numérico.

**Gravedad: menor.**

### O8 — MENOR: incoherencias menores en la tabla de metadatos (C5, C7)

Cita textual (C7): "`README.md`, `eval/README.md` and `docs/methodology/` in the repository" — no son enlaces, sino rutas relativas a un repositorio que devuelve 404 (O1); la celda pide "Link to developer documentation/manual".

Cita textual (C5): "Python (≥3.11), **JavaScript (annotation utilities), HTML**; ..." frente a la Sección 2.1: "SycoCode is a **Python (≥ 3.11) codebase of roughly 9,900 lines** organized as three packages" — el desglose de líneas (4.171 + 4.862 + 907 = 9.940) es íntegramente Python y el JavaScript/HTML declarado en C5 no aparece por ningún lado en la descripción de la arquitectura.

**Gravedad: menor.**

### O9 — MENOR: ausencia total de figuras en la descripción de una arquitectura de tres pasadas

Cita textual (Sección 2.1): "The pipeline has three passes with a strict separation of concerns".

El manuscrito no contiene ni una sola figura (el límite de SoftwareX es un máximo de 6, no un mínimo, así que no es una violación de plantilla), pero para un software paper cuyo núcleo es un pipeline de tres pasadas con dos capas de medición redundantes, la ausencia de un diagrama de arquitectura es un defecto de presentación evidente que dificulta la evaluación de la Sección 2.

**Gravedad: menor.**

### Aspectos verificados que NO dan lugar a objeción (en honestidad)

- **Extensión:** el cuerpo (Secciones 1–5) se estima muy por debajo de las ~4.000 palabras permitidas. Cumple.
- **Estructura OSP:** Motivation and significance; Software description (architecture + functionalities); Illustrative examples; Impact; Conclusions; tabla de metadatos C1–C8 formalmente completa; Declaration of competing interest presente; declaración de IA generativa presente y correctamente redactada ("the author used Claude (Anthropic) ... takes full responsibility"). La estructura cumple; el contenido de CRediT/Acknowledgements no (O2).
- **Foco en el software:** las Secciones 1–3 y 5 están genuinamente centradas en el software (arquitectura, funcionalidades, reutilización: "New models are one configuration entry away (any OpenAI-compatible endpoint)"). El desvío hacia resultados se concentra en la Sección 4 (O4).
- **Referencias:** las 8 verifican correctamente (sección d). No hay DOIs muertos ni discrepancias de título o autoría.

## (d) Verificación independiente de referencias, DOI a DOI

Método: `curl` contra `https://api.crossref.org/works/{doi}`; para los 404 de Crossref, `https://api.datacite.org/dois/{doi}`. Fecha: 2026-07-20.

| # | DOI impreso | API / HTTP | Título devuelto por la API | Cotejo con la bibliografía |
|---|---|---|---|---|
| [1] | `10.48550/arxiv.2310.13548` | Crossref 404 → **DataCite 200** | "Towards Understanding Sycophancy in Language Models" — Sharma, Mrinank; Tong, Meg; Korbak, Tomasz; Duvenaud, David; ... (2023) | **Coincide** (título, primer autor M. Sharma, año 2023). DOI DataCite, por eso el 404 de Crossref no es un DOI muerto. |
| [2] | `10.18653/v1/2023.findings-acl.847` | **Crossref 200** | "Discovering Language Model Behaviors with Model-Written Evaluations" — Perez, Ethan; Ringer, Sam; Lukosiute, Kamile; ... ACL, pp. 13387–13434, 2023 | **Coincide** (título, primer autor E. Perez, páginas 13387–13434 idénticas a las impresas). |
| [3] | `10.1145/3641289` | **Crossref 200** | "A Survey on Evaluation of Large Language Models" — Chang, Yupeng; et al. ACM Trans. Intell. Syst. Technol. 15(3), pp. 1–45 | **Coincide** (título, primer autor Y. Chang, volumen 15, número 3, páginas 1–45, 2024). |
| [4] | `10.48550/arxiv.2107.03374` | Crossref 404 → **DataCite 200** | "Evaluating Large Language Models Trained on Code" — Chen, Mark; Tworek, Jerry; Jun, Heewoo; ... (2021) | **Coincide** (título, primer autor M. Chen, año 2021). |
| [5] | `10.48550/arxiv.2108.07732` | Crossref 404 → **DataCite 200** | "Program Synthesis with Large Language Models" — Austin, Jacob; Odena, Augustus; Nye, Maxwell; ... (2021) | **Coincide** (título, primer autor J. Austin, año 2021). |
| [6] | `10.52202/075280-0943` | **Crossref 200** | "Is Your Code Generated by ChatGPT Really Correct? Rigorous Evaluation of Large Language Models for Code Generation" — Liu, Jiawei; Xia, Chunqiu Steven; ... NeurIPS, pp. 21558–21572, 2023 | **Coincide** (título, primer autor J. Liu, páginas 21558–21572 idénticas). Nota cosmética: la bibliografía imprime "chatgpt" en minúsculas por descuido de BibTeX. |
| [7] | `10.1177/001316446002000104` | **Crossref 200** | "A Coefficient of Agreement for Nominal Scales" — Cohen, Jacob. Educational and Psychological Measurement 20(1), pp. 37–46, 1960 | **Coincide** exactamente (título, autor, revista, volumen, número, páginas, año). |
| [8] | `10.2307/2529310` | **Crossref 200** | "The Measurement of Observer Agreement for Categorical Data" — Landis, J. Richard; Koch, Gary G. Biometrics 33(1), p. 159, 1977 | **Coincide** exactamente (título, autores, revista, volumen, número, página, año). |

**Conclusión de la verificación:** 8 de 8 DOIs resuelven y coinciden en título y autoría con lo impreso. No hay DOIs muertos ni referencias fabricadas. Los tres 404 de Crossref corresponden a DOIs de arXiv registrados en DataCite y verifican allí.

**Verificación adicional de red:** C2 (`https://github.com/Darkrai500/SycoCode`) → HTTP 404 en web y API de GitHub; usuario `Darkrai500` existente; búsqueda pública de repositorios "SycoCode" en GitHub → 0 resultados. Véase O1.

---

*Fin del informe del Revisor C.*
