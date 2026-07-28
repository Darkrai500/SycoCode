# Code Metadata Table — SycoCode (SoftwareX Original Software Publication)

Datos extraídos del repo en la rama `softwarex-prep` (base v1.0, commit
`4050b9b`; fixes de publicación en `f367fb4`; tag local `v1.0.0`).

| Nr | Code metadata description | Value |
|----|---------------------------|-------|
| C1 | Current code version | v1.0.0 <!-- tag anotado local; ver git tag --> |
| C2 | Permanent link to code/repository used for this code version | https://github.com/Darkrai500/SycoCode — **[TODO** al liberar: snapshot archivado con DOI (Zenodo o Software Heritage) apuntando al tag v1.0.0; SoftwareX pide enlace permanente**]** |
| C3 | Permanent link to Reproducible Capsule | **[TODO** — opcional; si se quiere, un Code Ocean capsule con el flujo offline (tests + dry-run + oráculo), que no necesita API keys**]** |
| C4 | Legal Code License | MIT (código: `eval/`, `scripts/`, `tests/` — `LICENSE`). Material original del dataset: CC BY 4.0 (`LICENSE-DATASET`). Material upstream conserva su licencia: HumanEval MIT, HumanEval+/MBPP+ Apache-2.0, MBPP CC BY 4.0 (`THIRD_PARTY_NOTICES.md`, `LICENSE-APACHE`). <!-- verificado: los 4 ficheros de licencia existen en el repo --> |
| C5 | Code versioning system used | git |
| C6 | Software code languages, tools, and services used | Python ≥ 3.11 (≈9.900 líneas: `eval/` 4.171, `scripts/` 4.862, `tests/` 907 <!-- wc -l -->); JavaScript (2 utilidades de anotación: `scripts/vcr_human_annotation.js`, `scripts/vcr_reannotate_missing.js`); HTML (`scripts/panel.html`). Servicios (solo en runs con API): endpoints OpenAI-compatibles — OpenRouter, Cerebras (W&B Inference también soportado; la campaña usó 9×OpenRouter + 1×Cerebras, `config/models.json`). JSON Schema para los contratos de datos (`schema/`). |
| C7 | Compilation requirements, operating environments & dependencies | Sin compilación (Python puro). SO: probado en macOS (Apple Silicon) y Linux (x86-64) <!-- macOS: suite completa, 6 scripts / 127 checks / exit 0, en macOS 26.5.2 arm64 con Python 3.12.13, 2026-07-28. Linux: la campaña de 10 modelos corrió en un VPS dockerizado x86-64, README §Engineering notes. Windows: sin evidencia en el repo, no se declara -->. Dependencias pinneadas: runner+oráculo+juez → `requirements-eval.txt` (httpx 0.28.1, rich 15.0.0, openpyxl 3.1.5, numpy 2.0.2); reconstrucción del dataset → `requirements-data.txt` (datasets 4.5.0, pandas 2.3.3, pyarrow 21.0.0, …). Instalación limpia verificada en venv nuevo con Python 3.12.13 <!-- verificación Fase 2, 2026-07-19 -->. Los tests y el dry-run corren 100% offline; los runs de evaluación reales requieren API keys vía `.env`. |
| C8 | If available, link to developer documentation/manual | `README.md` (instalación, quickstart, reproducción end-to-end), `eval/README.md` (runner), `docs/methodology/` (diseño del dataset, rúbrica y contratos VCR, esquema de evaluación, runbooks), `DATASHEET.md` (datasheet del dataset). |
| C9 | Support email for questions | jcnegrin2003@gmail.com <!-- confirmado por el autor 2026-07-19; opcionalmente sustituir por el institucional UAH --> |
