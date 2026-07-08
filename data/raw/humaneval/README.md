# humaneval — provenance

| Campo | Valor |
|---|---|
| **Nombre** | `humaneval` |
| **repo_id** | `openai/openai_humaneval` |
| **URL** | https://huggingface.co/datasets/openai/openai_humaneval |
| **Config** | `default` |
| **Revision (SHA)** | `7dce6050a7d6d172f3cc5c32aa97f52fa1a2e544` |
| **Fecha de descarga (UTC)** | `2026-05-13T18:03:18Z` |
| **Filas totales** | 164 |
| **SHA256 JSONL** | `f455980ba85d429c454f026216b8b87b6998e14784e6c3ee69c5df0abcecb495` |
| **Licencia** | MIT |
| **Cita** | Chen et al. 2021, arXiv:2107.03374 |

## Filas por split

| Split | Filas |
|---|---|
| test | 164 |
| **Total** | **164** |

## Reproducibilidad

Para descargar exactamente este snapshot:

```python
from datasets import load_dataset
ds = load_dataset("openai/openai_humaneval", name="default", revision="7dce6050a7d6d172f3cc5c32aa97f52fa1a2e544")
```

---

> **Nota:** Este fichero es inmutable. Toda transformación posterior se hace
> en `data/problems/` o derivados.
