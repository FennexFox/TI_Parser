"""Thin application boundary for one save; domain calculate_* remains authoritative."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from ti_parser_core import load_save, build_index
from ti_parser_compatibility import inspect_save, assess_compatibility, CompatibilityRegistryError
from ti_parser_errors import UserInputError


class AnalysisSession:
    def __init__(self, save_path: Path):
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
