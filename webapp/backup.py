"""Consistent SQLite backup, including when the app is running. Never copy a live DB directly."""
import argparse
import os
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("destination", type=Path)
args = parser.parse_args()
if not args.source.is_file():
    parser.error("La base de datos origen no existe.")
args.destination.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(args.destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
try:
    with sqlite3.connect(args.source.resolve().as_uri()+"?mode=ro", uri=True) as source, sqlite3.connect(args.destination) as target:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("La copia no superó la verificación de integridad.")
except Exception:
    args.destination.unlink(missing_ok=True)
    raise
print(f"Copia consistente y verificada: {args.destination}")
