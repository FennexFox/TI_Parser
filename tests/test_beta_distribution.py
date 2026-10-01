from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_beta_distribution import (  # noqa: E402
    MANIFEST_PATH,
    RUNTIME_DATA,
    BetaDistributionError,
    build_beta_distribution,
)


class BetaDistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self._git("init", "-q")
        self._git("config", "user.name", "Distribution Test")
        self._git("config", "user.email", "distribution@example.invalid")
        self._write_fixture()
        self.first_commit = self._commit("initial")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, *arguments: str) -> str:
        environment = dict(os.environ)
        environment.update(
            {
                "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
                "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
            }
        )
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            self.fail(completed.stderr)
        return completed.stdout.strip()

    def _write(self, path: str, content: str) -> None:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")

    def _write_fixture(self) -> None:
        self._write("README.md", "# Synthetic parser\n")
        self._write("LICENSE", "Synthetic license\n")
        self._write("docs/QUICKSTART_KO.md", "# Quickstart\n")
        self._write("docs/BETA_DATA_NOTICE.md", "# Data notice\n")
        self._write("docs/CHATGPT_START.md", "# ChatGPT start\n")
        self._write("tools/ti_save_parser.py", "print('entrypoint')\n")
        self._write("tools/ti_parser_core.py", "VALUE = 'first'\n")
        self._write("tools/ti_parser_version.py", "__version__ = '0.1.0b1'\n")
        self._write("tools/build_beta_distribution.py", "# developer tool\n")
        self._write("tools/standalone_catalog_integrity.py", "# runtime integrity helper\n")
        self._write("tools/catalog_utils.py", "# generator helper\n")
        self._write(
            "data/catalog_manifest.json",
            json.dumps({"catalogs": {"effect_catalog.json": {"sha256": "synthetic"}}}) + "\n",
        )
        for name in RUNTIME_DATA - {"catalog_manifest.json"}:
            self._write(f"data/{name}", "{}\n")
        self._write("data/effect_catalog.json", '{"effect": 1}\n')
        self._write("data/future_compatibility.json", '{"gameVersion": "future"}\n')
        self._write(".agents/skills/ti-save-analysis/SKILL.md", "# Skill\n")
        self._write(".agents/skills/ti-save-analysis/scripts/helper.py", "VALUE = 1\n")
        self._write("tests/test_private.py", "SECRET = 'excluded'\n")
        self._write("dev-docs/internal.md", "private\n")
        self._write("private-save.gz", "not really a save\n")

    def _commit(self, message: str) -> str:
        self._git("add", ".")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD")

    def test_archive_is_deterministic_allowlisted_and_hashed(self) -> None:
        first = self.root / "first.zip"
        second = self.root / "second.zip"

        result = build_beta_distribution(self.root, first)
        build_beta_distribution(self.root, second)

        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(result["version"], "0.1.0b1")
        self.assertEqual(result["sourceCommit"], self.first_commit)
        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertNotIn("data/future_compatibility.json", names)
            self.assertIn(".agents/skills/ti-save-analysis/scripts/helper.py", names)
            self.assertNotIn("tools/build_beta_distribution.py", names)
            self.assertNotIn("tools/catalog_utils.py", names)
            self.assertNotIn("tests/test_private.py", names)
            self.assertNotIn("dev-docs/internal.md", names)
            self.assertNotIn("private-save.gz", names)
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)
            manifest = json.loads(archive.read(MANIFEST_PATH))
            self.assertEqual(manifest["version"], "0.1.0b1")
            self.assertEqual(manifest["sourceCommit"], self.first_commit)
            self.assertNotIn(MANIFEST_PATH, manifest["files"])
            self.assertEqual(set(manifest["files"]), set(names) - {MANIFEST_PATH})
            for path, metadata in manifest["files"].items():
                self.assertEqual(metadata["sha256"], hashlib.sha256(archive.read(path)).hexdigest())

    def test_ref_uses_committed_bytes_and_changes_change_archive(self) -> None:
        self._write("tools/ti_parser_core.py", "VALUE = 'second'\n")
        second_commit = self._commit("change runtime")
        self._write("tools/ti_parser_core.py", "VALUE = 'uncommitted'\n")

        old_archive = self.root / "old.zip"
        new_archive = self.root / "new.zip"
        old_result = build_beta_distribution(self.root, old_archive, ref=self.first_commit)
        new_result = build_beta_distribution(self.root, new_archive, ref="HEAD")

        self.assertNotEqual(old_archive.read_bytes(), new_archive.read_bytes())
        self.assertEqual(old_result["sourceCommit"], self.first_commit)
        self.assertEqual(new_result["sourceCommit"], second_commit)
        with zipfile.ZipFile(old_archive) as archive:
            self.assertEqual(archive.read("tools/ti_parser_core.py"), b"VALUE = 'first'\n")
        with zipfile.ZipFile(new_archive) as archive:
            self.assertEqual(archive.read("tools/ti_parser_core.py"), b"VALUE = 'second'\n")

    def test_missing_required_document_fails(self) -> None:
        (self.root / "docs/CHATGPT_START.md").unlink()
        self._git("add", "-u")
        self._git("commit", "-q", "-m", "remove required doc")

        with self.assertRaisesRegex(BetaDistributionError, "docs/CHATGPT_START.md"):
            build_beta_distribution(self.root, self.root / "missing.zip")

    def test_missing_catalog_listed_by_manifest_fails(self) -> None:
        self._write(
            "data/catalog_manifest.json",
            json.dumps({"catalogs": {"missing_catalog.json": {"sha256": "synthetic"}}}) + "\n",
        )
        self._commit("refer to missing catalog")

        with self.assertRaisesRegex(BetaDistributionError, "data/missing_catalog.json"):
            build_beta_distribution(self.root, self.root / "missing-catalog.zip")

    def test_refuses_to_overwrite_tracked_source_path(self) -> None:
        original = (self.root / "README.md").read_bytes()
        with self.assertRaisesRegex(BetaDistributionError, "tracked source path"):
            build_beta_distribution(self.root, self.root / "README.md")
        self.assertEqual((self.root / "README.md").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
