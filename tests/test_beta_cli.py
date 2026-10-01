import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ti_save_parser as ti
import ti_parser_cli as cli


def invoke(args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = ti.main(args)
    return code, json.loads(out.getvalue())


def test_selector_name_and_id_are_exclusive():
    code, result = invoke(["nation", "USA", "--entity-id", "1"])
    assert code == 2
    assert result["error"]["code"] == "invalid-arguments"


def test_advise_id_preserves_required_target():
    args = cli.build_parser(ti).parse_args(["advise", "USA", "--entity-id", "10"])
    assert args.councilor is None
    assert args.nation == "USA"


def test_unexpected_failure_has_distinct_status():
    with patch.object(ti, "resolve_save_path", side_effect=RuntimeError("bug")):
        code, result = invoke(["summary"])
    assert code == 1
    assert result["error"]["code"] == "internal-error"


def test_missing_save_is_structured():
    code, result = invoke(["--save", "never-existing-beta-fixture.gz", "summary"])
    assert code == 2
    assert result["status"] == "error"


def test_unverified_gate_is_explicit_and_does_not_bypass_dependencies(tmp_path):
    from tests.test_package_only_runtime import PackageOnlyRuntimeTests
    save = PackageOnlyRuntimeTests()._save(tmp_path)
    code, result = invoke(["--save", str(save), "topbar"])
    assert code == 2 and result["error"]["code"] == "unverified-compatibility"
    code, result = invoke(["--save", str(save), "topbar", "--allow-unverified"])
    assert code == 0 and result["compatibility"]["unverifiedAllowed"]
    unsupported = PackageOnlyRuntimeTests()._save(tmp_path, "UnsupportedScenario")
    code, result = invoke(["--save", str(unsupported), "--allow-unverified", "topbar"])
    assert code == 2 and result["status"] == "incomplete"
    assert result["missingDependencies"]


def test_raw_inspection_identity_is_path_independent_and_catalog_free(tmp_path):
    import shutil
    from tests.test_package_only_runtime import PackageOnlyRuntimeTests
    from ti_parser_session import AnalysisSession
    save = PackageOnlyRuntimeTests()._save(tmp_path)
    copy = tmp_path / "copy.gz"
    shutil.copyfile(save, copy)
    with patch("ti_parser_compatibility._read_registry", side_effect=__import__("ti_parser_compatibility").CompatibilityRegistryError("missing", "missing")):
        first = AnalysisSession(save).inspect()
        second = AnalysisSession(copy).inspect()
    assert first["saveIdentity"] == second["saveIdentity"]
    assert first["compatibility"]["status"] == "unverified"
    assert str(tmp_path) not in json.dumps(first)
