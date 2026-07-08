# mbpp_sanitized — provenance

| Campo | Valor |
|---|---|
| **Nombre** | `mbpp_sanitized` |
| **repo_id** | `google-research-datasets/mbpp` |
| **URL** | https://huggingface.co/datasets/google-research-datasets/mbpp |
| **Config** | `sanitized` |
| **Revision (SHA)** | `4bb6404fdc6cacfda99d4ac4205087b89d32030c` |
| **Fecha de descarga (UTC)** | `2026-05-13T18:03:25Z` |
| **Filas totales** | 427 |
| **SHA256 JSONL** | `a91bc782a6b2cdcc8b337cf9c3d2b9aa031360b5aa006b9248913595dd8544fd` |
| **Licencia** | CC-BY-4.0 |
| **Cita** | Austin et al. 2021, arXiv:2108.07732 |

## Filas por split

| Split | Filas |
|---|---|
| train | 120 |
| test | 257 |
| validation | 43 |
| prompt | 7 |
| **Total** | **427** |

## Reproducibilidad

Para descargar exactamente este snapshot:

```python
from datasets import load_dataset
ds = load_dataset("google-research-datasets/mbpp", name="sanitized", revision="4bb6404fdc6cacfda99d4ac4205087b89d32030c")
```

---

> **Nota:** Este fichero es inmutable. Toda transformación posterior se hace
> en `data/problems/` o derivados.
