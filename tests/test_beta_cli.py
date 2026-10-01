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
