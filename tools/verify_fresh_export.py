#!/usr/bin/env python3
"""Validate the committed parser from a clean, LF-preserving Git archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class FreshExportError(RuntimeError):
    """Raised when the committed fresh-export acceptance gate fails."""


def run_checked(command: Sequence[str], *, cwd: Path, label: str) -> dict[str, object]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        details = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        raise FreshExportError(f"{label} failed with exit code {completed.returncode}\n{details}")
    return {
        "label": label,
        "command": list(command),
        "exitCode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def create_fresh_export(repository: Path, destination: Path) -> Path:
    git = shutil.which("git")
    if git is None:
        raise FreshExportError("Git is required to build the fresh-export acceptance archive")
    archive_path = destination / "repository.tar"
    run_checked(
        [git, "-c", "core.autocrlf=false", "archive", "--format=tar", "HEAD", "-o", str(archive_path)],
        cwd=repository,
        label="git archive",
    )
    export_root = destination / "export"
    export_root.mkdir()
    with tarfile.open(archive_path, "r") as archive:
        try:
            archive.extractall(export_root, filter="data")
        except TypeError:  # Python < 3.12; the archive is locally produced from this repository.
            archive.extractall(export_root)
    return export_root


def verify_export(export_root: Path, python: str) -> dict[str, object]:
    checks = [
        run_checked(
            [python, "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=export_root,
            label="fresh-export full test suite",
        ),
        run_checked(
            [
                python,
                "-m",
                "unittest",
                "tests.test_package_only_runtime",
                "tests.test_runtime_raw_loader_guard",
                "-q",
            ],
            cwd=export_root,
            label="fresh-export package-only suite",
        ),
    ]
    scenario_code = """
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path('tools').resolve()))
from ti_parser_catalogs import RuntimeCatalogs
envelope = json.loads(Path('data/effect_catalog.json').read_text(encoding='utf-8'))
scenarios = envelope['supportedScenarios']
loaded = {}
for scenario in scenarios:
    catalogs = RuntimeCatalogs.load(scenario, Path('data'))
    loaded[scenario] = catalogs.calculation_diagnostics()['catalogBundleFingerprint']
print(json.dumps({'scenarios': loaded}, sort_keys=True))
""".strip()
    scenario_check = run_checked(
        [python, "-c", scenario_code],
        cwd=export_root,
        label="fresh-export supported scenario loads",
    )
    checks.append(scenario_check)
    scenario_result = json.loads(str(scenario_check["stdout"]))
    return {
        "status": "complete",
        "exportRoot": str(export_root),
        "checks": checks,
        "supportedScenarios": sorted(scenario_result["scenarios"]),
        "catalogBundleFingerprints": scenario_result["scenarios"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    repository = args.repository.resolve()
    try:
        with tempfile.TemporaryDirectory(prefix="ti-parser-fresh-export-") as temporary:
            export_root = create_fresh_export(repository, Path(temporary))
            result = verify_export(export_root, args.python)
        result["exportRoot"] = "<temporary directory removed>"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (FreshExportError, OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
