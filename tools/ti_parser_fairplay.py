"""Conservative application policy for fair-play save analysis.

The profile deliberately exposes only sanitized identity inspection. Analysis
classifications live in ``ti_parser_registry`` so this module does not create a
second policy inventory.
"""

from __future__ import annotations

import re
import math
import hashlib
import json
from weakref import WeakKeyDictionary
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ti_parser_errors import UserInputError
from ti_parser_registry import ANALYSES


DEFAULT_PROFILE = "default"
FAIRPLAY_ROUTING_INSTRUCTIONS = (
    "Use Companion for current nation observations and previous-save changes. "
    "Call TI inspect-save only for requested save correlation or compatibility; "
    "it is not a bootstrap prerequisite for Companion-only questions. "
    "Fair-play projections are blocked pending source-read and authoritative evidence "
    "acceptance. Refuse hidden-state requests directly without tool calls. "
    "Do not retry another profile, infer hidden state, or invent forecasts."
)
FAIRPLAY_ADVICE_GENERATION_POLICY = {
    "id": "fair-play-projection-v1",
    "status": "pending",
    "enabled": False,
    "authorityHashStatus": "not_evaluated",
    "runtimeInstalledDiscovery": False,
}
FAIR_PLAY_PROFILE = "fair-play"
FAIRPLAY_BOOTSTRAP_POLICY = (
    "fair-play: identity inspection only; nation-projection and all other save "
    "analyses are blocked pending input visibility approval. Companion "
    "interoperability acceptance remains incomplete."
)
_EXPOSED_ROUTING_CLASSES = frozenset({"bootstrap", "primary"})
_FAIRPLAY_ANALYSIS_IDS = frozenset({"inspect-save"})
_FAIRPLAY_ERROR_MESSAGE = "The request could not be completed under the selected profile."
_SHA256_ALGORITHM = "sha256-canonical-save-json-v1"
_SHA256_VALUE = re.compile(r"^[0-9a-f]{64}$")
_ERROR_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_DATE_COMPONENTS = ("year", "month", "day", "hour", "minute", "second")


def validate_profile(profile: str) -> str:
    """Return a supported application profile or raise a structured error."""

    if isinstance(profile, str) and profile in {DEFAULT_PROFILE, FAIR_PLAY_PROFILE}:
        return profile
    raise UserInputError(
        "Unknown application profile.",
        code="invalid-profile",
        context={"supportedProfiles": [DEFAULT_PROFILE, FAIR_PLAY_PROFILE]},
    )


def exposed_entries(profile: str = DEFAULT_PROFILE):
    """Return analysis descriptors available under ``profile``.

    Default preserves the established bootstrap and primary routes. Fair-play
    is a strict allowlist derived from the registry's single classification.
    """

    selected = validate_profile(profile)
    if selected == FAIR_PLAY_PROFILE:
        return tuple(
            descriptor for descriptor in ANALYSES
            if descriptor.command in _FAIRPLAY_ANALYSIS_IDS
            and descriptor.fair_play_classification == "safe"
        )
    return tuple(
        descriptor for descriptor in ANALYSES
        if descriptor.routing_class in _EXPOSED_ROUTING_CLASSES
    )


def policy_inventory() -> dict[str, Any]:
    """Return optional classification metadata without changing capabilities."""

    visible = {entry.command for entry in exposed_entries(FAIR_PLAY_PROFILE)}
    return {
        "profile": FAIR_PLAY_PROFILE,
        "bootstrapPolicy": FAIRPLAY_BOOTSTRAP_POLICY,
        "adviceGenerationPolicy": deepcopy(FAIRPLAY_ADVICE_GENERATION_POLICY),
        "analyses": [
            {
                "command": descriptor.command,
                "classification": descriptor.fair_play_classification,
                "guardPolicy": descriptor.fair_play_guard_policy,
                "exposed": descriptor.command in visible,
            }
            for descriptor in ANALYSES
        ],
    }


def run_profile(session: Any, analysis: str, *, profile: str = DEFAULT_PROFILE, **kwargs: Any) -> dict[str, Any]:
    """Run an analysis under a named profile.

    The default route is a direct compatibility-preserving delegation. Fair-
    play performs no domain calculation and returns only a filtered identity
    and compatibility result for ``inspect-save``.
    """

    selected = validate_profile(profile)
    if selected == DEFAULT_PROFILE:
        return session.run(analysis, **kwargs)

    if analysis not in {entry.command for entry in exposed_entries(FAIR_PLAY_PROFILE)}:
        raise UserInputError(
            "Analysis is unavailable under the selected profile.",
            code="fairplay-analysis-denied",
        )
    allow_unverified = kwargs.pop("allow_unverified", False)
    if type(allow_unverified) is not bool or kwargs:
        raise UserInputError(
            "Invalid arguments for the selected profile.",
            code="invalid-arguments",
        )

    inspection = session.inspect()
    identity = _sanitize_identity(inspection.get("saveIdentity"))
    if identity is None:
        return _error_envelope("player-identity-unresolved")

    compatibility = _sanitize_compatibility(inspection.get("compatibility"))
    from ti_parser_version import __version__

    safe_result = {"saveIdentity": identity, "compatibility": compatibility}
    return {
        "schemaVersion": 1,
        "parserVersion": __version__,
        "analysis": "inspect-save",
        "saveIdentity": identity,
        "compatibility": compatibility,
        "status": "complete",
        "result": safe_result,
    }


def sanitize_profile_error(payload: Any, profile: str = DEFAULT_PROFILE) -> Any:
    """Strip potentially identifying context from transport errors in fair-play."""

    selected = validate_profile(profile)
    if selected == DEFAULT_PROFILE:
        return payload
    if not isinstance(payload, Mapping):
        return payload
    if payload.get("status") != "error" and not isinstance(payload.get("error"), Mapping):
        return payload

    error = payload.get("error")
    code = error.get("code") if isinstance(error, Mapping) else None
    if not isinstance(code, str) or not _ERROR_CODE.fullmatch(code):
        code = "request-rejected"
    return _error_envelope(code)


def _error_envelope(code: str) -> dict[str, Any]:
    if not _ERROR_CODE.fullmatch(code):
        code = "request-rejected"
    return {
        "schemaVersion": 1,
        "status": "error",
        "error": {"code": code, "message": _FAIRPLAY_ERROR_MESSAGE},
    }


def _sanitize_identity(identity: Any) -> dict[str, Any] | None:
    if not isinstance(identity, Mapping):
        return None
    fingerprint = identity.get("fingerprint")
    if not isinstance(fingerprint, Mapping):
        return None
    algorithm, value = fingerprint.get("algorithm"), fingerprint.get("value")
    if algorithm != _SHA256_ALGORITHM or not isinstance(value, str) or not _SHA256_VALUE.fullmatch(value):
        return None

    player = identity.get("playerFaction")
    if not isinstance(player, Mapping) or player.get("status") != "resolved":
        return None
    player_id = player.get("id")
    template = player.get("template")
    display = player.get("display")
    if not _valid_id(player_id) or not isinstance(template, str) or not template.strip():
        return None
    if display is not None and not isinstance(display, str):
        return None

    campaign = identity.get("campaign")
    if not isinstance(campaign, Mapping):
        return None
    date = _sanitize_date(identity.get("gameDate"))
    if date is _INVALID:
        return None
    campaign_start = _sanitize_date(campaign.get("realWorldCampaignStart"))
    if campaign_start is _INVALID:
        return None

    scenario, save_version = identity.get("scenario"), identity.get("latestSaveVersion")
    campaign_version = identity.get("campaignStartVersion")
    if scenario is not None and not isinstance(scenario, str):
        return None
    if save_version is not None and not isinstance(save_version, str):
        return None
    if not _is_safe_scalar(campaign_version):
        return None

    return {
        "schemaVersion": 1,
        "fingerprint": {"algorithm": algorithm, "value": value},
        "gameDate": date,
        "scenario": scenario,
        "latestSaveVersion": save_version,
        "campaignStartVersion": campaign_version,
        "campaign": {"realWorldCampaignStart": campaign_start},
        "playerFaction": {
            "status": "resolved",
            "id": player_id,
            "template": template,
            "display": display,
        },
    }


_INVALID = object()


def _sanitize_date(value: Any) -> Any:
    if _is_safe_scalar(value):
        return value
    if not isinstance(value, Mapping) or not value:
        return _INVALID
    if any(key not in _DATE_COMPONENTS for key in value):
        return _INVALID
    result = {}
    for key, component in value.items():
        if type(component) is not int:
            return _INVALID
        result[key] = component
    return result


def _is_safe_scalar(value: Any) -> bool:
    if type(value) is float:
        return math.isfinite(value)
    return value is None or type(value) in (str, int, bool)


def _valid_id(value: Any) -> bool:
    return type(value) is int or (isinstance(value, str) and bool(value.strip()))


def _sanitize_compatibility(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"schemaVersion": 1, "status": "unverified", "reasons": [], "unverifiedAllowed": False}
    status = value.get("status")
    if status not in {"verified", "unverified"}:
        status = "unverified"
    reasons = []
    raw_reasons = value.get("reasons")
    if isinstance(raw_reasons, (list, tuple)):
        for reason in raw_reasons:
            code = reason.get("code") if isinstance(reason, Mapping) else None
            if isinstance(code, str) and _ERROR_CODE.fullmatch(code):
                reasons.append({"code": code})
    result = {
        "schemaVersion": 1,
        "status": status,
        "reasons": reasons,
        "unverifiedAllowed": False,
    }
    catalog_fingerprint = value.get("catalogFingerprint")
    if isinstance(catalog_fingerprint, str) and _SHA256_VALUE.fullmatch(catalog_fingerprint):
        result["catalogFingerprint"] = catalog_fingerprint
    return result


def get_profile_output_schema(profile: str, analysis: str) -> dict[str, Any]:
    """Return an application-owned strict output schema for the profile route."""

    selected = validate_profile(profile)
    if selected == DEFAULT_PROFILE:
        from ti_parser_schema import get_analysis_output_schema

        return get_analysis_output_schema()
    if analysis != "inspect-save":
        return {"type": "object", "oneOf": [_fairplay_error_schema()]}

    from ti_parser_schema import _save_identity_schema

    identity_schema = deepcopy(_save_identity_schema())
    identity_schema["properties"]["playerFaction"] = next(
        branch for branch in identity_schema["properties"]["playerFaction"]["oneOf"]
        if branch["properties"]["status"].get("const") == "resolved"
    )
    identity_schema["properties"]["gameDate"] = _date_schema()
    identity_schema["properties"]["campaignStartVersion"] = _safe_scalar_schema()
    identity_schema["properties"]["campaign"]["properties"]["realWorldCampaignStart"] = _date_schema()
    compatibility_schema = {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "status": {"enum": ["verified", "unverified"]},
            "reasons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,63}$"}},
                    "required": ["code"],
                    "additionalProperties": False,
                },
            },
            "unverifiedAllowed": {"const": False},
            "catalogFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
        "required": ["schemaVersion", "status", "reasons", "unverifiedAllowed"],
        "additionalProperties": False,
    }
    safe_result = {
        "type": "object",
        "properties": {
            "saveIdentity": identity_schema,
            "compatibility": compatibility_schema,
        },
        "required": ["saveIdentity", "compatibility"],
        "additionalProperties": False,
    }
    success = {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "parserVersion": {"type": "string"},
            "analysis": {"const": "inspect-save"},
            "saveIdentity": identity_schema,
            "compatibility": compatibility_schema,
            "status": {"const": "complete"},
            "result": safe_result,
        },
        "required": [
            "schemaVersion", "parserVersion", "analysis", "saveIdentity",
            "compatibility", "status", "result",
        ],
        "additionalProperties": False,
    }
    return {"type": "object", "oneOf": [success, _fairplay_error_schema()]}


def _safe_scalar_schema() -> dict[str, Any]:
    return {"type": ["string", "number", "boolean", "null"]}


def _date_schema() -> dict[str, Any]:
    component = {"type": "integer"}
    return {
        "anyOf": [
            _safe_scalar_schema(),
            {
                "type": "object",
                "properties": {key: component for key in _DATE_COMPONENTS},
                "additionalProperties": False,
                "minProperties": 1,
            },
        ]
    }


def _fairplay_error_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "status": {"const": "error"},
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{0,63}$"},
                    "message": {"const": _FAIRPLAY_ERROR_MESSAGE},
                },
                "required": ["code", "message"],
                "additionalProperties": False,
            },
        },
        "required": ["schemaVersion", "status", "error"],
        "additionalProperties": False,
    }


class _ProjectionSubjectBinding:
    """Opaque in-process receipt; caller JSON cannot manufacture issuance."""

    __slots__ = ("__weakref__",)


_SUBJECT_BINDINGS: WeakKeyDictionary = WeakKeyDictionary()


def _envelope_digest(envelope: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=True,
    ).encode("utf-8")).hexdigest()


def _resolve_owned_subject(session: Any, nation_name: str | int) -> tuple[int, dict[str, Any]]:
    """Resolve every declared CP; permissive income helpers cannot attest this."""
    from ti_parser_core import find_faction_state, match_raw_state
    from ti_parser_compatibility import save_identity

    player_id, _ = find_faction_state(session.indexed)
    identity = _sanitize_identity(save_identity(session.indexed))
    if identity is None or identity["playerFaction"]["id"] != player_id:
        raise UserInputError("Subject player is unresolved", code="fairplay-subject-unresolved")
    found = match_raw_state(session.indexed, "TINationState", nation_name)
    if found is None or type(found[0]) is not int:
        raise UserInputError("Subject nation is unresolved", code="fairplay-subject-unresolved")
    nation_id, nation = found
    refs = nation.get("controlPoints")
    if (not isinstance(refs, list) or not refs
            or type(nation.get("numControlPoints")) is not int
            or nation["numControlPoints"] != len(refs)):
        raise UserInputError("Subject ownership is unresolved", code="fairplay-subject-unresolved")
    seen = set()
    for reference in refs:
        cp_id = _normalize_id(reference)
        cp = session.indexed.id_index.get(cp_id) if type(cp_id) is int else None
        if (cp is None or cp[1] != "TIControlPointState" or cp_id in seen
                or not _same_value(_normalize_id(cp[2].get("nation")), nation_id)):
            raise UserInputError("Subject CP is unresolved", code="fairplay-subject-unresolved")
        seen.add(cp_id)
        owner = _normalize_id(cp[2].get("faction"))
        owner_state = session.indexed.id_index.get(owner) if type(owner) is int else None
        if owner_state is None or owner_state[1] != "TIFactionState" or owner != player_id:
            raise UserInputError("Subject is not wholly player owned", code="fairplay-subject-unresolved")
    return nation_id, identity


def _run_subject_bound_projection(session: Any, *, nation_name: str | int, **kwargs: Any):
    """Trusted application operation, private until guard acceptance.

    Never accept a caller-supplied result to attest. Compute through the existing
    session, then bind this particular result object and its complete content.
    This lower-level operation does not grant fair-play admission.
    """
    from ti_parser_session import AnalysisSession

    if type(session) is not AnalysisSession:
        raise UserInputError("Trusted analysis session required", code="fairplay-subject-unresolved")
    nation_id, identity = _resolve_owned_subject(session, nation_name)
    if kwargs.get("faction_name") is not None:
        raise UserInputError("Subject uses the strict player", code="fairplay-subject-unresolved")
    envelope = session.run("nation-projection", nation_name=nation_name, **kwargs)
    current_id, current_identity = _resolve_owned_subject(session, nation_name)
    binding = _ProjectionSubjectBinding()
    if (current_id == nation_id and _same_identity_value(current_identity, identity)
            and _same_identity_value(_sanitize_identity(envelope.get("saveIdentity")), identity)):
        _SUBJECT_BINDINGS[binding] = (envelope, _envelope_digest(envelope), nation_id, identity)
    return envelope, binding


def _run_guarded_projection(session: Any, **kwargs: Any):
    """Use the existing admission owner; metadata cannot activate projection.

    This remains denied until an audited visibility/execution guard is actually
    implemented in the profile boundary. The private subject operation above
    supplies correlation evidence only.
    """
    return run_profile(session, "nation-projection", profile=FAIR_PLAY_PROFILE, **kwargs)


def validate_advice_generation(
    context_envelope: Mapping[str, Any] | None,
    ti_inspection_envelope: Mapping[str, Any] | None,
    projection_envelope: Mapping[str, Any] | None,
    ti_reinspect_envelope: Mapping[str, Any] | None,
    companion_reobserved_context_envelope: Mapping[str, Any] | None,
    *,
    pinned: bool,
    subject_binding: Any = None,
) -> dict[str, str]:
    """Accept only a context-bound, reobserved projection generation.

    The two peer context envelopes contain saveIdentity, selectedNationId, and
    result.nation.id, which binds the selected id. Parser envelopes use the
    standard analysis, status, saveIdentity, and result fields. Inspections are
    save-only. Nation binding requires an opaque receipt from the trusted
    application operation that resolved the strict player and every owned CP
    and computed this exact projection. Caller JSON IDs are not attestations.
    Receipts are process-local and cannot be serialized for transport.

    Exact generation correlation requires the supported parser fingerprint to
    remain stable across inspect, projection, and reinspect. If either peer
    observation lacks an exact fingerprint, only an explicit pin permits a
    provisional contextual match. That weak match cannot detect hidden
    same-date changes. Incomplete projection envelopes are accepted for
    correlation only when they contain a structurally valid authoritative
    prefix; callers must preserve the incomplete outcome and must not synthesize
    predictions from it. This helper does not enable a route or expose results.
    """

    if type(pinned) is not bool:
        return _rejected("invalid-pin-state")

    peer_before = _bound_peer_context(context_envelope, "context")
    if peer_before.get("status") == "rejected":
        return peer_before
    peer_after = _bound_peer_context(companion_reobserved_context_envelope, "companion-reobserved-context")
    if peer_after.get("status") == "rejected":
        return peer_after

    inspection = _parser_generation_envelope(
        ti_inspection_envelope, "inspect-save", {"complete"}, require_nested_identity=True
    )
    if inspection.get("status") == "rejected":
        return inspection
    projection = _parser_generation_envelope(
        projection_envelope, "nation-projection", {"complete", "incomplete"}
    )
    if projection.get("status") == "rejected":
        return projection
    reinspect = _parser_generation_envelope(
        ti_reinspect_envelope, "inspect-save", {"complete"}, require_nested_identity=True
    )
    if reinspect.get("status") == "rejected":
        return reinspect

    projection_result = projection["result"]
    projection_reason = _usable_projection_result(projection["status"], projection_result)
    if projection_reason is not None:
        return _rejected(projection_reason)

    for observation in (inspection, projection, reinspect):
        if observation["fingerprint_state"] != "supported":
            return _rejected("parser-fingerprint-unavailable-or-invalid")
    if projection["fingerprint"] != inspection["fingerprint"]:
        return _rejected("parser-fingerprint-changed")
    if reinspect["fingerprint"] != inspection["fingerprint"]:
        return _rejected("parser-fingerprint-changed")

    receipt = (_SUBJECT_BINDINGS.get(subject_binding)
               if type(subject_binding) is _ProjectionSubjectBinding else None)
    if receipt is None:
        return _rejected("projection-subject-binding-missing-or-invalid")
    issued_envelope, issued_digest, selected_nation_id, issued_identity = receipt
    if issued_envelope is not projection_envelope:
        return _rejected("projection-subject-binding-result-mismatch")
    try:
        current_digest = _envelope_digest(projection_envelope)
    except (TypeError, ValueError, RecursionError):
        return _rejected("projection-subject-binding-result-changed")
    if current_digest != issued_digest:
        return _rejected("projection-subject-binding-result-changed")
    if not _same_identity_value(issued_identity, _sanitize_identity(projection["identity"])):
        return _rejected("projection-subject-binding-identity-mismatch")
    if "selectedNationId" in projection_result and not _same_value(
        _normalize_id(projection_result["selectedNationId"]), selected_nation_id
    ):
        return _rejected("selected-nation-id-mismatch")
    inspection_nation_id = reinspect_nation_id = selected_nation_id

    parser_identity = inspection["identity"]
    projection_identity = projection["identity"]
    reinspect_identity = reinspect["identity"]

    parser_pairs = (
        compare_save_context(
            parser_identity, projection_identity, inspection_nation_id, selected_nation_id,
            pinned=False, previous_parser_fingerprint=inspection["fingerprint"],
        ),
        compare_save_context(
            reinspect_identity, projection_identity, reinspect_nation_id, selected_nation_id,
            pinned=False, previous_parser_fingerprint=projection["fingerprint"],
        ),
    )
    for comparison in parser_pairs:
        if comparison["status"] != "exact":
            return comparison

    peer_pairs = (
        compare_save_context(
            parser_identity, peer_before["identity"], inspection_nation_id, peer_before["nation_id"],
            pinned=pinned,
        ),
        compare_save_context(
            reinspect_identity, peer_after["identity"], reinspect_nation_id, peer_after["nation_id"],
            pinned=pinned, previous_parser_fingerprint=inspection["fingerprint"],
        ),
    )
    for comparison in peer_pairs:
        if comparison["status"] == "rejected":
            return comparison

    if any(comparison["status"] == "provisional" for comparison in peer_pairs):
        accepted = {
            "status": "provisional",
            "reason": "pinned-context-match-without-peer-fingerprint",
        }
    else:
        accepted = {
            "status": "exact",
            "reason": "exact-generation-and-context-match",
        }
    if projection["status"] == "incomplete":
        accepted["outcomeStatus"] = "incomplete"
    return accepted


def _bound_peer_context(envelope: Any, label: str) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        return _rejected(f"{label}-missing")
    if envelope.get("status") != "complete":
        return _rejected(f"{label}-status-invalid")
    identity = envelope.get("saveIdentity")
    if not isinstance(identity, Mapping):
        return _rejected(f"{label}-save-identity-missing")
    nation_id = _normalize_id(envelope.get("selectedNationId"))
    result = envelope.get("result")
    nation = result.get("nation") if isinstance(result, Mapping) else None
    bound_id = _normalize_id(nation.get("id")) if isinstance(nation, Mapping) else _MISSING
    if nation_id is _MISSING or bound_id is _MISSING:
        return _rejected(f"{label}-selected-nation-unbound")
    if not _same_value(nation_id, bound_id):
        return _rejected(f"{label}-selected-nation-binding-mismatch")
    return {"identity": identity, "nation_id": nation_id}


def _parser_generation_envelope(
    envelope: Any,
    expected_analysis: str,
    allowed_statuses: set[str],
    *,
    require_nested_identity: bool = False,
) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        return _rejected(f"{expected_analysis}-envelope-missing")
    if type(envelope.get("schemaVersion")) is not int or envelope.get("schemaVersion") != 1:
        return _rejected(f"{expected_analysis}-envelope-schema-version-unsupported")
    if envelope.get("analysis") != expected_analysis:
        return _rejected(f"{expected_analysis}-analysis-mismatch")
    status = envelope.get("status")
    if not isinstance(status, str) or status not in allowed_statuses:
        return _rejected(f"{expected_analysis}-status-invalid")
    identity = envelope.get("saveIdentity")
    result = envelope.get("result")
    if not isinstance(identity, Mapping):
        return _rejected(f"{expected_analysis}-save-identity-missing")
    if not isinstance(result, Mapping):
        return _rejected(f"{expected_analysis}-result-missing")
    nested_identity = result.get("saveIdentity", _MISSING)
    if require_nested_identity and not isinstance(nested_identity, Mapping):
        return _rejected(f"{expected_analysis}-result-save-identity-missing")
    if nested_identity is not _MISSING:
        if not isinstance(nested_identity, Mapping) or not _same_identity_value(nested_identity, identity):
            return _rejected(f"{expected_analysis}-response-save-identity-mismatch")
    schema = identity.get("schemaVersion", _MISSING)
    if schema is not _MISSING and (type(schema) is not int or schema != 1):
        return _rejected(f"{expected_analysis}-identity-schema-version-unsupported")
    if schema != 1:
        return _rejected(f"{expected_analysis}-identity-schema-version-unsupported")
    fingerprint_state, fingerprint = _parse_fingerprint(identity.get("fingerprint"))
    if fingerprint_state == "invalid":
        return _rejected(f"{expected_analysis}-fingerprint-invalid")
    if fingerprint_state != "supported":
        return _rejected(f"{expected_analysis}-fingerprint-unavailable")
    return {
        "status": status,
        "identity": identity,
        "result": result,
        "fingerprint_state": fingerprint_state,
        "fingerprint": fingerprint,
    }


def get_profile_capabilities_output_schema(profile: str) -> dict[str, Any]:
    """Extend the shared schema only for the optional profile's pending policy."""
    from ti_parser_schema import get_capabilities_output_schema

    selected = validate_profile(profile)
    schema = get_capabilities_output_schema()
    if selected == FAIR_PLAY_PROFILE:
        inventory = schema["oneOf"][0]
        inventory["properties"]["fairPlayPolicy"] = {
            "type": "object",
            "properties": {key: {"const": value} for key, value in FAIRPLAY_ADVICE_GENERATION_POLICY.items()},
            "required": list(FAIRPLAY_ADVICE_GENERATION_POLICY),
            "additionalProperties": False,
        }
        inventory["required"].append("fairPlayPolicy")
    return schema


def _same_identity_value(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return left.keys() == right.keys() and all(
            _same_identity_value(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_identity_value(left_value, right_value)
            for left_value, right_value in zip(left, right)
        )
    return left == right


def _usable_projection_result(status: str, result: Mapping[str, Any]) -> str | None:
    initial_state = result.get("initialState")
    if not isinstance(initial_state, Mapping) or not isinstance(initial_state.get("nation"), Mapping):
        return "projection-result-unusable"
    plans = result.get("plans")
    if not isinstance(plans, list) or not plans:
        return "projection-result-unusable"
    if not isinstance(result.get("comparison"), Mapping):
        return "projection-result-unusable"
    if any(
        not isinstance(plan, Mapping)
        or not isinstance(plan.get("status"), str)
        or plan.get("status") not in {"complete", "incomplete"}
        for plan in plans
    ):
        return "projection-result-unusable"
    incomplete_plans = [plan for plan in plans if plan.get("status") == "incomplete"]
    if status == "complete":
        return "projection-status-result-mismatch" if incomplete_plans else None
    if not incomplete_plans:
        return "projection-status-result-mismatch"
    for plan in incomplete_plans:
        last_state = plan.get("lastAuthoritativeState")
        if not isinstance(last_state, Mapping) or not isinstance(last_state.get("nation"), Mapping):
            return "projection-result-incomplete-without-authoritative-prefix"
    return None


def compare_save_context(
    parser_identity: Mapping[str, Any] | None,
    companion_identity: Mapping[str, Any] | None,
    parser_nation_id: Any,
    companion_nation_id: Any,
    *,
    pinned: bool,
    previous_parser_fingerprint: Any = None,
) -> dict[str, str]:
    """Compare a companion snapshot with current parser identity evidence.

    Exact status requires matching valid parser-issued save fingerprints and
    matching campaign, date, player, and selected-nation context. If exact
    fingerprints are unavailable, a caller's explicit pin can yield only a
    provisional match after every context value has been checked.
    """

    if not isinstance(parser_identity, Mapping) or not isinstance(companion_identity, Mapping):
        return _rejected("identity-missing")
    if type(pinned) is not bool:
        return _rejected("invalid-pin-state")
    parser_schema = parser_identity.get("schemaVersion", _MISSING)
    companion_schema = companion_identity.get("schemaVersion", _MISSING)
    for version in (parser_schema, companion_schema):
        if version is not _MISSING and (type(version) is not int or version != 1):
            return _rejected("identity-schema-version-unsupported")

    context_reason = _compare_context(
        parser_identity, companion_identity, parser_nation_id, companion_nation_id
    )
    if context_reason is not None:
        return _rejected(context_reason)

    parser_fingerprint_state, parser_fingerprint = _parse_fingerprint(parser_identity.get("fingerprint"))
    companion_fingerprint_state, companion_fingerprint = _parse_fingerprint(companion_identity.get("fingerprint"))
    if "invalid" in {parser_fingerprint_state, companion_fingerprint_state}:
        return _rejected("fingerprint-invalid")
    if previous_parser_fingerprint is not None:
        previous_state, previous = _parse_fingerprint(previous_parser_fingerprint, allow_digest=True)
        if previous_state != "supported":
            return _rejected("previous-parser-fingerprint-invalid")
        if parser_fingerprint_state != "supported":
            return _rejected("parser-fingerprint-unavailable-after-observation")
        if parser_fingerprint != previous:
            return _rejected("parser-fingerprint-changed")

    if parser_fingerprint_state == companion_fingerprint_state == "supported":
        if parser_fingerprint != companion_fingerprint:
            return _rejected("fingerprint-mismatch")
        if parser_schema == companion_schema == 1:
            return {"status": "exact", "reason": "exact-fingerprint-and-context-match"}
    if not pinned:
        return _rejected("pin-required-for-provisional-match")
    return {"status": "provisional", "reason": "pinned-context-match-without-exact-fingerprint"}


def _compare_context(
    parser_identity: Mapping[str, Any],
    companion_identity: Mapping[str, Any],
    parser_nation_id: Any,
    companion_nation_id: Any,
) -> str | None:
    parser_campaign = _campaign_start(parser_identity)
    companion_campaign = _campaign_start(companion_identity)
    if parser_campaign is _MISSING or companion_campaign is _MISSING:
        return "campaign-start-missing"
    if not _same_value(parser_campaign, companion_campaign):
        return "campaign-start-mismatch"

    parser_date, companion_date = parser_identity.get("gameDate", _MISSING), companion_identity.get("gameDate", _MISSING)
    if parser_date is _MISSING or companion_date is _MISSING or parser_date is None or companion_date is None:
        return "game-date-missing"
    if not _is_safe_context_value(parser_date) or not _is_safe_context_value(companion_date):
        return "game-date-invalid"
    if not _same_value(parser_date, companion_date):
        return "game-date-mismatch"

    parser_player, companion_player = parser_identity.get("playerFaction"), companion_identity.get("playerFaction")
    if not isinstance(parser_player, Mapping) or not isinstance(companion_player, Mapping):
        return "player-identity-missing"
    if parser_player.get("status") != "resolved" or companion_player.get("status") != "resolved":
        return "player-identity-missing"
    parser_player_id, companion_player_id = parser_player.get("id"), companion_player.get("id")
    parser_template, companion_template = parser_player.get("template"), companion_player.get("template")
    if not _valid_id(parser_player_id) or not _valid_id(companion_player_id):
        return "player-identity-missing"
    if not isinstance(parser_template, str) or not parser_template.strip() or not isinstance(companion_template, str) or not companion_template.strip():
        return "player-identity-missing"
    if not _same_value(parser_player_id, companion_player_id) or parser_template != companion_template:
        return "player-identity-mismatch"

    parser_nation = _normalize_id(parser_nation_id)
    companion_nation = _normalize_id(companion_nation_id)
    if parser_nation is _MISSING or companion_nation is _MISSING:
        return "selected-nation-id-missing"
    if not _same_value(parser_nation, companion_nation):
        return "selected-nation-id-mismatch"
    return None


_MISSING = object()


def _campaign_start(identity: Mapping[str, Any]) -> Any:
    campaign = identity.get("campaign")
    if not isinstance(campaign, Mapping):
        return _MISSING
    value = campaign.get("realWorldCampaignStart", _MISSING)
    return value if value is not None and value is not _MISSING and _is_safe_context_value(value) else _MISSING


def _normalize_id(value: Any) -> Any:
    if isinstance(value, Mapping) and set(value) == {"value"}:
        value = value["value"]
    return value if _valid_id(value) else _MISSING


def _is_safe_context_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if type(value) is int:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, Mapping) and value and all(
        key in _DATE_COMPONENTS and type(component) is int for key, component in value.items()
    ):
        return True
    return False


def _same_value(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _parse_fingerprint(value: Any, *, allow_digest: bool = False) -> tuple[str, str | None]:
    if allow_digest and isinstance(value, str):
        return ("supported", value) if _SHA256_VALUE.fullmatch(value) else ("invalid", None)
    if value is None:
        return "unavailable", None
    if not isinstance(value, Mapping):
        return "invalid", None
    algorithm = value.get("algorithm")
    if algorithm != _SHA256_ALGORITHM:
        return ("unsupported", None) if isinstance(algorithm, str) and algorithm else ("invalid", None)
    digest = value.get("value")
    return ("supported", digest) if isinstance(digest, str) and _SHA256_VALUE.fullmatch(digest) else ("invalid", None)


def _rejected(reason: str) -> dict[str, str]:
    return {"status": "rejected", "reason": reason}


__all__ = [
    "get_profile_capabilities_output_schema",
    "FAIRPLAY_ROUTING_INSTRUCTIONS",
    "DEFAULT_PROFILE", "FAIR_PLAY_PROFILE", "FAIRPLAY_BOOTSTRAP_POLICY",
    "FAIRPLAY_ADVICE_GENERATION_POLICY", "compare_save_context",
    "exposed_entries", "get_profile_output_schema",
    "policy_inventory", "run_profile", "sanitize_profile_error", "validate_profile",
    "validate_advice_generation",
]
