"""Validate a beta ZIP in an isolated stdlib-only process outside the checkout."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile
from build_beta_distribution import REQUIRED_PATHS, RUNTIME_DATA, _is_distribution_path, _required_catalog_paths


def extract_verified(archive_path: Path, root: Path):
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP member")
        manifest = json.loads(archive.read("beta_manifest.json"))
        if set(names) != set(manifest["files"]) | {"beta_manifest.json"}:
            raise ValueError("Manifest membership mismatch")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError("Unsafe ZIP path")
            content = archive.read(name)
            if name != "beta_manifest.json" and hashlib.sha256(content).hexdigest() != manifest["files"][name]["sha256"]:
                raise ValueError(f"Manifest hash mismatch: {name}")
        required = REQUIRED_PATHS | {f"data/{name}" for name in RUNTIME_DATA}
        if required - set(names):
            raise ValueError("Required distribution files missing")
        if any(not _is_distribution_path(name) for name in names if name != "beta_manifest.json"):
            raise ValueError("Unexpected distribution file")
        if _required_catalog_paths(archive.read("data/catalog_manifest.json")) - set(names):
            raise ValueError("Manifest-listed runtime catalog missing")
        for name in names:
            content = archive.read(name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return manifest


def synthetic_save(path: Path):
    def row(sid, **value):
        return {"Key": {"value": sid}, "Value": {"ID": {"value": sid}, **value}}
    data = {"gamestates": {
        "TITimeState": [row(1, scenarioMetaTemplateName="ModernScenario", currentDateTime={"year":2035,"month":1,"day":10})],
        "TIFactionState": [row(2, templateName="ResistCouncil", displayName="Resistance", player={"value":3},
            resources={}, baseIncomes_year={"Research":365}, councilors=[], controlPoints=[], habitats=[], fleets=[],
            researchWeights=[0]*6, currentProjectProgress=[], availableProjectNames=[], finishedProjectNames=[], missionControlUsage=0)],
        "TIPlayerState": [row(3, faction={"value":2}, isAI=False)],
        "TIEffectsState": [row(4, effects=[])],
        "TIGlobalResearchState": [row(5, techProgress=[], finishedTechsNames=[])],
        "TIGlobalValuesState": [row(6, latestSaveVersion="synthetic-not-verified", moddingActive=False, moddingUsedAnytime=False)],
    }}
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(data, handle)


# -I removes environment/user packages; -S removes site packages entirely.
# Audit hooks reject network operations and installed-game inputs during runtime.
BOOT = r'''
import sys, runpy, pathlib
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / 'tools'))
def audit(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind'}:
        raise RuntimeError('Network access forbidden in beta acceptance')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        value = str(args[0]).lower().replace(chr(92), '/')
        if 'assembly-csharp.dll' in value or 'streamingassets/templates' in value:
            raise RuntimeError('Installed game input forbidden in beta acceptance')
sys.addaudithook(audit)
if sys.argv[2] == '__catalogs__':
    import json
    from ti_parser_catalogs import RuntimeCatalogs
    from ti_parser_core import load_hab_module_catalog, load_location_catalog
    scenarios = json.loads((root/'data/effect_catalog.json').read_text())['supportedScenarios']
    for scenario in scenarios:
        RuntimeCatalogs.load(scenario, root/'data')
    load_hab_module_catalog(); load_location_catalog()
    print(json.dumps({'scenarios': scenarios}))
else:
    args = sys.argv[2:]
    sys.argv = [str(root/'tools/ti_save_parser.py'), *args]
    runpy.run_path(sys.argv[0], run_name='__main__')
'''


def verify_archive(archive_path: Path):
    with tempfile.TemporaryDirectory(prefix="ti-beta-acceptance-") as directory:
        base = Path(directory)
        root = base / "배포 폴더"
        manifest = extract_verified(archive_path, root)
        outside = base / "별도 작업 경로"
        outside.mkdir()
        save = outside / "합성 세이브.gz"
        synthetic_save(save)
        checks = []

        def run(args, expected=0, json_output=True):
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", BOOT, str(root), *args],
                cwd=outside, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=120)
            if result.returncode != expected:
                raise RuntimeError(f"{args}: exit {result.returncode}; {result.stdout}\n{result.stderr}")
            checks.append({"command": next((arg for arg in args if arg in {"inspect-save", "analyze", "topbar", "capabilities", "__catalogs__", "--version", "--help"}), args[0]), "exitCode": result.returncode})
            return json.loads(result.stdout) if json_output else result.stdout.strip()

        version = run(["--version"], json_output=False)
        if version != manifest["version"]:
            raise ValueError("Runtime version differs from manifest")
        run(["--help"], json_output=False)
        inventory = run(["capabilities"])
        if not inventory["analyses"]:
            raise ValueError("Empty capabilities")
        catalogs = run(["__catalogs__"])
        facts = run(["--save", str(save), "inspect-save"])
        blocked = run(["--save", str(save), "topbar"], expected=2)
        if blocked["error"]["code"] != "unverified-compatibility":
            raise ValueError("Unverified calculation was not gated")
        deferred = run(["--save", str(save), "analyze"], expected=2)
        report_path = outside / "bootstrap.json"
        report = run(["--save", str(save), "--allow-unverified", "analyze", "--output", str(report_path)])
        if facts["saveIdentity"] != report["saveIdentity"] or deferred["status"] != "deferred":
            raise ValueError("Identity or deferred contract mismatch")
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise ValueError("File and stdout report differ")
        run(["--save", str(save), "--allow-unverified", "topbar"])
        return {"status":"complete", "sourceCommit":manifest["sourceCommit"], "version":version,
                "checks":checks, "supportedScenarios":catalogs["scenarios"],
                "isolation":"stdlib only (-I -S), outside checkout, network/game-input audit guards"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        result = verify_archive(args.archive)
    except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status":"failed", "reason":str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
