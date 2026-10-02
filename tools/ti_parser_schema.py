"""Application-owned JSON Schemas for machine-facing output envelopes.

This module deliberately depends only on the Python standard library.  The
optional MCP transport can publish these schemas without making the normal
application or CLI depend on the MCP SDK.
"""

from __future__ import annotations


_ANALYSIS_STATUSES = ["complete", "deferred", "incomplete", "error"]


def _error_object_schema() -> dict:
    """Schema for errors emitted by ``UserInputError`` and compatibility checks."""

    return {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
            "context": {"type": "object"},
            "candidates": {"type": "array", "items": {"type": "object"}},
            "details": {"type": "object"},
        },
        "required": ["code", "message"],
        "additionalProperties": False,
    }


def get_tool_error_schema() -> dict:
    """Return the complete pre-session error envelope schema.

    A session-construction error has no ``saveIdentity`` or compatibility
    metadata because neither is available until the save has been loaded.
    """

    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "status": {"const": "error"},
            "error": _error_object_schema(),
        },
        "required": ["schemaVersion", "status", "error"],
        "additionalProperties": False,
    }


def _save_identity_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "fingerprint": {
                "type": "object",
                "properties": {
                    "algorithm": {"const": "sha256-canonical-save-json-v1"},
                    "value": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                "required": ["algorithm", "value"],
                "additionalProperties": False,
            },
            "gameDate": {},
            "scenario": {"type": ["string", "null"]},
            "latestSaveVersion": {"type": ["string", "null"]},
            "campaignStartVersion": {},
            "campaign": {
                "type": "object",
                "properties": {"realWorldCampaignStart": {}},
                "required": ["realWorldCampaignStart"],
                "additionalProperties": False,
            },
            "playerFaction": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "status": {"const": "resolved"},
                            "id": {"type": ["string", "integer"]},
                            "template": {"type": ["string", "null"]},
                            "display": {"type": ["string", "null"]},
                        },
                        "required": ["status", "id", "template", "display"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "status": {"const": "unresolved"},
                            "error": _error_object_schema(),
                        },
                        "required": ["status", "error"],
                        "additionalProperties": False,
                    },
                ]
            },
        },
        "required": [
            "schemaVersion",
            "fingerprint",
            "gameDate",
            "scenario",
            "latestSaveVersion",
            "campaignStartVersion",
            "campaign",
            "playerFaction",
        ],
        "additionalProperties": False,
    }


def _compatibility_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "status": {"enum": ["verified", "unverified"]},
            "reasons": {"type": "array", "items": {"type": "object"}},
            "unverifiedAllowed": {"type": "boolean"},
            "version": {"type": "object"},
            "scenario": {"type": "object"},
            "modEvidence": {"type": "object"},
            "catalogFingerprint": {"type": ["string", "null"]},
            "runtimeAssets": {"type": "array", "items": {"type": "object"}},
            "registry": {"type": "object"},
        },
        # The compatibility-registry fallback produced during save inspection
        # contains only status and reasons before AnalysisSession.run adds
        # unverifiedAllowed. The full assessment has further optional detail.
        "required": ["status", "reasons", "unverifiedAllowed"],
        "additionalProperties": True,
    }


def _application_envelope_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "parserVersion": {"type": "string"},
            "analysis": {"type": "string"},
            "saveIdentity": _save_identity_schema(),
            "compatibility": _compatibility_schema(),
            "status": {"enum": list(_ANALYSIS_STATUSES)},
            # Domain results intentionally have no common shape. Preserve the
            # exact application value, including projections and partial data.
            "result": {},
            "missingDependencies": {"type": "array", "items": {"type": "object"}},
            "error": _error_object_schema(),
        },
        # All six fields are created before AnalysisSession.run enters its
        # expected-failure handling. The other fields depend on that outcome.
        "required": [
            "schemaVersion",
            "parserVersion",
            "analysis",
            "saveIdentity",
            "compatibility",
            "status",
        ],
        "additionalProperties": False,
    }


def get_analysis_output_schema() -> dict:
    """Return the schema for an application analysis result or load error."""

    return {
        "type": "object",
        "oneOf": [_application_envelope_schema(), get_tool_error_schema()]
    }


def _argument_descriptor_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "required": {"type": "boolean"},
            "kind": {"type": "string"},
            "type": {"type": ["string", "null"]},
            "default": {},
            "choices": {
                "anyOf": [
                    {"type": "array", "items": {}},
                    {"type": "null"},
                ]
            },
        },
        "required": ["name", "required", "kind", "type", "default", "choices"],
        "additionalProperties": False,
    }


def _capability_descriptor_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "purpose": {"type": "string"},
            "kind": {"type": "string"},
            "requiresVerifiedCompatibility": {"type": "boolean"},
            "allowsExplicitUnverifiedConsent": {"type": "boolean"},
            "requiresSave": {"type": "boolean"},
            "requiresSourceCheckout": {"type": "boolean"},
            "routingClass": {"type": "string"},
            "applicationCallable": {"type": "boolean"},
            "arguments": {"type": "array", "items": _argument_descriptor_schema()},
            # The base application inventory omits this MCP projection field.
            # The stdio adapter includes it in each exposed descriptor.
            "inputSchema": {"type": "object"},
        },
        "required": [
            "command",
            "purpose",
            "kind",
            "requiresVerifiedCompatibility",
            "allowsExplicitUnverifiedConsent",
            "requiresSave",
            "requiresSourceCheckout",
            "routingClass",
            "applicationCallable",
            "arguments",
        ],
        "additionalProperties": False,
    }


def _capabilities_inventory_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "parserVersion": {"type": "string"},
            "analyses": {
                "type": "array",
                "items": _capability_descriptor_schema(),
            },
            "bootstrapPolicy": {"type": "string"},
        },
        "required": ["schemaVersion", "parserVersion", "analyses", "bootstrapPolicy"],
        "additionalProperties": False,
    }


def get_capabilities_output_schema() -> dict:
    """Return the schema for the exposed MCP inventory or its argument error."""

    return {
        "type": "object",
        "oneOf": [_capabilities_inventory_schema(), get_tool_error_schema()]
    }
