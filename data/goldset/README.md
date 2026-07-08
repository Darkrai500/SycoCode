# VCR-2 — Gold set humano (selección de jueces, gate κ ≥ 0.6)

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
