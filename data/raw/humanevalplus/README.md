# humanevalplus — provenance

| Campo | Valor |
|---|---|
| **Nombre** | `humanevalplus` |
| **repo_id** | `evalplus/humanevalplus` |
| **URL** | https://huggingface.co/datasets/evalplus/humanevalplus |
| **Config** | `default` |
| **Revision (SHA)** | `d32357cf319e50e9c8d8dab5ea876c72b0fd321b` |
| **Fecha de descarga (UTC)** | `2026-05-13T18:03:22Z` |
| **Filas totales** | 164 |
| **SHA256 JSONL** | `d1df5f798bda34218e7b8ea75af31ac837da27b8771f5c7ee80bf81193a4c881` |
| **Licencia** | Apache-2.0 |
| **Cita** | Liu et al. 2023, NeurIPS 2023, arXiv:2305.01210 |

## Filas por split

| Split | Filas |
|---|---|
| test | 164 |
| **Total** | **164** |

## Reproducibilidad

Para descargar exactamente este snapshot:

```python
from datasets import load_dataset
ds = load_dataset("evalplus/humanevalplus", name="default", revision="d32357cf319e50e9c8d8dab5ea876c72b0fd321b")
```

---

> **Nota:** Este fichero es inmutable. Toda transformación posterior se hace
> en `data/problems/` o derivados.
