"""Central registry for the reusable machine-facing analysis boundary.

The application handlers are the source of executable behavior. This module
owns stable metadata and resolves handlers lazily from
``ti_parser_application.HANDLERS`` so importing the registry never imports the
application layer recursively.
"""

from __future__ import annotations

import inspect
import types
from collections import abc as collections_abc
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping, Union, get_args, get_origin, get_type_hints

from ti_parser_config import (
    HAB_MONTHLY_RESOURCES,
    HAB_PLAN_FOCUS_CHOICES,
    ORG_PLAN_FOCUS_CHOICES,
    PROJECT_ANALYSIS_SORT_CHOICES,
    RESEARCH_PLAN_MODE_CHOICES,
    SHIP_PLAN_ROLE_CHOICES,
)
from ti_parser_errors import UserInputError


_NO_DEFAULT = object()
_BOOTSTRAP_IDS = frozenset({"inspect-save", "analyze"})
_RUNTIME_OVERRIDE_NAMES = frozenset({"research_templates", "base_daily_cache"})
_ALWAYS_PRIVATE_NAMES = frozenset({"templates_dir", "templates", "runtime_catalogs", "claim_catalog"})
_ARGUMENT_CHOICES: Mapping[tuple[str, str], tuple[Any, ...]] = MappingProxyType({
    ("org-plan", "focus"): ORG_PLAN_FOCUS_CHOICES,
    ("hab-plan", "focus"): HAB_PLAN_FOCUS_CHOICES,
    ("ship-plan", "role"): SHIP_PLAN_ROLE_CHOICES,
    ("project-analysis", "sort_axis"): PROJECT_ANALYSIS_SORT_CHOICES,
    ("project-analysis", "slot"): (3, 4, 5),
    ("research-plan", "mode"): RESEARCH_PLAN_MODE_CHOICES,
    ("topbar", "forecast_resource"): HAB_MONTHLY_RESOURCES,
})


@dataclass(frozen=True)
class ArgumentDescriptor:
    """One caller-visible argument in an analysis contract."""

    name: str
    required: bool
    kind: str
    annotation: str | None = None
    default: Any = _NO_DEFAULT
    choices: tuple[Any, ...] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "kind": self.kind,
            "type": self.annotation,
            "default": None if self.default is _NO_DEFAULT else _json_value(self.default),
            "choices": None if self.choices is None else [_json_value(value) for value in self.choices],
        }


@dataclass(frozen=True)
class AnalysisDescriptor:
    """Immutable metadata and lazy handler reference for one analysis ID."""

    command: str
    purpose: str
    kind: str
    requires_verified_compatibility: bool
    allows_explicit_unverified_consent: bool
    requires_save: bool
    requires_source_checkout: bool
    routing_class: str
    application_callable: bool
    input_kind: str
    required_arguments: frozenset[str] = frozenset()
    fair_play_classification: Literal[
        "safe", "own-subject", "visibility-dependent", "diagnostic"
    ] = "visibility-dependent"
    fair_play_guard_policy: str | None = None

    @property
    def fair_play_policy(self) -> str:
        """Alias emphasizing that the classification is policy metadata."""

        return self.fair_play_classification

    @property
    def id(self) -> str:
        return self.command

    @property
    def handler(self) -> Callable[..., Any] | None:
        """Resolve the application handler only when this property is read."""

        if not self.application_callable or self.command in _BOOTSTRAP_IDS:
            return None
        from ti_parser_application import HANDLERS

        handler = HANDLERS[self.command]
        if not callable(handler):
            raise TypeError(f"Application handler for {self.command!r} is not callable.")
        return handler

    def resolve_handler(self) -> Callable[..., Any] | None:
        return self.handler

    @property
    def arguments(self) -> tuple[ArgumentDescriptor, ...]:
        """Return the caller-facing contract derived from ``HANDLERS``."""

        if self.command in _BOOTSTRAP_IDS or not self.application_callable:
            return ()
        return _signature_arguments(
            self.handler,
            required_arguments=self.required_arguments,
            analysis_id=self.command,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "purpose": self.purpose,
            "kind": self.kind,
            "requiresVerifiedCompatibility": self.requires_verified_compatibility,
            "allowsExplicitUnverifiedConsent": self.allows_explicit_unverified_consent,
            "requiresSave": self.requires_save,
            "requiresSourceCheckout": self.requires_source_checkout,
            "routingClass": self.routing_class,
            "applicationCallable": self.application_callable,
            "arguments": [argument.as_dict() for argument in self.arguments],
        }


# (command, purpose, kind, compatibility requirement, routing class,
# application-callable, input kind, required caller selectors, fair-play class)
_METADATA: tuple[tuple[Any, ...], ...] = (
    ("inspect-save", "Identify save, campaign and player without calculations", "observed-state", False, "bootstrap", True, "session", (), "safe"),
    ("analyze", "Bounded LLM bootstrap context and next analysis routes", "bootstrap-context", False, "bootstrap", True, "session", (), "visibility-dependent"),
    ("summary", "Compact campaign summary", "reconstructed-state", True, "primary", True, "snapshot", (), "visibility-dependent"),
    ("faction", "Faction summary", "reconstructed-state", True, "primary", True, "snapshot", ("name",), "visibility-dependent"),
    ("nation", "Nation summary", "reconstructed-state", True, "primary", True, "snapshot", ("name",), "visibility-dependent"),
    ("councilor", "Councilor attributes and conditions", "reconstructed-state", True, "primary", True, "snapshot", ("name",), "visibility-dependent"),
    ("topbar", "Resource income, MC and CP capacity; optional queue forecast", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("research", "Research income breakdown", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("research-ui", "Active research slots, progress and ETA", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("research-plan", "Research candidates and goal-specific evidence", "planning-evidence", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("org-plan", "Organization acquisition and assignment evidence", "planning-evidence", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("hab-ui", "Habitat power, modules and support", "reconstructed-state", True, "primary", True, "indexed", ("hab_name",), "visibility-dependent"),
    ("hab-slots", "Usable habitat slots", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("hab-plan", "Habitat module candidates and expansion evidence", "planning-evidence", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("ship-plan", "Ship component choices and design simulations", "planning-evidence", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("project-analysis", "Project unlocks and resource tradeoffs", "planning-evidence", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("nation-ui", "Nation priorities and displayed metrics", "reconstructed-state", True, "primary", True, "indexed", ("nation_name",), "visibility-dependent"),
    ("nation-claims", "Claims and reconstructed hostility", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("nation-projection", "Counterfactual future nation outcomes under candidate priority plans; preserve conditional mechanics evidence", "simulation", True, "primary", True, "indexed", ("nation_name", "days"), "visibility-dependent"),
    ("advise", "Hypothetical councilor advice contribution", "simulation", True, "primary", True, "indexed", ("councilor_name", "nation_name"), "visibility-dependent"),
    ("world-ui", "World population, climate and markets", "reconstructed-state", True, "primary", True, "indexed", (), "visibility-dependent"),
    ("ai-fleet-diagnostics", "AI goals and unresolved causes", "reconstructed-state", True, "diagnostic", True, "indexed", (), "diagnostic"),
    ("raw", "Selected raw save fields", "observed-state", False, "advanced", False, "indexed", (), "diagnostic"),
    ("types", "Save state type counts", "observed-state", False, "advanced", False, "indexed", (), "diagnostic"),
    ("export", "Export calculated compact snapshot", "maintenance", True, "maintenance", False, "snapshot", (), "diagnostic"),
    ("cache", "Build or validate calculated snapshot cache", "maintenance", True, "maintenance", False, "indexed", (), "diagnostic"),
    ("catalog-verify", "Audit packaged catalogs against explicit game sources", "maintenance", False, "maintenance", False, "session", (), "diagnostic"),
    ("capabilities", "Machine-readable analysis inventory", "inventory", False, "inventory", False, "session", (), "safe"),
)


def _make_descriptor(row: tuple[Any, ...]) -> AnalysisDescriptor:
    command, purpose, kind, requires_verified, routing_class, application_callable, input_kind, required_arguments, fair_play_classification = row
    return AnalysisDescriptor(
        command=command,
        purpose=purpose,
        kind=kind,
        requires_verified_compatibility=bool(requires_verified),
        allows_explicit_unverified_consent=bool(requires_verified or command == "analyze"),
        requires_save=command not in {"capabilities", "catalog-verify"},
        requires_source_checkout=command == "catalog-verify",
        routing_class=routing_class,
        application_callable=bool(application_callable),
        input_kind=input_kind,
        required_arguments=frozenset(required_arguments),
        fair_play_classification=fair_play_classification,
        fair_play_guard_policy="fair-play-projection-v1" if command == "nation-projection" else None,
    )


ANALYSES: tuple[AnalysisDescriptor, ...] = tuple(_make_descriptor(row) for row in _METADATA)
ANALYSIS_REGISTRY: Mapping[str, AnalysisDescriptor] = MappingProxyType({
    descriptor.command: descriptor for descriptor in ANALYSES
})
PRIMARY_ANALYSIS_IDS = frozenset(
    descriptor.command for descriptor in ANALYSES if descriptor.routing_class == "primary"
)
CALLABLE_ANALYSIS_IDS = frozenset(
    descriptor.command for descriptor in ANALYSES if descriptor.application_callable
)


def _validate_registry() -> None:
    commands = [descriptor.command for descriptor in ANALYSES]
    if len(commands) != len(set(commands)):
        raise RuntimeError("Analysis registry contains duplicate command IDs.")
    for descriptor in ANALYSES:
        if descriptor.fair_play_classification not in {
            "safe", "own-subject", "visibility-dependent", "diagnostic"
        }:
            raise RuntimeError(f"Invalid fair-play classification for {descriptor.command!r}.")
        if descriptor.routing_class in {"primary", "bootstrap", "diagnostic"} and not descriptor.application_callable:
            raise RuntimeError(f"Callable routing class is disabled for {descriptor.command!r}.")
        if descriptor.routing_class in {"advanced", "maintenance", "inventory"} and descriptor.application_callable:
            raise RuntimeError(f"Unsupported routing class is callable for {descriptor.command!r}.")


_validate_registry()


def _annotation_text(annotation: Any) -> str | None:
    if annotation is inspect.Parameter.empty:
        return None
    if isinstance(annotation, str):
        return annotation
    if annotation is Any:
        return "Any"
    text = str(annotation)
    if text.startswith("<class '") and text.endswith("'>"):
        return text[8:-2]
    return text.removeprefix("typing.")


def _literal_choices(annotation: Any) -> tuple[Any, ...] | None:
    origin = get_origin(annotation)
    if origin is not None and str(origin).endswith("Literal"):
        return tuple(get_args(annotation))
    return None


def _signature_parameters(
    handler: Callable[..., Any],
    *,
    allow_runtime_overrides: bool = False,
) -> tuple[inspect.Signature, dict[str, Any]]:
    signature = inspect.signature(handler)
    parameters = list(signature.parameters.values())
    if parameters:
        parameters = parameters[1:]  # indexed state or compact snapshot
    private = _ALWAYS_PRIVATE_NAMES
    if not allow_runtime_overrides:
        private = private | _RUNTIME_OVERRIDE_NAMES
    parameters = [parameter for parameter in parameters if parameter.name not in private]
    try:
        hints = get_type_hints(handler)
    except (NameError, TypeError, ValueError):
        hints = {}
    return signature.replace(parameters=parameters), hints


def _signature_arguments(
    handler: Callable[..., Any],
    *,
    required_arguments: frozenset[str] = frozenset(),
    analysis_id: str | None = None,
) -> tuple[ArgumentDescriptor, ...]:
    signature, hints = _signature_parameters(handler)
    arguments: list[ArgumentDescriptor] = []
    for parameter in signature.parameters.values():
        required = parameter.name in required_arguments or (
            parameter.default is inspect.Parameter.empty
            and parameter.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        )
        annotation = hints.get(parameter.name, parameter.annotation)
        arguments.append(
            ArgumentDescriptor(
                name=parameter.name,
                required=required,
                kind=parameter.kind.name.lower().replace("_", "-"),
                annotation=_annotation_text(annotation),
                default=_NO_DEFAULT if parameter.default is inspect.Parameter.empty else parameter.default,
                choices=(
                    _ARGUMENT_CHOICES.get((analysis_id, parameter.name))
                    if analysis_id is not None and (analysis_id, parameter.name) in _ARGUMENT_CHOICES
                    else _literal_choices(annotation)
                ),
            )
        )
    return tuple(arguments)


def get_analysis(analysis: str) -> AnalysisDescriptor:
    """Return the immutable registry entry for an analysis ID."""

    if not isinstance(analysis, str) or analysis not in ANALYSIS_REGISTRY:
        raise UserInputError(
            f"Unknown analysis: {analysis!r}",
            code="unknown-analysis",
            context={"analysis": analysis},
        )
    return ANALYSIS_REGISTRY[analysis]


def _schema_for_annotation(annotation: Any) -> dict[str, Any]:
    """Translate the supported public handler annotations to JSON Schema."""

    if annotation is inspect.Parameter.empty:
        return {}
    if annotation in (Any, object):
        return {}
    if annotation is type(None):
        return {"type": "null"}

    origin = get_origin(annotation)
    if origin is Literal:
        values = list(get_args(annotation))
        schema: dict[str, Any] = {"enum": [_json_value(value) for value in values]}
        value_types = {_schema_for_annotation(type(value)).get("type") for value in values}
        if len(value_types) == 1:
            schema["type"] = value_types.pop()
        return schema
    if origin in (types.UnionType, Union):
        return {"anyOf": [_schema_for_annotation(item) for item in get_args(annotation)]}
    if origin in (list, set, frozenset):
        item_types = get_args(annotation)
        item_type = item_types[0] if item_types and item_types[0] is not Ellipsis else Any
        return {"type": "array", "items": _schema_for_annotation(item_type)}
    if origin is tuple:
        item_types = get_args(annotation)
        if len(item_types) == 2 and item_types[1] is Ellipsis:
            return {"type": "array", "items": _schema_for_annotation(item_types[0])}
        if item_types:
            return {
                "type": "array",
                "prefixItems": [_schema_for_annotation(item_type) for item_type in item_types],
                "items": False,
                "minItems": len(item_types),
                "maxItems": len(item_types),
            }
        return {"type": "array", "items": {}}
    if origin in (dict, Mapping, collections_abc.Mapping):
        value_type = get_args(annotation)[1] if len(get_args(annotation)) > 1 else Any
        return {"type": "object", "additionalProperties": _schema_for_annotation(value_type)}
    if annotation is Path:
        return {"type": "string"}
    if annotation is bool:
        return {"type": "boolean"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is str:
        return {"type": "string"}
    raise TypeError(f"Unsupported application argument annotation for JSON Schema: {annotation!r}")


def _schema_with_choices(schema: dict[str, Any], choices: tuple[Any, ...] | None) -> dict[str, Any]:
    if choices is None:
        return schema
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            if branch.get("type") != "null" and "enum" not in branch:
                branch["enum"] = [_json_value(value) for value in choices]
    elif "enum" not in schema:
        schema["enum"] = [_json_value(value) for value in choices]
    return schema


def get_input_schema(analysis: str) -> dict[str, Any]:
    """Return a fresh JSON Schema object for one callable analysis contract.

    The registry derives argument presence and types from the application
    handler signatures, then adds declared selector choices owned here. The
    returned nested objects are newly allocated so callers may extend them.
    """

    descriptor = get_analysis(analysis)
    if not descriptor.application_callable:
        raise UserInputError(
            f"Analysis is not callable through the application API: {descriptor.command}",
            code="unsupported-analysis",
            context={"analysis": descriptor.command, "routingClass": descriptor.routing_class},
        )
    properties: dict[str, Any] = {}
    required: list[str] = []
    if descriptor.command not in _BOOTSTRAP_IDS:
        handler = descriptor.handler
        signature, hints = _signature_parameters(handler)
        for argument in descriptor.arguments:
            parameter = signature.parameters[argument.name]
            annotation = hints.get(argument.name, parameter.annotation)
            if descriptor.command == "nation-projection" and argument.name == "plan_payload":
                schema = {"anyOf": [{"type": "object"}, {"type": "null"}]}
            else:
                schema = _schema_for_annotation(annotation)
            schema = _schema_with_choices(schema, argument.choices)
            if argument.default is not _NO_DEFAULT:
                schema["default"] = _json_value(argument.default)
            properties[argument.name] = schema
            if argument.required:
                required.append(argument.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def validate_argument_shape(entry: AnalysisDescriptor | str, name: str, value: Any) -> None:
    """Validate a caller value whose application annotation is too broad.

    JSON plan documents are objects or null. Keeping this narrow check in the
    registry lets transports reject malformed documents before opening a save
    session while the application API enforces the same contract.
    """

    descriptor = get_analysis(entry) if isinstance(entry, str) else entry
    if (
        isinstance(descriptor, AnalysisDescriptor)
        and descriptor.command == "nation-projection"
        and name == "plan_payload"
        and value is not None
        and not isinstance(value, dict)
    ):
        raise UserInputError(
            "Argument 'plan_payload' must be an object or null.",
            code="invalid-arguments",
            context={
                "analysis": descriptor.command,
                "argument": name,
                "expected": "object or null",
                "received": type(value).__name__,
            },
        )


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return repr(value)


def _type_matches(value: Any, annotation: Any) -> bool:
    if annotation is inspect.Parameter.empty or annotation in (Any, object):
        return True
    if isinstance(annotation, str):
        return True
    if value is None:
        return type(None) in get_args(annotation) or annotation is type(None)
    origin = get_origin(annotation)
    if origin in (types.UnionType, Union):
        return any(_type_matches(value, item) for item in get_args(annotation))
    if origin is not None:
        if str(origin).endswith("Literal"):
            return value in get_args(annotation)
        if origin in (list, set, frozenset, tuple):
            if not isinstance(value, origin):
                return False
            item_types = get_args(annotation)
            if not item_types:
                return True
            if origin is tuple and len(item_types) == 2 and item_types[1] is Ellipsis:
                return all(_type_matches(item, item_types[0]) for item in value)
            if origin is tuple and len(item_types) == len(value):
                return all(_type_matches(item, expected) for item, expected in zip(value, item_types))
            return all(_type_matches(item, item_types[0]) for item in value)
        if origin is dict:
            return isinstance(value, dict)
        return True
    if annotation is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if annotation is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if annotation is bool:
        return isinstance(value, bool)
    if annotation is str:
        return isinstance(value, str)
    try:
        return isinstance(value, annotation)
    except TypeError:
        return True


def validate_arguments(
    entry: AnalysisDescriptor | str,
    kwargs: Mapping[str, Any] | None = None,
    *,
    allow_runtime_overrides: bool = False,
    **named_kwargs: Any,
) -> dict[str, Any]:
    """Validate and return caller arguments for one application analysis."""

    descriptor = get_analysis(entry) if isinstance(entry, str) else entry
    if not isinstance(descriptor, AnalysisDescriptor):
        raise UserInputError("Analysis entry is invalid.", code="invalid-analysis")
    if kwargs is None:
        arguments: dict[str, Any] = dict(named_kwargs)
    elif named_kwargs:
        raise UserInputError(
            "Pass arguments as a mapping or keyword arguments, not both.",
            code="invalid-arguments",
            context={"analysis": descriptor.command},
        )
    elif not isinstance(kwargs, Mapping):
        raise UserInputError(
            "Analysis arguments must be a mapping.",
            code="invalid-arguments",
            context={"analysis": descriptor.command},
        )
    else:
        arguments = dict(kwargs)

    if not descriptor.application_callable:
        raise UserInputError(
            f"Analysis is not callable through the application API: {descriptor.command}",
            code="unsupported-analysis",
            context={"analysis": descriptor.command, "routingClass": descriptor.routing_class},
        )
    if descriptor.command in _BOOTSTRAP_IDS:
        if arguments:
            raise UserInputError(
                f"Bootstrap analysis {descriptor.command!r} does not accept arguments.",
                code="invalid-arguments",
                context={"analysis": descriptor.command, "unknownArguments": sorted(arguments)},
            )
        return {}

    handler = descriptor.handler
    signature, hints = _signature_parameters(handler, allow_runtime_overrides=allow_runtime_overrides)
    allowed = {
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    }
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        raise UserInputError(
            f"Unknown argument(s) for {descriptor.command}: {', '.join(unknown)}",
            code="invalid-arguments",
            context={"analysis": descriptor.command, "unknownArguments": unknown, "allowedArguments": sorted(allowed)},
        )
    missing = [
        parameter.name
        for parameter in signature.parameters.values()
        if (
            parameter.name in descriptor.required_arguments
            or parameter.default is inspect.Parameter.empty
        )
        and parameter.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        and parameter.name not in arguments
    ]
    if missing:
        raise UserInputError(
            f"Missing required argument(s) for {descriptor.command}: {', '.join(missing)}",
            code="invalid-arguments",
            context={"analysis": descriptor.command, "missingArguments": missing},
        )
    try:
        bound = signature.bind(**arguments)
    except TypeError as exc:
        raise UserInputError(
            str(exc),
            code="invalid-arguments",
            context={"analysis": descriptor.command},
        ) from exc
    for name, value in bound.arguments.items():
        parameter = signature.parameters[name]
        annotation = hints.get(name, parameter.annotation)
        validate_argument_shape(descriptor, name, value)
        if name in descriptor.required_arguments and value is None:
            raise UserInputError(
                f"Argument {name!r} is required for {descriptor.command!r}.",
                code="invalid-arguments",
                context={"analysis": descriptor.command, "argument": name, "expected": _annotation_text(annotation)},
            )
        choices = _ARGUMENT_CHOICES.get((descriptor.command, name))
        if choices is None:
            choices = _literal_choices(annotation)
        if choices is not None and value is not None and value not in choices:
            raise UserInputError(
                f"Invalid choice for argument {name!r} of {descriptor.command!r}.",
                code="invalid-arguments",
                context={"analysis": descriptor.command, "argument": name, "choices": [_json_value(choice) for choice in choices]},
            )
        if not _type_matches(value, annotation):
            raise UserInputError(
                f"Invalid value for argument {name!r} of {descriptor.command!r}.",
                code="invalid-arguments",
                context={"analysis": descriptor.command, "argument": name, "expected": _annotation_text(annotation), "received": type(value).__name__},
            )
    return dict(bound.arguments)


__all__ = [
    "ANALYSES", "ANALYSIS_REGISTRY", "CALLABLE_ANALYSIS_IDS", "PRIMARY_ANALYSIS_IDS",
    "AnalysisDescriptor", "ArgumentDescriptor", "get_analysis", "get_input_schema",
    "validate_argument_shape", "validate_arguments",
]
