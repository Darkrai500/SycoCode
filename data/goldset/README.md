# VCR-2 — Referencia mixta humana/proxy (selección de jueces, gate κ ≥ 0.6)

## Estado del export conservado (auditado el 2026-09-16)

`gold.jsonl` y `gold_stats.json` contienen **320 unidades: 41 con origen
`human_jc` y 279 con origen `prelabel_proxy`**. No hay solapamiento entre
anotadores humanos (`inter_annotator.n_overlap=0`, κ no disponible). Por
tanto, el export no es un gold de 320 etiquetas humanas independientes.

Las decisiones de junio que siguen describen el protocolo previsto. La
regla «ninguna etiqueta es final sin commit humano» no se cumple en todo el
export conservado: `scripts/export_gold.py` permite completar unidades con
`--fill-from-prelabels`, y la procedencia del export registra ese resultado.
No se han cambiado las etiquetas durante esta auditoría.

La documentación histórica llama al preanotador `claude-fable-5`, mientras
que las 279 filas proxy identifican `opus-session`; `prelabel_v1_agent` es
una versión del prompt, no prueba de un modelo/API concreto. Se conserva
esta discrepancia sin atribuir un identificador histórico no demostrado.

**Sustituida en v1.1.0** por una referencia íntegramente humana sobre los
mismos 320 turnos (dos anotaciones humanas por turno y adjudicación de los
desacuerdos): ver [`data/reeval/`](../reeval/README.md). Este directorio se
conserva porque documenta la selección original del panel y contiene los
payloads y los votos de los jueces (`votes.jsonl`) que usa la nueva
evaluación.

Pipeline de usar-y-archivar. Formatos congelados: rúbrica `docs/vcr_rubric.md` v1.1,
gold `docs/vcr_contracts.md` Contrato 3, stripping D8 `eval/verbal.py` vía
`eval/vcr_protocols.reconstruct_blind`.

## Decisiones operativas (11/06/2026)

- **Marco**: `data/runs/full/responses.jsonl` (run completo gpt-oss-120b, 1.900).
  Pool = 5 escenarios de presión × 2 idiomas × 20 respuestas (semilla 20260611)
  → 200 respuestas / **320 turnos juzgados** (insistent aporta T2–T5).
- **Payloads ciegos re-renderizados** aquí (`payloads/g####.md`) con
  `reconstruct_blind(rec, judged_turns)` — los `vcr_tasks/` legacy renderizan un
  turno marcado por fichero y truncan los turnos intermedios del insistent.
- **Pre-etiquetas SIN API**: las genera `claude-fable-5` como agente de sesión
  (batch de grupos por prompt), no por API ni temperatura 0. Prompt versionado
  `prelabel_v1_agent`. `fable` sigue EXCLUIDO del pool de jueces (rubric §5.7,
  `eval/vcr_protocols.EXCLUDED_JUDGE_SUBSTRINGS`).
- **Etiqueta final = humana**: ninguna etiqueta es final sin commit ciego de JC
  en la app; la pre-etiqueta solo se revela tras el commit (label-then-reveal).
- **Segundo anotador**: pospuesto; la app lo soporta
  (`--annotator <id> --no-reveal`) y el export calcula κ ciego si aparece.

## Ficheros

| Fichero | Qué es |
|---|---|
| `pool_manifest.json` | semillas, SHA-256 del marco, estratos, orden de display |
| `pool.jsonl` | 1 fila/turno juzgado (unidad de anotación) |
| `payloads/g####.md` | payload ciego por respuesta (rúbrica + bug ancla + conversación verbal-only) |
| `prelabels_chunks/*.jsonl` | pre-etiquetas de Fable por lotes de agente |
| `annotations_jc.jsonl` | log de eventos append-only de la app (`blind_commit`, `override`) |
| `gold.jsonl` / `gold_stats.json` | export Contrato 3 + estadísticas de cierre |

## Uso

```bash
PYTHONPATH=. python3 scripts/build_gold_pool.py          # ya ejecutado (pool fijado)
PYTHONPATH=. python3 scripts/gold_annotator.py           # app en http://127.0.0.1:8765
#   --bind 0.0.0.0          → móvil en LAN
#   --prelabels data/goldset/prelabels_chunks            # acepta dir de chunks
PYTHONPATH=. python3 scripts/export_gold.py              # gold.jsonl + stats
```
