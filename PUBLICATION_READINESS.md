# SycoCode — Auditoría de readiness para SoftwareX

**Fecha:** 2026-07-19 · **Rama:** `softwarex-prep` · **Commit auditado:** `3cf5d83` (main)
**Alcance:** solo el software (el dataset va por separado a Data in Brief).

---

## Veredicto: **GO (condicionado)**

No hay ningún blocker estructural que impida el artículo de SoftwareX. Hay
**3 roturas mecánicas** que impiden hoy que un desconocido reproduzca la
instalación/tests siguiendo el README — las tres tienen fix trivial y se
arreglan en Fase 2 sobre esta rama. Quedan **3 decisiones** que solo puedes
tomar tú (ninguna bloquea el envío del software si se decide "no hacer nada",
pero debes decidirlas conscientemente).

**Dato relevante descubierto durante la auditoría:** el repo
`Darkrai500/SycoCode` **ya es público** en GitHub (verificado vía
`gh repo view` → `visibility: PUBLIC`). El guardarraíl de "no hacer público
nada" se ha respetado (no he tocado visibilidad ni remotos), pero conviene que
sepas que el código y el dataset completo ya están expuestos; la
"sincronización de la liberación con el paper" aplica solo a lo nuevo (tag,
release, HF, Zenodo).

> **Actualización 2026-07-19 (posterior a la auditoría):** con autorización
> explícita del autor, `Darkrai500/SycoCode` se puso **PRIVADO** (0 forks /
> 0 stars comprobados antes de tocarlo) y el GitHub Pages de
> `Darkrai500/TFG_SycoCode` se **despublicó** (la rama `WebPage` y `/docs`
> quedan intactas; la URL pública devuelve 404). La liberación queda ahora
> genuinamente sincronizable con el envío del paper.

---

## Resumen por área

| # | Área | Estado | Nota |
|---|------|--------|------|
| 1 | Licencia | ✅ OK | MIT (código) + CC BY 4.0 (dataset) + Apache-2.0 upstream + THIRD_PARTY_NOTICES.md. MIT es OSI: cumple SoftwareX. |
| 2 | README | ✅ OK (2 gaps menores) | Setup, quickstart y reproducción e2e presentes. Falta: cómo ejecutar los tests; badge Python 3.11+ vs comentario "3.9+" en requirements-eval. |
| 3 | Dependencias | ❌ ROTO → fix mecánico | `requirements-data.txt` no instala (ni solo ni combinado): pin `click==8.1.8` incompatible con `typer==0.23.2` (exige `click>=8.2.1` en Python ≥3.10). Además `numpy` falta en `requirements-eval.txt` y el oráculo lo necesita. |
| 4 | Smoke test | ✅ PASA (tras fixes) | Ver evidencia abajo. `tests/test_vcr_panel.py` roto por desfase test↔producción (fix mecánico). |
| 5 | Secretos | ✅ LIMPIO | Historial completo (4 commits) escaneado: cero API keys, `.env` jamás commiteado. ⚠️ email Gmail personal como autor del commit raíz (decisión D2). |
| 6 | Higiene | ✅ OK | Sin junk trackeado, sin paths absolutos, .gitignore correcto (mejora menor: añadir `.pytest_cache/`). |
| 7 | Estructura | ✅ OK (decisión D1) | Separación clara código/datos/resultados. El dataset completo (~26 MB) vive en el repo — decidir si se separa para Data in Brief/HF. |
| 8 | CITATION / versionado | ❌ INVÁLIDO → fix mecánico | `CITATION.cff` no valida contra el esquema CFF 1.2.0 (`year` y `notes` no permitidos; `type: dataset` debería ser `software`; faltan `version` y `date-released`). Sin ningún tag. |

---

## Evidencia de la auditoría

**Instalación limpia (venv nuevo, Python 3.12.13):**
- `pip install -r requirements-eval.txt` → OK en solitario.
- `pip install -r requirements-data.txt` → **ResolutionImpossible**
  (`typer 0.23.2 depends on click>=8.2.1; python_version >= "3.10"` vs pin
  `click==8.1.8`). Falla también combinado. Un desconocido no puede seguir el
  README hoy.

**Test suite (scripts standalone, no pytest — `pytest tests/` recolecta 0 tests):**
- `tests/offline_selftest.py` → 40/41; el check `oracle: canonical passes`
  falla con `ModuleNotFoundError: No module named 'numpy'` (los harnesses de
  HumanEval+ usan numpy y no está en requirements-eval). **Con numpy: 41/41.**
- `tests/test_registry.py` 21/21 · `test_validate.py` 19/19 ·
  `test_vcr_harness.py` 18/18 · `test_verbal.py` 14/14.
- `tests/test_vcr_panel.py` → **KeyError**: el `FakeJudge` del test devuelve
  `{turn: verdict}` pero `eval/judge.py:334` desempaqueta `(verdicts, usage)`
  de `_PanelJudge.judge()` (`eval/judge.py:265-271`). El excepcionado se traga
  en `asyncio.gather(..., return_exceptions=True)` → "0 completed, 0 failed".
  Es el **test** el desactualizado, no producción (la campaña de 10 modelos
  corrió con este código).

**Smoke test del pipeline:**
- `python -m eval --dry-run` sin ninguna API key → OK: scope de 1.900 ítems,
  7 escenarios, EN/ES, 3.400 requests estimadas.
- Oráculo real (subprocess worker): la solución canónica de `cand_001` **pasa**
  sus tests ocultos y su bug inyectado b1 **falla** — ejecución de código real
  verificada.
- `offline_selftest.py` conduce cliente/retry/governor/records reales vía
  `httpx.MockTransport` (sin red). No hay `.env` local con claves, así que no
  se hizo run real contra API (el modo mock cubre el requisito).

**Secretos (working tree + historial completo, 4 commits):**
- Patrones específicos (`sk-or-v1-`, `sk-ant-`, `sk-proj-`, `AKIA…`, `ghp_`,
  `github_pat_`, `xox…`, `AIza…`, `csk-`) → 0 hits en todas las revisiones.
- Patrón genérico credencial (`api_key/token/bearer = <20+ chars>`) → 0 hits.
- `.env` nunca añadido en ningún commit; solo `.env.example` (sin valores).

**Higiene:**
- Nada de `__pycache__`/`.DS_Store`/`.pyc`/caches trackeado.
- Cero rutas absolutas (`/Users/…`, `/home/…`) en código/docs commiteados.
- `data/runs/*` gitignorado salvo `aggregates/` (los packs publicables) — correcto.

**Cifras del README verificadas contra los datos:**
- 50 problemas (`problems.jsonl`), 1.900 ítems (`items.jsonl`), 7 escenarios,
  320 filas de gold (`gold.jsonl`), 50 entradas en `bug_specs.json`,
  10 packs de modelo + master en `data/runs/aggregates/`.

---

## BLOCKERS mecánicos (los arreglo yo en Fase 2, en esta rama)

| ID | Qué | Fix |
|----|-----|-----|
| B1 | `requirements-data.txt` no instalable (click/typer) | Subir pin a `click==8.2.1` y verificar instalación limpia combinada. |
| B2 | Oráculo inutilizable en clon limpio (`numpy` ausente de `requirements-eval.txt`) | Añadir `numpy==2.0.2` (la versión ya pinneada en requirements-data) con comentario de por qué. |
| B3 | `tests/test_vcr_panel.py` roto (FakeJudge devuelve dict; producción devuelve tupla `(verdicts, usage)`) | Actualizar el mock: `return out, {}`. Re-ejecutar toda la suite. |
| B4 | `CITATION.cff` inválido (esquema CFF 1.2.0) | `year`→`date-released`, `notes`→`abstract`, `type: dataset`→`software`, añadir `version: 1.0.0`. Validar con `cffconvert --validate`. |

## Decisiones que requieren tu confirmación (NO ejecutadas)

| ID | Qué | Contexto | Opciones |
|----|-----|----------|----------|
| D1 | **Separación del dataset** | `data/` = 26 MB (raw 13 MB, problems 6,2 MB, goldset 5,5 MB) vive en el repo y ya estuvo en el historial público. | **RESUELTO (2026-07-19): opción (a)** — el dataset se queda en el repo tal cual. Ninguna reescritura de historial, ahora ni después (decisión del autor). |
| D2 | **Email personal en el historial** | El commit raíz `0690089` tiene autor `JC <jcnegrin2003@gmail.com>` (los otros 3 usan el noreply de GitHub). | **RESUELTO (2026-07-19): opción (a)** — no se toca (decisión del autor). |
| D3 | **10 vs 11 modelos** | Tu brief dice "11 modelos frontera"; el repo entero (README, comparativa v3, master.json, 10 packs — el slug `full` es gpt-oss-120b) dice **10**. | **RESUELTO (2026-07-19): son 10**, confirmado por el autor y coherente con la memoria del TFG ("nine of the ten models"). El draft usa 10. |

## NICE-TO-HAVE (los mecánicos también van en Fase 2)

- **N1** — README: sección breve "Running the tests" (los tests son scripts
  standalone; `pytest` recolecta 0 y confunde). *(lo arreglo)*
- **N2** — Armonizar versión de Python: badge dice 3.11+, el comentario de
  `requirements-eval.txt` dice 3.9+. Verificado funcionando en 3.12. *(lo arreglo: 3.11+)*
- **N3** — `.gitignore`: añadir `.pytest_cache/`. *(lo arreglo)*
- **N4** — Tag anotado `v1.0.0` local (sin push) al cierre de Fase 2; se puede
  recolocar con `git tag -f` antes del push definitivo. *(lo preparo)*
- **N5** — Sin empaquetado (`pyproject.toml`): SoftwareX no lo exige y el flujo
  actual (`python -m eval`, scripts) funciona; considerar solo si algún día va
  a PyPI. *(no lo toco)*
- **N6** — `docs/figures/` lleva 2,4 MB de PNGs generados; son referenciados por
  los docs de resultados, así que es razonable mantenerlos. *(no lo toco)*

## Qué he arreglado ya (Fase 2, aplicado y verificado en esta rama)

- **B1** `requirements-data.txt`: `click==8.1.8` → `click==8.2.1`.
- **B2** `requirements-eval.txt`: añadido `numpy==2.0.2` (con comentario del porqué).
- **B3** `tests/test_vcr_panel.py`: el `FakeJudge` devuelve ahora `(verdicts, usage)`.
- **B4** `CITATION.cff`: reescrito válido CFF 1.2.0 (`type: software`,
  `version: 1.0.0`, `date-released: 2026-07-08`, `abstract`, `keywords`,
  `repository-code`); `cffconvert --validate` → OK.
- **N1** README: sección "6. Offline test suite" (+ entrada en el TOC).
- **N2** Versión de Python armonizada a 3.11+ (header de requirements-eval).
- **N3** `.gitignore`: añadido `.pytest_cache/`.
- **N4** Tag anotado local `v1.0.0` (sin push; recolocable con `git tag -f`).

**Verificación post-fix (venv nuevo desde cero, Python 3.12.13):**
`pip install -r requirements-eval.txt -r requirements-data.txt` → OK;
los 6 scripts de test salen con exit 0; `python -m eval --dry-run` → OK
(1.900 ítems); `cffconvert --validate` → OK.

## Guardarraíles respetados

- Sin push a ningún remoto; sin cambios de visibilidad; sin servicios externos.
- Único acceso externo: lectura de metadatos del repo con `gh repo view`.
