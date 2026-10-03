"""Application-owned receipts for visible-input conditional scenarios.

The injected inspector reads identity/ownership only. Its save index must never
be passed to the model builder. A receipt attests this application's input and
calculation, not the truth or UI visibility of a caller-reported observation.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from typing import Any, Callable

from ti_parser_errors import UserInputError
from ti_parser_fairplay import compare_save_context

POLICY_ID = "visible-input-projection-v1"
_MESSAGE = "The conditional request could not be completed."


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _scope() -> str:
    """Invalidate receipts after parser, policy or packaged data changes."""
    tools = Path(__file__).resolve().parent
    paths = sorted(tools.glob("ti_parser_*.py"))
    paths += sorted((tools.parent / "data").glob("*.json"))
    return _digest({str(p.relative_to(tools.parent)): hashlib.sha256(
        p.read_bytes().replace(b"\r\n", b"\n") if p.suffix == ".py" else p.read_bytes()
    ).hexdigest() for p in paths})


def _date(value: Any) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
    if not isinstance(value, dict) or not {"year", "month", "day"} <= value.keys():
        raise ValueError("Missing game date")
    keys = {"year", "month", "day", "hour", "minute", "second", "millisecond"}
    if set(value) - keys or any(type(x) is not int for x in value.values()):
        raise ValueError("Invalid game date")
    return datetime(value["year"], value["month"], value["day"], value.get("hour", 0),
                    value.get("minute", 0), value.get("second", 0), value.get("millisecond", 0) * 1000)


def _error(code: str = "invalid-conditional-request") -> dict:
    return {"schemaVersion": 1, "profile": "conditional", "policyId": POLICY_ID,
            "status": "error", "error": {"code": code, "message": _MESSAGE}}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise UserInputError(_MESSAGE, code=code)


def _safe_peer(document: dict) -> None:
    """Reject arbitrary payloads in the identity channel, too."""
    peer = document["peer"]
    _require(set(peer) == {"saveIdentity", "selectedNationId"}, "invalid-peer-identity")
    identity = peer["saveIdentity"]
    _require(type(identity) is dict and set(identity) <= {
        "schemaVersion", "fingerprint", "gameDate", "scenario", "latestSaveVersion",
        "campaignStartVersion", "campaign", "playerFaction",
    }, "invalid-peer-identity")
    _require(identity.get("schemaVersion") == 1 and type(identity.get("schemaVersion")) is int,
             "invalid-peer-identity")
    _require(identity.get("scenario") == "ModernScenario", "unsupported-conditional-scenario")
    _require(type(identity.get("campaign")) is dict and
             set(identity["campaign"]) == {"realWorldCampaignStart"}, "invalid-peer-identity")
    player = identity.get("playerFaction")
    _require(type(player) is dict and set(player) <= {"status", "id", "template", "display"}
             and player.get("status") == "resolved" and type(player.get("id")) is int
             and isinstance(player.get("template"), str) and bool(player["template"].strip()),
             "invalid-peer-identity")
    fingerprint = identity.get("fingerprint")
    _require(fingerprint is None or (type(fingerprint) is dict and
             set(fingerprint) == {"algorithm", "value"} and
             all(isinstance(v, str) for v in fingerprint.values())), "invalid-peer-identity")
    nation = document["observations"]["nation"]
    _require(_date(nation["asOf"]) == _date(identity["gameDate"]), "observation-time-mismatch")
    _require(nation["playerFactionId"] == player["id"], "observation-player-mismatch")


class ConditionalApplication:
    """Bounded, process-local context store; inject a trusted identity inspector."""

    def __init__(self, *, inspect_save: Callable, max_contexts: int = 16,
                 ttl_seconds: float = 1800, clock: Callable = time.monotonic):
        self._inspect_save = inspect_save
        self._max_contexts = max_contexts
        self._ttl = ttl_seconds
        self._clock = clock
        self._contexts: OrderedDict[str, dict] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _observe(self, context: dict) -> dict:
        document = context["document"]
        nation = document["observations"]["nation"]
        _require(all(cp.get("ownerFactionId") == nation["playerFactionId"]
                     for cp in nation["controlPoints"]), "conditional-subject-mismatch")
        observation = await self._inspect_save(context["savePath"], nation["id"])
        _require(type(observation) is dict and observation.get("status") == "complete",
                 "conditional-inspection-unavailable")
        subject = observation.get("subject")
        expected = {"nationId": nation["id"], "playerFactionId": nation["playerFactionId"],
                    "controlPointIds": [cp["id"] for cp in sorted(nation["controlPoints"],
                                                              key=lambda cp: cp["position"])]}
        _require(subject == expected, "conditional-subject-mismatch")
        identity = observation.get("saveIdentity")
        _require(type(identity) is dict and identity.get("scenario") == "ModernScenario",
                 "unsupported-conditional-scenario")
        correlation = compare_save_context(identity, document["peer"]["saveIdentity"],
                                           subject["nationId"], document["peer"]["selectedNationId"],
                                           pinned=context["pinned"],
                                           previous_parser_fingerprint=context.get("fingerprint"))
        _require(correlation["status"] in {"exact", "provisional"}, "conditional-generation-mismatch")
        if "identity" in context:
            _require(_digest(identity) == _digest(context["identity"]), "conditional-generation-changed")
        return {"identity": deepcopy(identity), "subject": deepcopy(subject),
                "correlation": correlation}

    def _lookup(self, receipt: str) -> dict:
        _require(type(receipt) is str and receipt in self._contexts, "conditional-receipt-invalid")
        context = self._contexts[receipt]
        if self._clock() >= context["expires"]:
            context["valid"] = False
            _require(False, "conditional-receipt-expired")
        try:
            current_scope = _scope()
        except Exception:
            context["valid"] = False
            raise
        if context["scope"] != current_scope:
            context["valid"] = False
        _require(context["valid"], "conditional-receipt-invalid")
        self._contexts.move_to_end(receipt)
        return context

    def _base(self, context: dict, receipt: str) -> dict:
        return {"schemaVersion": 1, "profile": "conditional", "policyId": POLICY_ID,
                "receipt": receipt, "contextDigest": context["digest"],
                "scopeFingerprint": context["scope"], "saveIdentity": deepcopy(context["identity"]),
                "subject": deepcopy(context["subject"]), "correlation": deepcopy(context["correlation"]),
                "inputTrust": "caller-reported-observations-and-explicit-assumptions",
                "mechanicsAcceptance": "conditional-implementation-not-game-authority"}

    async def register(self, document: dict, save_path: str, pinned: bool = False) -> dict:
        from ti_parser_conditional_projection import build_conditional_state
        _require(type(pinned) is bool and isinstance(save_path, str) and bool(save_path.strip()),
                 "invalid-conditional-request")
        snapshot = deepcopy(document)
        build_conditional_state(snapshot)
        _safe_peer(snapshot)
        context = {"document": snapshot, "savePath": save_path, "pinned": pinned,
                   "digest": _digest(snapshot), "scope": _scope(), "valid": True,
                   "expires": self._clock() + self._ttl, "projections": OrderedDict()}
        context.update(await self._observe(context))
        context["fingerprint"] = deepcopy(context["identity"]["fingerprint"])
        # Reinspect after the initial identity/subject observation as well.
        await self._observe(context)
        receipt = secrets.token_urlsafe(32)
        self._contexts[receipt] = context
        while len(self._contexts) > self._max_contexts:
            self._contexts.popitem(last=False)
        return {**self._base(context, receipt), "status": "complete",
                "adviceStatus": "not-calculated"}

    async def project(self, receipt: str, plans: list) -> dict:
        from ti_parser_conditional_projection import calculate_conditional_projection
        context = self._lookup(receipt)
        try:
            await self._observe(context)
            result = calculate_conditional_projection(deepcopy(context["document"]), deepcopy(plans))
            await self._observe(context)
            _require(context["scope"] == _scope(), "conditional-evidence-changed")
        except Exception:
            context["valid"] = False
            raise
        projection_receipt = secrets.token_urlsafe(32)
        envelope = {**self._base(context, receipt), "status": result["status"],
                    "projectionReceipt": projection_receipt, "adviceStatus": "pending-reobservation",
                    "result": result}
        context["projections"][projection_receipt] = deepcopy(envelope)
        while len(context["projections"]) > 8:
            context["projections"].popitem(last=False)
        return deepcopy(envelope)

    async def verify(self, receipt: str, projection_receipt: str, document: dict) -> dict:
        context = self._lookup(receipt)
        _require(type(projection_receipt) is str and projection_receipt in context["projections"],
                 "conditional-projection-receipt-invalid")
        try:
            _require(_digest(document) == context["digest"], "conditional-context-changed")
            await self._observe(context)
        except Exception:
            context["valid"] = False
            raise
        projection = context["projections"][projection_receipt]
        return {**self._base(context, receipt), "status": "complete",
                "projectionReceipt": projection_receipt, "projectionDigest": _digest(projection),
                "adviceStatus": "conditional-only" if projection["status"] == "complete" else "incomplete-prefix-only",
                "generationLimit": "Peer identity is reported; provisional matching cannot prove a shared generation."
                if context["correlation"]["status"] == "provisional" else
                "Matching peer fingerprints do not attest observation truth or mechanics correctness."}

    async def call(self, name: str, arguments: dict) -> dict:
        methods = {"register-visible-context": (self.register, {"document", "save_path"}, {"pinned"}),
                   "conditional-nation-projection": (self.project, {"receipt", "plans"}, set()),
                   "verify-visible-generation": (self.verify, {"receipt", "projection_receipt", "document"}, set())}
        try:
            _require(name in methods and type(arguments) is dict, "unsupported-conditional-tool")
            method, required, optional = methods[name]
            _require(required <= arguments.keys() and not arguments.keys() - required - optional,
                     "invalid-conditional-request")
            async with self._lock:
                return await method(**arguments)
        except UserInputError as exc:
            return _error(exc.code)
        except Exception:
            # Neither malformed reported input nor callback/path exceptions may
            # echo raw values, save details, or a traceback to the public tool.
            return _error()

    def tool_contracts(self) -> dict:
        from ti_parser_conditional_projection import get_context_schema, get_plans_schema
        from ti_parser_registry import _schema_for_annotation
        def schema(properties: dict, required: list) -> dict:
            return {"type": "object", "properties": properties, "required": required,
                    "additionalProperties": False}
        string = _schema_for_annotation(str)
        contracts = {
            "register-visible-context": ("Register reported visible inputs and acknowledged scenario assumptions; identity/ownership only are checked against the save.",
                schema({"document": get_context_schema(), "save_path": string,
                        "pinned": {"type": "boolean", "default": False}}, ["document", "save_path"])),
            "conditional-nation-projection": ("Compare conditional 180-day Knowledge/Welfare plans using a registered input receipt; not exact game outcomes. Reobserve and verify before advice.",
                schema({"receipt": string, "plans": get_plans_schema()}, ["receipt", "plans"])),
            "verify-visible-generation": ("Verify the reobserved input generation and this server's projection receipt; assumptions and mechanics limitations still apply.",
                schema({"receipt": string, "projection_receipt": string,
                        "document": get_context_schema()}, ["receipt", "projection_receipt", "document"])),
        }
        return {name: {"description": f"[{POLICY_ID}] {description}", "inputSchema": input_schema,
                       "outputSchema": conditional_output_schema(name)}
                for name, (description, input_schema) in contracts.items()}

    def capabilities(self) -> dict:
        return {"schemaVersion": 1, "profile": "conditional",
                "policy": {"id": POLICY_ID, "enabled": True, "conditionalOnly": True,
                           "rawSaveProjectionEnabled": False, "requiresGenerationVerification": True,
                           "scenario": "ModernScenario", "model": "isolated-nation-v1",
                           "requiredOwnedControlPoints": 6, "days": 180,
                           "checkpoints": [0, 180], "segments": 1, "advisors": [],
                           "priorities": ["Knowledge", "Welfare"], "pipRange": [0, 3],
                           "planCountRange": [2, 8], "requiresPositivePipTotal": True},
                "tools": ["inspect-save", "register-visible-context", "conditional-nation-projection",
                          "verify-visible-generation"]}

    def capabilities_output_schema(self) -> dict:
        return {"type": "object", "properties": {"schemaVersion": {"const": 1},
                "profile": {"const": "conditional"}, "policy": {"type": "object"},
                "tools": {"type": "array", "items": {"type": "string"}}},
                "required": ["schemaVersion", "profile", "policy", "tools"], "additionalProperties": False}


def conditional_output_schema(tool_name: str | None = None) -> dict:
    properties = {"schemaVersion": {"const": 1}, "profile": {"const": "conditional"},
                  "policyId": {"const": POLICY_ID}, "status": {"enum": ["complete", "incomplete", "deferred", "error"]}}
    for name in ("receipt", "projectionReceipt", "contextDigest", "scopeFingerprint", "inputTrust",
                 "mechanicsAcceptance", "adviceStatus", "projectionDigest", "generationLimit"):
        properties[name] = {"type": "string"}
    for name in ("saveIdentity", "subject", "correlation", "result"):
        properties[name] = {"type": "object"}
    properties["error"] = {"type": "object", "properties": {"code": {"type": "string"},
                           "message": {"const": _MESSAGE}}, "required": ["code", "message"],
                           "additionalProperties": False}
    required_success = ["receipt", "contextDigest", "saveIdentity", "subject", "correlation",
                        "scopeFingerprint", "inputTrust", "mechanicsAcceptance", "adviceStatus"]
    if tool_name == "conditional-nation-projection":
        required_success += ["projectionReceipt", "result"]
    elif tool_name == "verify-visible-generation":
        required_success += ["projectionReceipt", "projectionDigest", "generationLimit"]
    return {"type": "object", "properties": properties,
            "required": ["schemaVersion", "profile", "policyId", "status"], "additionalProperties": False,
            "oneOf": [{"properties": {"status": {"const": "error"}}, "required": ["error"]},
                      {"properties": {"status": {"enum": ["complete", "incomplete", "deferred"]}},
                       "required": required_success}]}
