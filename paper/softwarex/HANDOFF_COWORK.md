# HANDOFF — Preparación SoftwareX (estado a 2026-07-19)

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
  del repo; TODOs marcados: C2 (enlace permanente archivado), C3 (cápsula
  reproducible, opcional), C9 (email de soporte).
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

- **D1 — Separación del dataset** (26 MB en repo e historial ya público).
  Recomendación: dejarlo tal cual para SoftwareX; decidir en el flujo de
  Data in Brief.
- **D2 — Email Gmail personal** como autor del commit raíz `0690089`.
  Recomendación: no reescribir historial.
- **D3 — ¿10 u 11 modelos?** El repo entero dice **10** (el slug `full` es
  gpt-oss-120b); tu brief decía 11. El draft usa 10. Si son 11, indicar cuál
  falta y de dónde salen sus números.
- **Nomenclatura BSG**: tu brief dice "Bilingual Sycophancy Gap"; el README
  dice "bilingual susceptibility gap". El draft sigue al README (verificable).
  Unificar antes del envío (y en el paper principal).

## Pasos que quedan (humanos)

1. **Decidir D1–D3** y la nomenclatura BSG.
2. **Descargar la plantilla oficial de SoftwareX** (LaTeX/Word) desde la
   página de la revista en Elsevier ("Guide for Authors" → template del
   formato Original Software Publication) y volcar `draft.md` +
   `metadata_table.md` a ella.
3. **Enlace permanente (C2)**: cuando la liberación esté autorizada, archivar
   el tag `v1.0.0` (Zenodo con integración GitHub, o Software Heritage) y
   poner el DOI resultante en la tabla. *No hacerlo antes de la
   sincronización con el paper principal.*
4. **Email de soporte (C9)** y ORCID del autor.
5. **Cuenta en Editorial Manager** de SoftwareX (Elsevier) y alta del
   manuscrito.
6. **Cover letter** (breve: qué es el software, por qué encaja en SoftwareX,
   relación con el TFG y con el paper principal/Data in Brief en preparación).
7. **Confirmación del tutor**: timing del envío (¿antes o después del paper
   principal?), orden/lista de autoría (¿va el tutor como coautor?), y
   afiliación exacta.
8. **Declaración de uso de IA generativa** según la política de Elsevier: el
   borrador fue redactado con asistencia de Claude (Anthropic) bajo
   supervisión del autor — hay que redactar la declaración en la sección
   correspondiente del manuscrito y repasarlo todo a mano antes de enviar.
9. Repaso final de los `[TODO]` restantes en `draft.md` (email/ORCID en la
   cabecera, agradecimientos).

## Qué NO se ha hecho (a propósito)

- Ningún push, ningún repo nuevo, nada a HF/Zenodo/PyPI, sin tocar visibilidad.
- Las decisiones D1–D3 no se han ejecutado.
- No se ha tocado el paper principal ni nada de Data in Brief.
