"""Regression contracts for offline evidence freshness and non-approval."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from projection_audit_evidence import review_evidence


def test_review_findings_cannot_approve_and_expire_on_source_or_build_change(tmp_path):
    (tmp_path / "tools").mkdir()
    source = tmp_path / "tools/parser.py"
    source.write_bytes(b"old parser")
    digest = "a" * 64
    path = tmp_path / "dev-docs/projection_execution_evidence.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"schemaVersion": 1, "mechanics": {
        "currentDllSha256": digest, "findings": [{"ruleId": "rule", "status": "accepted",
        "currentBuildClosureEstablished": True, "parser": {"file": "tools/parser.py",
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest()}}]},
        "visibilityFindings": {"currentDllSha256": digest, "findings": []}}))
    result = review_evidence(tmp_path, digest, digest, ["rule", "new-rule"])
    assert result["eligible"] is False
    assert result["mechanics"][0]["permissionEstablished"] is False
    assert result["unreviewedRuleIds"] == ["new-rule"]
    assert result["mechanics"][0]["applicability"] == "current"
    source.write_bytes(b"new parser")
    assert review_evidence(tmp_path, digest, digest, ["rule"])["unreviewedRuleIds"] == ["rule"]
    source.write_bytes(b"old parser")
    assert review_evidence(tmp_path, "b" * 64, digest, ["rule"])["unreviewedRuleIds"] == ["rule"]


def test_missing_or_malformed_review_is_not_evidence(tmp_path):
    assert review_evidence(tmp_path, None, None, ["rule"])["status"] == "unavailable"
    path = tmp_path / "dev-docs/projection_execution_evidence.json"
    path.parent.mkdir()
    path.write_text("[]")
    assert review_evidence(tmp_path, None, None, ["rule"])["eligible"] is False
