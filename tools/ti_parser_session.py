"""Thin application boundary for one save; domain calculate_* remains authoritative."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from contextlib import contextmanager
from ti_parser_catalogs import runtime_catalog_scope
from ti_parser_topbar import calculate_topbar
from ti_parser_research import calculate_research_ui
from ti_parser_core import load_save, build_index
from ti_parser_compatibility import inspect_save, assess_compatibility, CompatibilityRegistryError
from ti_parser_errors import UserInputError


class AnalysisSession:
    def __init__(self, save_path: Path):
        self._scope_depth = 0
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
        result = {**self.compatibility, "unverifiedAllowed": bool(allow_unverified)}
        if result["status"] != "verified" and not allow_unverified:
            raise UserInputError("Calculation requires verified compatibility or explicit --allow-unverified consent.", code="unverified-compatibility", context={"compatibility": result})
        return result


    @contextmanager
    def calculation_scope(self, *, allow_unverified=False):
        """Reusable lifetime for direct domain calls with this session's index."""
        self.require_calculation(allow_unverified)
        if self._scope_depth:
            yield self.indexed
            return
        with runtime_catalog_scope():
            self._scope_depth += 1
            try:
                yield self.indexed
            finally:
                self._scope_depth -= 1

    def calculate(self, analysis, *, allow_unverified=False, **kwargs):
        """Small application API; other domain functions can use calculation_scope."""
        with self.calculation_scope(allow_unverified=allow_unverified):
            if analysis == "topbar":
                return calculate_topbar(self.indexed, None, **kwargs)
            if analysis == "research-ui":
                return calculate_research_ui(self.indexed, None, **kwargs)
            if analysis == "nation-projection":
                from ti_parser_projection_adapter import calculate_nation_projection
                return calculate_nation_projection(self.indexed, **kwargs)
            raise UserInputError("Unknown application analysis", context={"analysis": analysis})

    def analyze(self, *, allow_unverified=False):
        from ti_parser_analysis import bootstrap_context
        return bootstrap_context(self, allow_unverified=allow_unverified)
