"""Descarga reproducible de los datasets fuente de SycoCode (Capa 0).

Para cada fuente se fija el commit SHA de HuggingFace en el momento de la
descarga, de modo que `python scripts/download_sources.py` siempre puede
reproducir el mismo snapshot si se pasa `--revision <sha>`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset
from huggingface_hub import dataset_info

# ---------------------------------------------------------------------------
# Definición de fuentes
# ---------------------------------------------------------------------------

SOURCES: list[dict[str, Any]] = [
    {
        "name": "humaneval",
        "repo_id": "openai/openai_humaneval",
        "config": None,
        "splits": ["test"],
        "out_dir": "data/raw/humaneval",
        "out_filename": "humaneval.jsonl",
        "license": "MIT",
        "citation": "Chen et al. 2021, arXiv:2107.03374",
    },
    {
        "name": "humanevalplus",
        "repo_id": "evalplus/humanevalplus",
        "config": None,
        "splits": None,  # auto-detectar todos los splits
        "out_dir": "data/raw/humanevalplus",
        "out_filename": "humanevalplus.jsonl",
        "license": "Apache-2.0",
        "citation": "Liu et al. 2023, NeurIPS 2023, arXiv:2305.01210",
    },
    {
        "name": "mbpp_sanitized",
        "repo_id": "google-research-datasets/mbpp",
        "config": "sanitized",
        "splits": None,  # auto-detectar todos los splits del config sanitized
        "out_dir": "data/raw/mbpp_sanitized",
        "out_filename": "mbpp_sanitized.jsonl",
        "license": "CC-BY-4.0",
        "citation": "Austin et al. 2021, arXiv:2108.07732",
    },
    {
        # MBPP+ (EvalPlus): strong differential oracle for the MBPP problems.
        # Distributed as a gzipped JSONL GitHub release asset, not a HF dataset.
        "name": "mbppplus",
        "source_type": "github_release",
        "release_url": "https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus.jsonl.gz",
        "version": "v0.2.0",
        "repo_id": "evalplus/mbppplus_release",
        "out_dir": "data/raw/mbppplus",
        "out_filename": "mbppplus.jsonl",
        "license": "Apache-2.0",
        "citation": "Liu et al. 2023, NeurIPS 2023, arXiv:2305.01210 (EvalPlus MBPP+)",
    },
]

# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _get_revision(repo_id: str) -> str:
    """Devuelve el commit SHA completo del branch `main` del dataset."""
    info = dataset_info(repo_id)
    sha: str = info.sha  # type: ignore[attr-defined]
    return sha


def _sha256_file(path: Path) -> str:
    """Calcula el SHA256 de un fichero en disco."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_readme(
    out_dir: Path,
    source: dict[str, Any],
    revision: str,
    split_counts: dict[str, int],
    total_rows: int,
    sha256: str,
    downloaded_at: str,
) -> None:
    """Escribe el README.md de provenance para una fuente."""
    repo_id: str = source["repo_id"]
    config_label = source["config"] if source["config"] else "default"
    url = f"https://huggingface.co/datasets/{repo_id}"

    rows_table = "\n".join(
        f"| {split} | {count} |" for split, count in split_counts.items()
    )

    content = f"""# {source['name']} — provenance

| Campo | Valor |
|---|---|
| **Nombre** | `{source['name']}` |
| **repo_id** | `{repo_id}` |
| **URL** | {url} |
| **Config** | `{config_label}` |
| **Revision (SHA)** | `{revision}` |
| **Fecha de descarga (UTC)** | `{downloaded_at}` |
| **Filas totales** | {total_rows} |
| **SHA256 JSONL** | `{sha256}` |
| **Licencia** | {source['license']} |
| **Cita** | {source['citation']} |

## Filas por split

| Split | Filas |
|---|---|
{rows_table}
| **Total** | **{total_rows}** |

## Reproducibilidad

Para descargar exactamente este snapshot:

```python
from datasets import load_dataset
ds = load_dataset("{repo_id}", name="{config_label}", revision="{revision}")
```

---

> **Nota:** Este fichero es inmutable. Toda transformación posterior se hace
> en `data/problems/` o derivados.
"""
    (out_dir / "README.md").write_text(content, encoding="utf-8")


def _write_global_readme(
    raw_dir: Path,
    summaries: list[dict[str, Any]],
) -> None:
    """Escribe/sobrescribe data/raw/README.md con la tabla resumen."""
    rows = "\n".join(
        "| {name} | `{repo_id}` | `{rev7}` | {total_rows} | `{sha16}` | {license} |".format(
            name=s["name"],
            repo_id=s["repo_id"],
            rev7=s["revision"][:7],
            total_rows=s["total_rows"],
            sha16=s["sha256"][:16],
            license=s["license"],
        )
        for s in summaries
    )

    content = f"""# data/raw — snapshots inmutables de datasets fuente

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
{rows}

---

*Generado automáticamente por `scripts/download_sources.py`.*
"""
    (raw_dir / "README.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Descarga de una sola fuente
# ---------------------------------------------------------------------------

def _write_readme_release(
    out_dir: Path,
    source: dict[str, Any],
    total_rows: int,
    sha256: str,
    downloaded_at: str,
) -> None:
    """README de provenance para una fuente descargada de un GitHub release."""
    content = f"""# {source['name']} — provenance

| Campo | Valor |
|---|---|
| **Nombre** | `{source['name']}` |
| **Origen** | GitHub release `{source['version']}` de `{source['repo_id']}` |
| **URL** | {source['release_url']} |
| **Fecha de descarga (UTC)** | `{downloaded_at}` |
| **Filas totales** | {total_rows} |
| **SHA256 JSONL** | `{sha256}` |
| **Licencia** | {source['license']} |
| **Cita** | {source['citation']} |

## Reproducibilidad

```bash
curl -sL {source['release_url']} | gunzip > {source['out_filename']}
```

---

> **Nota:** Este fichero es inmutable. EvalPlus MBPP+ aporta el oráculo fuerte
> (`base_input` + `plus_input` + `canonical_solution` + `contract`) para los
> problemas MBPP, frente a los ~3 asserts de `mbpp_sanitized`.
"""
    (out_dir / "README.md").write_text(content, encoding="utf-8")


def _download_github_release(source: dict[str, Any]) -> dict[str, Any] | None:
    """Descarga un asset .jsonl.gz de un GitHub release, lo descomprime y serializa."""
    name: str = source["name"]
    url: str = source["release_url"]
    out_dir = REPO_ROOT / source["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / source["out_filename"]

    print(f"[{name}] Descargando release {source['version']} desde {url}")
    try:
        with urllib.request.urlopen(url) as resp:  # noqa: S310 (URL fija de confianza)
            payload = gzip.decompress(resp.read())
    except Exception as exc:
        print(f"[{name}] ERROR al descargar release: {exc}")
        return None

    out_path.write_bytes(payload)
    total_rows = sum(1 for line in payload.decode("utf-8").splitlines() if line.strip())
    sha256 = _sha256_file(out_path)
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[{name}] Total: {total_rows} filas | SHA256: {sha256[:16]}...")
    _write_readme_release(out_dir, source, total_rows, sha256, downloaded_at)

    return {
        "name": name,
        "repo_id": source["repo_id"],
        "revision": source["version"],
        "total_rows": total_rows,
        "sha256": sha256,
        "license": source["license"],
    }


def download_source(source: dict[str, Any]) -> dict[str, Any] | None:
    """Descarga una fuente, serializa a JSONL y genera el README de provenance.

    Devuelve un dict resumen o None si falla.
    """
    if source.get("source_type", "hf") == "github_release":
        return _download_github_release(source)

    name: str = source["name"]
    repo_id: str = source["repo_id"]
    config: str | None = source["config"]
    specified_splits: list[str] | None = source["splits"]
    out_dir = REPO_ROOT / source["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / source["out_filename"]

    print(f"[{name}] Obteniendo revision SHA de '{repo_id}'...")
    try:
        revision = _get_revision(repo_id)
    except Exception as exc:
        print(f"[{name}] ERROR al obtener revision: {exc}")
        return None
    print(f"[{name}] Revision: {revision[:7]}... ({revision})")

    print(f"[{name}] Descargando dataset (revision={revision[:7]})...")
    try:
        ds = load_dataset(repo_id, name=config, revision=revision)
    except Exception as exc:
        print(f"[{name}] ERROR al descargar dataset: {exc}")
        return None

    # Determinar qué splits iterar
    if specified_splits is not None:
        splits_to_use = specified_splits
    else:
        splits_to_use = list(ds.keys())  # type: ignore[attr-defined]
    print(f"[{name}] Splits a serializar: {splits_to_use}")

    # Serializar a JSONL con campo __split__
    split_counts: dict[str, int] = {}
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with out_path.open("w", encoding="utf-8") as fh:
        for split_name in splits_to_use:
            try:
                split_ds = ds[split_name]  # type: ignore[index]
            except KeyError:
                print(f"[{name}] WARNING: split '{split_name}' no encontrado, omitiendo.")
                continue
            count = 0
            for record in split_ds:
                row: dict[str, Any] = dict(record)  # type: ignore[arg-type]
                row["__split__"] = split_name
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
            split_counts[split_name] = count
            print(f"[{name}]   split '{split_name}': {count} filas")

    total_rows = sum(split_counts.values())
    sha256 = _sha256_file(out_path)

    print(f"[{name}] Total: {total_rows} filas | SHA256: {sha256[:16]}...")
    print(f"[{name}] Escribiendo README.md de provenance...")

    _write_readme(
        out_dir=out_dir,
        source=source,
        revision=revision,
        split_counts=split_counts,
        total_rows=total_rows,
        sha256=sha256,
        downloaded_at=downloaded_at,
    )

    return {
        "name": name,
        "repo_id": repo_id,
        "revision": revision,
        "total_rows": total_rows,
        "sha256": sha256,
        "license": source["license"],
    }


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    """Descarga todos los datasets fuente y genera los READMEs de provenance."""
    raw_dir = REPO_ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    failed: list[str] = []

    for source in SOURCES:
        print(f"\n{'='*60}")
        print(f"Procesando: {source['name']}")
        print(f"{'='*60}")
        result = download_source(source)
        if result is None:
            failed.append(source["name"])
        else:
            summaries.append(result)

    print(f"\n{'='*60}")
    print("Generando data/raw/README.md global...")
    if summaries:
        _write_global_readme(raw_dir, summaries)

    print("\n--- RESUMEN FINAL ---")
    for s in summaries:
        print(f"  OK  {s['name']:20s}  {s['total_rows']} filas  rev={s['revision'][:7]}")
    for f in failed:
        print(f"  FAIL {f}")

    if failed:
        print(f"\n{len(failed)} fuente(s) fallaron.")
        sys.exit(1)
    else:
        print(f"\nTodas las fuentes descargadas correctamente.")


if __name__ == "__main__":
    main()
