"""Conservative application policy for fair-play save analysis.

The profile deliberately exposes only sanitized identity inspection. Analysis
classifications live in ``ti_parser_registry`` so this module does not create a
second policy inventory.
"""

from __future__ import annotations

import re
import math
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ti_parser_errors import UserInputError
from ti_parser_registry import ANALYSES


DEFAULT_PROFILE = "default"
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
        "analyses": [
            {
                "command": descriptor.command,
                "classification": descriptor.fair_play_classification,
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
    "DEFAULT_PROFILE", "FAIR_PLAY_PROFILE", "FAIRPLAY_BOOTSTRAP_POLICY",
    "compare_save_context", "exposed_entries", "get_profile_output_schema",
    "policy_inventory", "run_profile", "sanitize_profile_error", "validate_profile",
]
