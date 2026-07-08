# data/raw — snapshots inmutables de datasets fuente

## Política

Esta carpeta contiene **únicamente snapshots de sólo lectura** de los benchmarks
de programación originales. **No editar ningún fichero aquí directamente.**
Toda transformación (selección de problemas, inyección de bugs, etc.) se realiza
a partir de estos ficheros en las carpetas `data/problems/` y derivadas.

## Reproducir la descarga

```bash
python scripts/download_sources.py
```

## Resumen de fuentes

| Nombre | repo_id | Revision (7c) | Filas | SHA256 (16c) | Licencia |
|---|---|---|---|---|---|
| humaneval | `openai/openai_humaneval` | `7dce605` | 164 | `f455980ba85d429c` | MIT |
| humanevalplus | `evalplus/humanevalplus` | `d32357c` | 164 | `d1df5f798bda3421` | Apache-2.0 |
| mbpp_sanitized | `google-research-datasets/mbpp` | `4bb6404` | 427 | `a91bc782a6b2cdcc` | CC-BY-4.0 |
| mbppplus | `evalplus/mbppplus_release` (release `v0.2.0`, `MbppPlus.jsonl.gz`) | `v0.2.0` | 378 | `b54e762755248ca4` | Apache-2.0 |

MBPP+ (EvalPlus) aporta el **oráculo fuerte** para los 10 problemas MBPP: ~100+ casos
por problema (`base_input` + `plus_input` + `canonical_solution` + `contract`), frente a
los ~3 asserts de `mbpp_sanitized`. Cubre 9 de nuestros 10 (falta `Mbpp/802`). Descargado
a mano desde el release de GitHub; falta añadirlo a `scripts/download_sources.py`.

---

*Generado automáticamente por `scripts/download_sources.py`* (salvo la fila `mbppplus`, añadida a mano).
