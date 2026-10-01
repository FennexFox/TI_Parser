#!/usr/bin/env python3
"""Build a deterministic TI_Parser beta ZIP from tracked Git bytes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Mapping, Sequence
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "beta_manifest.json"
STABLE_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
RUNTIME_DATA = frozenset({
    "catalog_manifest.json", "compatibility_registry.json", "effect_catalog.json",
    "trait_catalog.json", "org_catalog.json", "research_catalog.json", "ship_catalog.json",
    "nation_claim_catalog.json", "nation_development_catalog.json", "module_catalog.json", "location_catalog.json",
})
REQUIRED_PATHS = frozenset(
    {
        "README.md",
        "LICENSE",
        "docs/QUICKSTART_KO.md",
        "docs/BETA_DATA_NOTICE.md",
        "docs/CHATGPT_START.md",
        "docs/MCP_SETUP.md",
        "requirements-mcp.txt",
        "tools/ti_parser_mcp.py",
        "tools/ti_save_parser.py",
        "tools/ti_parser_version.py",
        "tools/standalone_catalog_integrity.py",
        "data/catalog_manifest.json",
        ".agents/skills/ti-save-analysis/SKILL.md",
    }
)


class BetaDistributionError(RuntimeError):
    """Raised when a safe, complete beta archive cannot be built."""


def _run_git(repository: Path, arguments: Sequence[str]) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise BetaDistributionError("Git is required to build the beta distribution")
    completed = subprocess.run(
        [git, *arguments],
        cwd=repository,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        details = completed.stderr.decode("utf-8", errors="replace").strip()
        raise BetaDistributionError(details or f"git {' '.join(arguments)} failed")
    return completed.stdout


def _repository_root(repository: Path) -> Path:
    root = _run_git(repository, ["rev-parse", "--show-toplevel"])
    return Path(root.decode("utf-8", errors="strict").strip()).resolve()


def _resolve_commit(repository: Path, ref: str) -> str:
    output = _run_git(
        repository,
        ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
    )
    commit = output.decode("ascii", errors="strict").strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise BetaDistributionError(f"Git returned an invalid commit ID for {ref!r}")
    return commit


def _tracked_paths(repository: Path, commit: str) -> list[str]:
    output = _run_git(
        repository,
        ["-c", "core.quotepath=false", "ls-tree", "-r", "-z", "--name-only", commit],
    )
    return sorted(
        item.decode("utf-8", errors="strict")
        for item in output.split(b"\0")
        if item
    )


def _read_blob(repository: Path, commit: str, path: str) -> bytes:
    return _run_git(repository, ["cat-file", "blob", f"{commit}:{path}"])


def _is_distribution_path(path: str) -> bool:
    pure_path = PurePosixPath(path)
    if path in {"README.md", "LICENSE"}:
        return True
    if path in {
        "docs/QUICKSTART_KO.md",
        "docs/BETA_DATA_NOTICE.md",
        "docs/CHATGPT_START.md",
        "docs/MCP_SETUP.md",
    }:
        return True
    if path == "requirements-mcp.txt":
        return True
    if pure_path.parent == PurePosixPath("data"):
        return pure_path.name in RUNTIME_DATA
    if pure_path.parent == PurePosixPath("tools"):
        return pure_path.suffix == ".py" and (
            pure_path.name.startswith("ti_parser_") or pure_path.name in {"ti_save_parser.py", "standalone_catalog_integrity.py"}
        )
    return path.startswith(".agents/skills/ti-save-analysis/")


def _version_from_source(source: bytes) -> str:
    try:
        module = ast.parse(source.decode("utf-8"), filename="tools/ti_parser_version.py")
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise BetaDistributionError(f"Cannot parse distribution version: {exc}") from exc
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value = statement.value
        if (
            any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value
        ):
            return value.value
    raise BetaDistributionError("tools/ti_parser_version.py must define a non-empty string __version__")


def _required_catalog_paths(catalog_manifest: bytes) -> set[str]:
    try:
        manifest = json.loads(catalog_manifest)
        catalogs = manifest["catalogs"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise BetaDistributionError(f"data/catalog_manifest.json is invalid: {exc}") from exc
    if not isinstance(catalogs, dict):
        raise BetaDistributionError("data/catalog_manifest.json field 'catalogs' must be an object")
    required: set[str] = set()
    for name in catalogs:
        if not isinstance(name, str) or PurePosixPath(name).name != name or not name.endswith(".json"):
            raise BetaDistributionError(f"Invalid catalog filename in catalog manifest: {name!r}")
        required.add(f"data/{name}")
    return required


def _protect_tracked_output(
    repository: Path,
    output: Path,
    commit_paths: set[str],
) -> None:
    try:
        relative = output.resolve().relative_to(repository).as_posix()
    except ValueError:
        return
    index_paths = {
        item.decode("utf-8", errors="strict")
        for item in _run_git(repository, ["-c", "core.quotepath=false", "ls-files", "-z"]).split(b"\0")
        if item
    }
    if relative in commit_paths or relative in index_paths:
        raise BetaDistributionError(f"Refusing to overwrite tracked source path: {relative}")


def _manifest_bytes(version: str, commit: str, files: Mapping[str, bytes]) -> bytes:
    manifest = {
        "schemaVersion": 1,
        "version": version,
        "sourceCommit": commit,
        "files": {
            path: {"sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(files.items())
        },
    }
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, STABLE_ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o100644 & 0xFFFF) << 16
    info.flag_bits |= 0x800
    return info


def build_beta_distribution(
    repository: Path,
    output: Path | None = None,
    *,
    ref: str = "HEAD",
) -> dict[str, object]:
    """Build a deterministic archive and return its release metadata."""

    root = _repository_root(repository.resolve())
    commit = _resolve_commit(root, ref)
    all_paths = _tracked_paths(root, commit)
    all_path_set = set(all_paths)
    missing = sorted((REQUIRED_PATHS | {f"data/{name}" for name in RUNTIME_DATA}) - all_path_set)
    if missing:
        raise BetaDistributionError(f"Required distribution files are missing: {', '.join(missing)}")

    catalog_manifest = _read_blob(root, commit, "data/catalog_manifest.json")
    missing_catalogs = sorted(_required_catalog_paths(catalog_manifest) - all_path_set)
    if missing_catalogs:
        raise BetaDistributionError(
            f"Runtime catalogs listed by data/catalog_manifest.json are missing: {', '.join(missing_catalogs)}"
        )

    selected = [path for path in all_paths if _is_distribution_path(path)]
    omitted_catalogs = sorted(_required_catalog_paths(catalog_manifest) - set(selected))
    if omitted_catalogs:
        raise BetaDistributionError(f"Runtime catalogs excluded by allowlist: {', '.join(omitted_catalogs)}")
    files = {path: _read_blob(root, commit, path) for path in selected}
    version = _version_from_source(files["tools/ti_parser_version.py"])
    destination = (
        output.resolve()
        if output is not None
        else (root / "dist" / f"TI_Parser-{version}.zip").resolve()
    )
    _protect_tracked_output(root, destination, all_path_set)
    destination.parent.mkdir(parents=True, exist_ok=True)

    archive_files = dict(files)
    archive_files[MANIFEST_PATH] = _manifest_bytes(version, commit, files)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
        with zipfile.ZipFile(temporary_name, "w") as archive:
            for path in sorted(archive_files):
                archive.writestr(
                    _zip_info(path),
                    archive_files[path],
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

    return {
        "status": "complete",
        "output": str(destination),
        "version": version,
        "sourceCommit": commit,
        "fileCount": len(archive_files),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--ref", default="HEAD", help="Git commit-ish to package (default: HEAD)")
    parser.add_argument("--output", type=Path, help="ZIP path (default: dist/TI_Parser-<version>.zip)")
    args = parser.parse_args(argv)
    try:
        result = build_beta_distribution(args.repository, args.output, ref=args.ref)
    except (BetaDistributionError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
