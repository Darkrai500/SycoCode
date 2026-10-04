#!/usr/bin/env python3
"""Build a deterministic, local-only tier-A replay ZIP from an explicit allowlist."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
from verify_replay_bundle import (DATA_FILES, PAYLOAD, checked_file, digest,
                                  require, validate_ledgers, verify_manifest)

EVIDENCE = "data/replay"
SOURCES = {
    "README.md": "docs/reproducibility/BUNDLE_README.md",
    "LICENSE.txt": "LICENSE.txt",
    "requirements.txt": "requirements-replay.lock",
    "PROVENANCE.json": "docs/reproducibility/import_provenance.json",
    **{name: name for name in PAYLOAD if name.startswith("scripts/")},
    **{"data/" + name: EVIDENCE + "/" + name for name in DATA_FILES},
}


def build(root, output):
    root = root.resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("output must be a new ZIP file")
    provenance = json.loads(checked_file(root, SOURCES["PROVENANCE.json"]).read_text())
    imported = {entry["path"]: entry for entry in provenance["files"]}
    for source in SOURCES.values():
        if source in imported:
            require(digest(checked_file(root, source)) == imported[source]["sha256"],
                    "imported input differs from its recorded provenance: " + source)
    coverage = validate_ledgers(root / EVIDENCE)
    with tempfile.TemporaryDirectory(prefix="sycocode-bundle-") as temp:
        stage = Path(temp).resolve() / "sycocode-replay"
        stage.mkdir()
        entries = []
        for dest, source in sorted(SOURCES.items()):
            src = checked_file(root, source)
            target = stage / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            entries.append({"path": dest, "bytes": target.stat().st_size, "sha256": digest(target)})
        manifest = {"schema_version": 1, "tier": "A: arithmetic from historical derived ledgers",
                    "release_status": "distributed with SycoCode v1.1.0",
                    "coverage": coverage, "files": entries}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        verify_manifest(stage)
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(p for p in stage.rglob("*") if p.is_file()):
                member = zipfile.ZipInfo("sycocode-replay/" + path.relative_to(stage).as_posix(), (1980, 1, 1, 0, 0, 0))
                member.create_system = 3
                member.external_attr = 0o100644 << 16
                member.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(member, path.read_bytes(), compresslevel=9)
    return {"sha256": digest(output), "bytes": output.stat().st_size,
            "payload_files": len(entries), "coverage": coverage}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.root, args.out), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(1, f"bundle build failed: {exc}\n")


if __name__ == "__main__":
    main()
