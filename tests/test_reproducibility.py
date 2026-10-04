"""Negative checks for tampering, extra files and corrupt ledger relationships."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_replay_bundle import build, EVIDENCE
from verify_replay_bundle import PAYLOAD, validate_ledgers, verify_manifest


class BundleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix="sycocode-package-test-")
        cls.root = Path(cls.base.name).resolve()
        cls.zip = cls.root / "baseline.zip"
        build(ROOT, cls.zip)
        with zipfile.ZipFile(cls.zip) as archive:
            archive.extractall(cls.root / "original")
        cls.bundle = cls.root / "original/sycocode-replay"

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.root)
        self.copy = Path(self.temp.name).resolve() / "bundle"
        shutil.copytree(self.bundle, self.copy)

    def tearDown(self):
        self.temp.cleanup()

    def test_deterministic_zip_contains_only_allowlist(self):
        other = Path(self.temp.name) / "second.zip"
        build(ROOT, other)
        self.assertEqual(self.zip.read_bytes(), other.read_bytes())
        with zipfile.ZipFile(other) as archive:
            self.assertEqual(set(archive.namelist()), {"sycocode-replay/" + n for n in PAYLOAD | {"manifest.json"}})
        self.assertEqual(verify_manifest(self.copy)["files_checked"], len(PAYLOAD))

    def test_tampered_script_is_rejected_before_execution(self):
        script = self.copy / "scripts/revision_analysis.py"
        script.write_bytes(script.read_bytes() + b"\n# changed\n")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            verify_manifest(self.copy)

    def test_extra_private_file_is_rejected(self):
        (self.copy / ".env").write_text("EXAMPLE=synthetic\n")
        with self.assertRaisesRegex(ValueError, "unexpected or missing"):
            verify_manifest(self.copy)

    def test_manifest_cannot_omit_payload(self):
        path = self.copy / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"].pop()
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "allowlist"):
            verify_manifest(self.copy)

    def test_symlink_is_rejected(self):
        path = self.copy / "LICENSE.txt"
        path.unlink()
        path.symlink_to(self.bundle / "LICENSE.txt")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            verify_manifest(self.copy)

    def test_output_reuse_does_not_replace_existing_bytes(self):
        with self.assertRaisesRegex(ValueError, "new ZIP"):
            build(ROOT, self.zip)
        with zipfile.ZipFile(self.zip) as archive:
            self.assertIsNone(archive.testzip())

    def test_full_replay_keeps_bundle_unchanged_without_bytecode(self):
        out = Path(self.temp.name) / "replayed"
        result = subprocess.run([sys.executable, "-B", "-I",
                                 str(self.copy / "scripts/verify_replay_bundle.py"),
                                 "--out", str(out)], text=True, capture_output=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        validation = json.loads((out / "bundle_validation.json").read_text())
        self.assertTrue(validation["statistics_structured_equal"])
        self.assertTrue(validation["inputs_unchanged"])
        self.assertEqual(list(self.copy.rglob("__pycache__")), [])
        self.assertEqual(verify_manifest(self.copy)["files_checked"], len(PAYLOAD))

    def test_duplicate_conversation_even_with_correct_row_count(self):
        path = self.copy / "data/item_ledger.jsonl.gz"
        with gzip.open(path, "rt") as stream:
            lines = stream.readlines()
        lines[-1] = lines[0]
        with gzip.open(path, "wt") as stream:
            stream.writelines(lines)
        with self.assertRaisesRegex(ValueError, "duplicate conversation"):
            validate_ledgers(self.copy / "data")

    def test_turn_state_must_match_its_conversation(self):
        path = self.copy / "data/turn_ledger.jsonl.gz"
        with gzip.open(path, "rt") as stream:
            lines = stream.readlines()
        turn = json.loads(lines[0])
        turn["effective_pass"] = not turn["effective_pass"]
        lines[0] = json.dumps(turn) + "\n"
        with gzip.open(path, "wt") as stream:
            stream.writelines(lines)
        with self.assertRaisesRegex(ValueError, "effective state mismatch"):
            validate_ledgers(self.copy / "data")


if __name__ == "__main__":
    unittest.main()
