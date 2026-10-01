"""Versioned machine-facing inventory generated from the analysis registry."""

from ti_parser_registry import ANALYSES
from ti_parser_version import __version__


CALCULATION_COMMANDS = frozenset(
    descriptor.command
    for descriptor in ANALYSES
    if descriptor.requires_verified_compatibility
)


def capabilities():
    return {
        "schemaVersion": 1,
        "parserVersion": __version__,
        "analyses": [descriptor.as_dict() for descriptor in ANALYSES],
        "bootstrapPolicy": "analyze returns saved facts without consent; its calculated sections require verified compatibility or explicit consent",
    }
