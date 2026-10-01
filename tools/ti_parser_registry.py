"""Central registry for the reusable machine-facing analysis boundary.

The application handlers are the source of executable behavior. This module
owns stable metadata and resolves handlers lazily from
``ti_parser_application.HANDLERS`` so importing the registry never imports the
application layer recursively.
"""

from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Union, get_args, get_origin, get_type_hints

from ti_parser_errors import UserInputError


_NO_DEFAULT = object()
_BOOTSTRAP_IDS = frozenset({"inspect-save", "analyze"})
_RUNTIME_OVERRIDE_NAMES = frozenset({"research_templates", "base_daily_cache"})
_ALWAYS_PRIVATE_NAMES = frozenset({"templates_dir", "templates", "runtime_catalogs", "claim_catalog"})


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
        return _signature_arguments(self.handler, required_arguments=self.required_arguments)

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
# application-callable, input kind, required caller selectors)
_METADATA: tuple[tuple[Any, ...], ...] = (
    ("inspect-save", "Identify save, campaign and player without calculations", "observed-state", False, "bootstrap", True, "session", ()),
    ("analyze", "Bounded LLM bootstrap context and next analysis routes", "bootstrap-context", False, "bootstrap", True, "session", ()),
    ("summary", "Compact campaign summary", "reconstructed-state", True, "primary", True, "snapshot", ()),
    ("faction", "Faction summary", "reconstructed-state", True, "primary", True, "snapshot", ("name",)),
    ("nation", "Nation summary", "reconstructed-state", True, "primary", True, "snapshot", ("name",)),
    ("councilor", "Councilor attributes and conditions", "reconstructed-state", True, "primary", True, "snapshot", ("name",)),
    ("topbar", "Resource income, MC and CP capacity; optional queue forecast", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("research", "Research income breakdown", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("research-ui", "Active research slots, progress and ETA", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("research-plan", "Research candidates and goal-specific evidence", "planning-evidence", True, "primary", True, "indexed", ()),
    ("org-plan", "Organization acquisition and assignment evidence", "planning-evidence", True, "primary", True, "indexed", ()),
    ("hab-ui", "Habitat power, modules and support", "reconstructed-state", True, "primary", True, "indexed", ("hab_name",)),
    ("hab-slots", "Usable habitat slots", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("hab-plan", "Habitat module candidates and expansion evidence", "planning-evidence", True, "primary", True, "indexed", ()),
    ("ship-plan", "Ship component choices and design simulations", "planning-evidence", True, "primary", True, "indexed", ()),
    ("project-analysis", "Project unlocks and resource tradeoffs", "planning-evidence", True, "primary", True, "indexed", ()),
    ("nation-ui", "Nation priorities and displayed metrics", "reconstructed-state", True, "primary", True, "indexed", ("nation_name",)),
    ("nation-claims", "Claims and reconstructed hostility", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("nation-projection", "Audited conditional nation projection", "simulation", True, "primary", True, "indexed", ("nation_name", "days")),
    ("advise", "Hypothetical councilor advice contribution", "simulation", True, "primary", True, "indexed", ("councilor_name", "nation_name")),
    ("world-ui", "World population, climate and markets", "reconstructed-state", True, "primary", True, "indexed", ()),
    ("ai-fleet-diagnostics", "AI goals and unresolved causes", "reconstructed-state", True, "diagnostic", True, "indexed", ()),
    ("raw", "Selected raw save fields", "observed-state", False, "advanced", False, "indexed", ()),
    ("types", "Save state type counts", "observed-state", False, "advanced", False, "indexed", ()),
    ("export", "Export calculated compact snapshot", "maintenance", True, "maintenance", False, "snapshot", ()),
    ("cache", "Build or validate calculated snapshot cache", "maintenance", True, "maintenance", False, "indexed", ()),
    ("catalog-verify", "Audit packaged catalogs against explicit game sources", "maintenance", False, "maintenance", False, "session", ()),
    ("capabilities", "Machine-readable analysis inventory", "inventory", False, "inventory", False, "session", ()),
)


def _make_descriptor(row: tuple[Any, ...]) -> AnalysisDescriptor:
    command, purpose, kind, requires_verified, routing_class, application_callable, input_kind, required_arguments = row
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
                choices=_literal_choices(annotation),
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
        if name in descriptor.required_arguments and value is None:
            raise UserInputError(
                f"Argument {name!r} is required for {descriptor.command!r}.",
                code="invalid-arguments",
                context={"analysis": descriptor.command, "argument": name, "expected": _annotation_text(annotation)},
            )
        choices = _literal_choices(annotation)
        if choices is not None and value not in choices:
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
    "AnalysisDescriptor", "ArgumentDescriptor", "get_analysis", "validate_arguments",
]
