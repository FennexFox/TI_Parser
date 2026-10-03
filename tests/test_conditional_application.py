"""Receipt integrity and save-generation races independent of engine math."""
import asyncio
from copy import deepcopy
import sys
from types import SimpleNamespace

import pytest

from ti_parser_conditional_application import ConditionalApplication, _digest


def identity():
    return {"schemaVersion": 1, "fingerprint": {"algorithm": "sha256-canonical-save-json-v1", "value": "a" * 64},
            "scenario": "ModernScenario", "gameDate": {"year": 2035, "month": 1, "day": 1},
            "campaign": {"realWorldCampaignStart": "2026-01-01"},
            "playerFaction": {"status": "resolved", "id": 7, "template": "ResistCouncil"}}


def document():
    return {"peer": {"saveIdentity": identity(), "selectedNationId": 10},
            "observations": {"nation": {"id": 10, "playerFactionId": 7,
                "asOf": "2035-01-01T00:00:00Z", "controlPoints": [
                    {"id": 20 + n, "position": n, "ownerFactionId": 7} for n in range(6)]}},
            "assumptions": {"xenoformingLevel": 0}}


class Inspector:
    def __init__(self):
        self.calls = 0
        self.change_at = None
        self.changed = False
        self.owner_invalid = False

    async def __call__(self, path, nation):
        self.calls += 1
        data = identity()
        if self.changed or self.calls == self.change_at:
            data["fingerprint"]["value"] = "b" * 64
        return {"status": "complete", "saveIdentity": data,
                "subject": {"nationId": nation, "playerFactionId": 8 if self.owner_invalid else 7,
                            "controlPointIds": list(range(20, 26))}}


@pytest.fixture
def application(monkeypatch):
    # This suite tests only the application boundary. Real engine math and
    # contract validation are exercised independently in the engine suite.
    engine = SimpleNamespace(build_conditional_state=lambda doc: None,
        calculate_conditional_projection=lambda doc, plans: {"status": "complete", "conditional": True})
    monkeypatch.setitem(sys.modules, "ti_parser_conditional_projection", engine)
    monkeypatch.setattr("ti_parser_conditional_application._scope", lambda: "current-scope")
    inspector = Inspector()
    return ConditionalApplication(inspect_save=inspector), inspector


def run(awaitable):
    return asyncio.run(awaitable)


def register(app, doc=None, pinned=False):
    return run(app.call("register-visible-context", {"document": doc or document(), "save_path": "example.gz", "pinned": pinned}))


def project(app, receipt):
    return run(app.call("conditional-nation-projection", {"receipt": receipt, "plans": []}))


def verify(app, registration, result, doc=None):
    return run(app.call("verify-visible-generation", {"receipt": registration["receipt"],
        "projection_receipt": result["projectionReceipt"], "document": doc or document()}))


def test_registered_snapshot_is_immutable_and_receipts_bind_server_result(application):
    app, inspector = application
    reported = document()
    registration = register(app, reported)
    reported["assumptions"]["xenoformingLevel"] = 99
    result = project(app, registration["receipt"])
    original = deepcopy(result)
    result["result"]["conditional"] = False
    proof = verify(app, registration, result)
    assert proof["adviceStatus"] == "conditional-only"
    assert proof["projectionDigest"] == _digest(original)
    assert proof["projectionDigest"] != _digest(result)
    assert inspector.calls == 5


@pytest.mark.parametrize("phase", [2, 3, 4, 5])
def test_save_replacement_rejects_each_observation_boundary(application, phase):
    app, inspector = application
    inspector.change_at = phase
    registered = register(app)
    if phase == 2:
        assert registered["status"] == "error"
        return
    result = project(app, registered["receipt"])
    if phase in (3, 4):
        assert result["status"] == "error"
    else:
        assert verify(app, registered, result)["status"] == "error"
    assert project(app, registered["receipt"])["status"] == "error"


def test_changed_reobservation_invalidates_entire_advice_batch(application):
    app, _ = application
    registered = register(app)
    result = project(app, registered["receipt"])
    changed = document()
    changed["assumptions"]["xenoformingLevel"] = 1
    assert verify(app, registered, result, changed)["error"]["code"] == "conditional-context-changed"
    assert project(app, registered["receipt"])["status"] == "error"


def test_forged_projection_receipt_cannot_replace_issuance(application):
    app, _ = application
    registered = register(app)
    result = project(app, registered["receipt"])
    assert project(app, "forged")["error"]["code"] == "conditional-receipt-invalid"
    copied = ConditionalApplication(inspect_save=Inspector())
    assert project(copied, registered["receipt"])["status"] == "error"
    result["projectionReceipt"] = "forged"
    assert verify(app, registered, result)["error"]["code"] == "conditional-projection-receipt-invalid"


def test_scope_change_and_expiration_reject_old_receipts(application, monkeypatch):
    app, _ = application
    registered = register(app)
    monkeypatch.setattr("ti_parser_conditional_application._scope", lambda: "changed-scope")
    assert project(app, registered["receipt"])["status"] == "error"
    monkeypatch.setattr("ti_parser_conditional_application._scope", lambda: "current-scope")
    now = [0.0]
    expiring = ConditionalApplication(inspect_save=Inspector(), ttl_seconds=1, clock=lambda: now[0])
    registered = register(expiring)
    now[0] = 1
    assert project(expiring, registered["receipt"])["error"]["code"] == "conditional-receipt-expired"


def test_subject_identity_is_not_attested_by_caller_ids(application):
    app, inspector = application
    inspector.owner_invalid = True
    assert register(app)["error"]["code"] == "conditional-subject-mismatch"


def test_reported_point_owner_must_match_verified_player(application):
    app, inspector = application
    reported = document()
    reported["observations"]["nation"]["controlPoints"][0]["ownerFactionId"] = 8
    assert register(app, reported)["error"]["code"] == "conditional-subject-mismatch"
    assert inspector.calls == 0


def test_weak_identity_requires_explicit_pin_and_remains_provisional(application):
    app, _ = application
    weak = document()
    weak["peer"]["saveIdentity"].pop("fingerprint")
    assert register(app, weak)["status"] == "error"
    registered = register(app, weak, pinned=True)
    assert registered["correlation"]["status"] == "provisional"
    result = project(app, registered["receipt"])
    proof = verify(app, registered, result, weak)
    assert proof["correlation"]["status"] == "provisional"
    assert "cannot prove" in proof["generationLimit"]


def test_exact_fingerprint_conflict_is_not_bypassed_by_pin(application):
    app, _ = application
    conflict = document()
    conflict["peer"]["saveIdentity"]["fingerprint"]["value"] = "c" * 64
    assert register(app, conflict, pinned=True)["status"] == "error"


@pytest.mark.parametrize("change", ["time", "hidden-identity-payload", "scenario"])
def test_reported_identity_channel_is_strict(application, change):
    app, _ = application
    doc = document()
    if change == "time":
        doc["observations"]["nation"]["asOf"] = "2035-01-02T00:00:00Z"
    elif change == "scenario":
        doc["peer"]["saveIdentity"]["scenario"] = "2070Scenario"
    else:
        doc["peer"]["saveIdentity"]["hiddenAI"] = "secret payload"
    result = register(app, doc)
    assert result["status"] == "error"
    assert "secret" not in str(result)


def test_error_details_and_unapproved_options_are_not_exposed(application):
    app, _ = application
    response = run(app.call("conditional-nation-projection", {"receipt": "secret", "plans": [], "allow_unverified": True}))
    assert response["status"] == "error"
    assert "secret" not in str(response)
    assert run(app.call("nation-projection", {}))["status"] == "error"


def test_real_scope_binds_parser_and_packaged_data_without_line_ending_noise(tmp_path, monkeypatch):
    import ti_parser_conditional_application as module

    tools = tmp_path / "tools"
    data = tmp_path / "data"
    tools.mkdir()
    data.mkdir()
    source = tools / "ti_parser_conditional_application.py"
    source.write_bytes(b"policy = 1\n")
    catalog = data / "catalog.json"
    catalog.write_bytes(b'{"value":1}')
    monkeypatch.setattr(module, "__file__", str(source))
    initial = module._scope()
    source.write_bytes(b"policy = 1\r\n")
    assert module._scope() == initial
    source.write_bytes(b"policy = 2\n")
    assert module._scope() != initial
    source.write_bytes(b"policy = 1\n")
    catalog.write_bytes(b'{"value":2}')
    assert module._scope() != initial
    catalog.write_bytes(b'{"value":1}')
    (tools / "ti_parser_new_dependency.py").write_bytes(b"rule = 1\n")
    assert module._scope() != initial
