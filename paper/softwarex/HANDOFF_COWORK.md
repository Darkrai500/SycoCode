# HANDOFF — Preparación SoftwareX (estado a 2026-07-20)

> **Actualización 2026-07-20 — corrección + revisión adversarial.** Sobre el
> manuscrito se aplicaron los 14 fixes de la revisión externa (F1–F14) y,
> tras un checkpoint aprobado por el autor, los hallazgos de una revisión
> adversarial con tres subagentes de contexto fresco (auditor de cifras,
> auditor de consistencia con la memoria, revisor hostil SoftwareX). Todo
> documentado en `paper/softwarex/review/`: `FIXLOG.md` (fix → fuente →
> cambio, dos rondas) + `informe_A_cifras.md` (56 verificados / 1 no
> trazable / 0 contradichos) + `informe_B_memoria.md` (14 discrepancias,
> aplicadas o justificadas) + `informe_C_revisor.md` (simulacro de rechazo;
> objeciones triadas). Estado actual del PDF: 10 páginas, 0 errores,
> cuerpo ~2.079 palabras. ORCID del autor (0009-0001-8892-2442) en la
> cabecera del .tex (\fnref/\fntext) y en `CITATION.cff`.

## Estado final

Las tres fases del encargo están completas en la rama **`softwarex-prep`**
(local, **sin push** — guardarraíl respetado; sin cambios de visibilidad ni
subidas a servicios externos):

| Commit | Contenido |
|---|---|
| `8a5fb9b` | Fase 1 — `PUBLICATION_READINESS.md` (veredicto **GO condicionado**) |
| `f367fb4` | Fase 2 — fixes mecánicos B1–B4 + N1–N3, verificados; tag local `v1.0.0` |
| (este) | Fase 3 — `paper/softwarex/` completo |

Verificación de la Fase 2 (en venv limpio, Python 3.12.13): instalación
combinada de ambos requirements OK, **6/6 scripts de test en verde (127
checks)**, `python -m eval --dry-run` OK, `cffconvert --validate` OK.

## Ubicación de artefactos

- `PUBLICATION_READINESS.md` — auditoría completa, blockers y decisiones.
- `paper/softwarex/metadata_table.md` — Code Metadata Table con datos reales
  del repo (nota: usa el layout C1–C9 antiguo; la plantilla oficial 2026
  tiene C1–C8 — solo pide el enlace de GitHub, sin cápsula reproducible — y
  el manuscrito LaTeX sigue a la plantilla).
- `paper/softwarex/latex/` — **manuscrito LaTeX sobre la plantilla oficial**:
  `sycocode-softwarex.tex` (manuscrito), `sycocode-softwarex.pdf` (compilado,
  9 págs), `refs.bib` (generado desde las respuestas crudas de las APIs),
  `softwarex-osp-template.tex` (plantilla oficial intacta, referencia),
  `elsarticle.cls` + `elsarticle-num.bst` (Elsarticle Bundle oficial, CTAN).
  Compila con `latexmk -pdf sycocode-softwarex.tex`: 0 errores, 0 citas sin
  resolver, 0 "??"; warnings restantes justificados (4× hyperref por
  `\corref` dentro de `\author` — mecanismo de la propia plantilla, solo
  afecta al string de metadatos del PDF; 1× float `!h`→`!ht` del `[!h]` de
  la tabla del template, mantenido verbatim).
- `paper/softwarex/draft.md` — borrador OSP completo, **2.051 palabras** de
  cuerpo (límite orientativo 3.000; está deliberadamente sobrio, hay margen
  si el tutor quiere ampliar). Cada cifra lleva comentario HTML con su fuente
  en el repo. Ejemplos de la §3 ejecutados y verificados el 2026-07-19.
- `paper/softwarex/references_verification.md` — 8 referencias, todas
  verificadas API a API (5 Crossref + 3 DataCite/arXiv, con la nota
  metodológica de por qué los DOIs de arXiv no pueden estar en Crossref).
  Cero referencias inventadas; se descartaron las no verificables.
- Tag local `v1.0.0` (anotado). Recolocable antes del push definitivo:
  `git tag -f v1.0.0 <commit>`.

## Blockers / decisiones pendientes (de PUBLICATION_READINESS.md; ninguna ejecutada)

- ~~**D1 — Separación del dataset**~~ **RESUELTO (2026-07-19):** opción (a),
  el dataset se queda en el repo tal cual; ninguna reescritura de historial,
  ahora ni después (decisión del autor).
- ~~**D2 — Email Gmail personal**~~ **RESUELTO (2026-07-19):** opción (a),
  el email del commit raíz no se toca (decisión del autor).
- ~~**D3 — ¿10 u 11 modelos?**~~ **RESUELTO (2026-07-19):** el autor confirma
  **10 modelos**; el draft ya usaba 10.
- ~~**Nomenclatura BSG**~~ **RESUELTO (2026-07-19):** la memoria del TFG
  (glosario y capítulo experimental, `TFG_SycoCode/memory/sections/`) fija
  **"Bilingual Sycophancy Gap"** = FR*(ES) − FR*(EN) sobre las familias
  retenidas. Draft actualizado y README del repo armonizado en esta rama.

**Fuente autorizada para dudas de este tipo:** la memoria del TFG vive en
`/Users/jc/Documents/TFG_SycoCode/` (LaTeX EN en `memory/sections/`, ES en
`memory/es/sections/`; PDF `main_TFG_revised.pdf`). Tutor: Antonio García
Cabot; co-tutor: David de Fitero Domínguez (cabecera de `memory/main.tex`).

## Pasos que quedan (humanos)

1. ~~Decidir D1–D2~~ **hecho** — todas las decisiones (D1, D2, D3, BSG)
   están resueltas; ver arriba.
2. ~~Descargar la plantilla oficial y volcar el contenido~~ **hecho**
   (2026-07-19): `softwarex-osp-template.tex` descargada del fileshare de
   Elsevier, manuscrito completo en `paper/softwarex/latex/`, compilado y
   verificado. Quedan dentro del .tex los `\todo{}` de autoría/CRediT/
   agradecimientos y el ORCID.
   Requisitos de la plantilla a vigilar al enviar: el repo de GitHub debe
   ser **público** con README.md y **fichero de licencia** (la guía dice
   "Licence.txt"; el repo tiene `LICENSE` — probablemente valga, pero si el
   editorial se queja, añadir una copia como `License.txt`). Límite 4.000
   palabras (estamos en ~2.079) y máx. 6 figuras (llevamos 0 — el revisor
   hostil (informe C, O9) y la plantilla ("where possible") recomiendan
   añadir el diagrama TikZ del pipeline de la memoria como figura de
   arquitectura; decisión estética pendiente del autor. Opcional adicional
   del informe B: citar los precedentes cross-lingües Sattigeri/CLINIC en
   §1 exigiría verificar 2 DOIs nuevos — hoy se optó por "largely
   monolingual" sin refs nuevas).
3. **Enlace permanente (C2)**: cuando la liberación esté autorizada, archivar
   el tag `v1.0.0` (Zenodo con integración GitHub, o Software Heritage) y
   poner el DOI resultante en la tabla. *No hacerlo antes de la
   sincronización con el paper principal.*
4. ~~Email de soporte (C9)~~ **hecho** (jcnegrin2003@gmail.com; opcional:
   sustituir por el institucional UAH). ~~ORCID~~ **hecho** (2026-07-20):
   0009-0001-8892-2442 en la cabecera del .tex y en `CITATION.cff`.
5. **Cuenta en Editorial Manager** de SoftwareX (Elsevier) y alta del
   manuscrito.
6. **Cover letter** (breve: qué es el software, por qué encaja en SoftwareX,
   relación con el TFG y con el paper principal/Data in Brief en preparación).
7. **Confirmación del tutor** (Antonio García Cabot; co-tutor David de
   Fitero Domínguez): timing del envío (¿antes o después del paper
   principal?) y orden/lista de autoría (¿tutores como coautores o en
   agradecimientos?). Afiliación usada en el draft: Escuela Politécnica
   Superior, Universidad de Alcalá.
8. **Declaración de uso de IA generativa** según la política de Elsevier: el
   borrador fue redactado con asistencia de Claude (Anthropic) bajo
   supervisión del autor — hay que redactar la declaración en la sección
   correspondiente del manuscrito y repasarlo todo a mano antes de enviar.
9. Repaso final de los `[TODO]` restantes (email institucional sí/no,
   autoría/CRediT/agradecimientos) y pase de estilo manual del autor sobre
   el .tex — la corrección del 2026-07-20 fue quirúrgica, sin retoques de
   redacción.

## Estado de visibilidad (operaciones autorizadas el 2026-07-19)

| Repo | Visibilidad | GitHub Pages |
|---|---|---|
| `Darkrai500/SycoCode` | **PRIVATE** (antes público; 0 forks / 0 stars comprobados antes de privatizar) | No tiene (API 404) |
| `Darkrai500/TFG_SycoCode` | PRIVATE (ya lo era) | **Despublicado** (API 404; URL pública → HTTP 404). Rama `WebPage` y `/docs` intactas para republicar al liberar. |

⚠️ Consecuencia a revisar antes del envío: la landing
`https://darkrai500.github.io/TFG_SycoCode/` ahora devuelve 404, y la
referencian el badge/enlace "Project page" del `README.md` y el campo `url:`
de `CITATION.cff`. Si Pages se republica al liberar, no hay que tocar nada;
si no, cambiar ambos al enlace del repo.

## Qué NO se ha hecho (a propósito)

- Ningún push, ningún repo nuevo, nada a HF/Zenodo/PyPI.
- Ningún cambio de visibilidad fuera de los dos autorizados de la tabla.
- Ninguna reescritura de historial (D1/D2 cerradas como "no tocar").
- No se ha tocado el paper principal ni nada de Data in Brief.
