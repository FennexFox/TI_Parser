"""Thin application boundary for one save; domain calculate_* remains authoritative."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from contextlib import contextmanager
from ti_parser_catalogs import runtime_catalog_scope, CatalogError
from ti_parser_core import (load_save, build_index, CalculationDependencyError,
                            ModuleCatalogError, LocationCatalogError, SolarPowerDataError)
from ti_parser_compatibility import inspect_save, assess_compatibility, CompatibilityRegistryError
from ti_parser_errors import UserInputError


class AnalysisSession:
    def __init__(self, save_path: Path):
        self._catalog_cache = {}
        self.save_path = Path(save_path)
        self.indexed = build_index(load_save(self.save_path))

    @cached_property
    def facts(self):
        return inspect_save(self.indexed, self.save_path)

    @cached_property
    def compatibility(self):
        return assess_compatibility(self.indexed)

    def inspect(self):
        result = dict(self.facts)
        try:
            result["compatibility"] = self.compatibility
        except CompatibilityRegistryError as exc:
            result["compatibility"] = {"status": "unverified", "reasons": [{"code": exc.code}]}
        return result

    def require_calculation(self, allow_unverified=False):
        if type(allow_unverified) is not bool:
            raise UserInputError("allow_unverified must be a boolean", code="invalid-arguments")
        result = {**self.compatibility, "unverifiedAllowed": allow_unverified}
        if result["status"] != "verified" and not allow_unverified:
            raise UserInputError("Calculation requires verified compatibility or explicit --allow-unverified consent.", code="unverified-compatibility", context={"compatibility": result})
        return result


    @contextmanager
    def calculation_scope(self, *, allow_unverified=False):
        """Reusable lifetime for direct domain calls with this session's index."""
        self.require_calculation(allow_unverified)
        with runtime_catalog_scope(cache=self._catalog_cache):
            yield self.indexed

    def calculate(self, analysis, *, allow_unverified=False, **kwargs):
        """Return the shared analysis payload; expected failures remain exceptions."""
        from ti_parser_registry import get_analysis, validate_arguments
        from ti_parser_application import dispatch
        entry = get_analysis(analysis)
        validate_arguments(entry, kwargs, allow_runtime_overrides=True)
        if not entry.requires_verified_compatibility:
            raise UserInputError("Use run() for inspection and bootstrap analyses", context={"analysis": analysis})
        with self.calculation_scope(allow_unverified=allow_unverified):
            source = self._snapshot if entry.input_kind == "snapshot" else self.indexed
            return dispatch(analysis, source, **kwargs)

    @cached_property
    def _snapshot(self):
        from ti_parser_snapshot import build_snapshot
        from ti_parser_config import SNAPSHOT_CONFIG
        return build_snapshot(self.save_path, self.indexed.data, None, SNAPSHOT_CONFIG, indexed=self.indexed)

    def run(self, analysis_id, *, allow_unverified=False, **kwargs):
        """Versioned machine result retaining save context on expected failures."""
        from ti_parser_registry import get_analysis, validate_arguments
        from ti_parser_version import __version__
        from ti_parser_nation_projection import ProjectionInputError
        envelope = {"schemaVersion": 1, "parserVersion": __version__,
                    "analysis": analysis_id, "saveIdentity": self.facts["saveIdentity"],
                    "compatibility": {**self.inspect()["compatibility"],
                                      "unverifiedAllowed": allow_unverified is True}}
        try:
            if type(allow_unverified) is not bool:
                raise UserInputError("allow_unverified must be a boolean", code="invalid-arguments")
            entry = get_analysis(analysis_id)
            forbidden = {"research_templates", "base_daily_cache"} & kwargs.keys()
            if forbidden:
                raise UserInputError("Machine analyses do not accept runtime overrides",
                                     context={"arguments": sorted(forbidden)})
            validate_arguments(entry, kwargs)
            if analysis_id == "inspect-save":
                result = self.inspect()
            elif analysis_id == "analyze":
                result = self.analyze(allow_unverified=allow_unverified)
            else:
                result = self.calculate(analysis_id, allow_unverified=allow_unverified, **kwargs)
            envelope.update(status=result_status(result), result=result)
        except CalculationDependencyError as exc:
            envelope.update(status="incomplete", missingDependencies=exc.missing_dependencies)
        except CompatibilityRegistryError as exc:
            envelope.update(status="incomplete", error=exc.to_dict())
        except UserInputError as exc:
            envelope.update(status="deferred" if exc.code == "unverified-compatibility" else "error", error=exc.to_dict())
        except (CatalogError, ModuleCatalogError, LocationCatalogError, SolarPowerDataError) as exc:
            envelope.update(status="incomplete", error={"code": "calculation-input-error", "message": str(exc)})
        except (ProjectionInputError, OSError) as exc:
            envelope.update(status="error", error={"code": "invalid-input", "message": str(exc)})
        return envelope

    def analyze(self, *, allow_unverified=False):
        if type(allow_unverified) is not bool:
            raise UserInputError("allow_unverified must be a boolean", code="invalid-arguments")
        from ti_parser_analysis import bootstrap_context
        return bootstrap_context(self, allow_unverified=allow_unverified)


def result_status(result):
    """Report completion conservatively without rewriting domain evidence."""
    if not isinstance(result, dict):
        return "complete"
    status = result.get("status")
    if status in {"deferred", "error"}:
        return status
    # Projection returns a comparison containing per-plan execution results,
    # rather than a single top-level completion flag.
    if "plans" in result and "comparison" in result:
        if any(result_status(plan) != "complete" for plan in result["plans"]):
            return "incomplete"
    scopes = result.get("scopeStatus", {})
    if (status in {"incomplete", "partial", "unsupported"} or result.get("complete") is False
            or result.get("missingDependencies")
            or any(row.get("status") in {"incomplete", "partial", "unsupported"}
                   for row in scopes.values() if isinstance(row, dict))):
        return "incomplete"
    return "complete"
