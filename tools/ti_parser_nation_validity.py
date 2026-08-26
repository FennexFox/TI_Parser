"""Shared value-only nation priority validity contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ALWAYS_VALID_PRIORITIES = frozenset({
    "Economy", "Welfare", "Environment", "Knowledge", "Unity", "Oppression",
    "Spoils", "LaunchFacilities", "Military",
})


@dataclass(frozen=True)
class PriorityValidityResult:
    valid: bool | None
    reason: str
    dependencies: tuple[dict[str, Any], ...] = ()

    def output(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "dependencies": [dict(value) for value in self.dependencies],
        }


def _unknown(*fields: str, reason: str = "required validity input is unavailable") -> PriorityValidityResult:
    return PriorityValidityResult(
        None,
        reason,
        tuple({"field": field, "source": "nationPriorityValidity"} for field in fields),
    )


def _boolean(view: Mapping[str, Any], field: str) -> bool | None:
    value = view.get(field)
    return value if isinstance(value, bool) else None


def _number(view: Mapping[str, Any], field: str) -> float | None:
    value = view.get(field)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def evaluate_priority_validity(priority: str, view: Mapping[str, Any]) -> PriorityValidityResult:
    """Evaluate only validity; callers precompute mechanics-specific derived inputs."""

    if priority in ALWAYS_VALID_PRIORITIES:
        return PriorityValidityResult(True, "always valid for an existing nation")
    if priority == "Government":
        democracy = _number(view, "democracy")
        hostile = _boolean(view, "hasHostileRegion")
        if democracy is None or hostile is None:
            return _unknown(*(
                field for field, value in (("democracy", democracy), ("hasHostileRegion", hostile))
                if value is None
            ))
        valid = democracy < 10.0 or hostile
        return PriorityValidityResult(valid, "below democracy cap or hostile-region legitimize target exists" if valid else "democracy is capped and no legitimize target exists")
    if priority == "Funding":
        funding = _number(view, "fundingYear")
        gdp = _number(view, "gdp")
        if funding is None or gdp is None:
            return _unknown(*(
                field for field, value in (("fundingYear", funding), ("gdp", gdp)) if value is None
            ))
        valid = funding < 0.005 * (gdp / 1_000_000.0)
        return PriorityValidityResult(valid, "funding remains below its GDP-derived cap" if valid else "funding reached its GDP-derived cap")
    if priority == "MissionControl":
        program = _boolean(view, "spaceFlightProgram")
        candidate = _boolean(view, "missionControlHasCapacity")
        if program is None or candidate is None:
            return _unknown(*(
                field for field, value in (("spaceFlightProgram", program), ("missionControlHasCapacity", candidate))
                if value is None
            ))
        valid = program and candidate
        return PriorityValidityResult(valid, "spaceflight exists and regional MC capacity remains" if valid else "spaceflight or regional MC capacity is unavailable")
    if priority == "Military_BuildArmy":
        allowed = _number(view, "allowedArmies")
        current = _number(view, "currentArmies")
        if allowed is None or current is None:
            return _unknown(*(
                field for field, value in (("allowedArmies", allowed), ("currentArmies", current)) if value is None
            ))
        valid = allowed > current
        return PriorityValidityResult(valid, "army capacity remains" if valid else "army capacity is full")
    if priority == "Military_FoundMilitary":
        military = _boolean(view, "military")
        return _unknown("military") if military is None else PriorityValidityResult(not military, "military capability is absent" if not military else "military already exists")
    if priority == "Civilian_InitiateSpaceflightProgram":
        program = _boolean(view, "spaceFlightProgram")
        return _unknown("spaceFlightProgram") if program is None else PriorityValidityResult(not program, "spaceflight program is absent" if not program else "spaceflight program already exists")
    if priority == "Military_InitiateNuclearProgram":
        military = _boolean(view, "military")
        nuclear = _boolean(view, "nuclearProgram")
        if military is None or nuclear is None:
            return _unknown(*(
                field for field, value in (("military", military), ("nuclearProgram", nuclear)) if value is None
            ))
        valid = military and not nuclear
        return PriorityValidityResult(valid, "military exists and nuclear program is absent" if valid else "military prerequisite or nuclear-program state blocks initiation")
    if priority == "Military_BuildNuclearWeapons":
        nuclear = _boolean(view, "nuclearProgram")
        return _unknown("nuclearProgram") if nuclear is None else PriorityValidityResult(nuclear, "nuclear program exists" if nuclear else "nuclear program is absent")
    if priority == "Military_BuildSpaceDefenses":
        military = _boolean(view, "military")
        capability = _boolean(view, "canBuildSpaceDefenses")
        if military is None or capability is None:
            return _unknown(*(
                field for field, value in (("military", military), ("canBuildSpaceDefenses", capability)) if value is None
            ))
        valid = military and capability
        return PriorityValidityResult(valid, "space-defense prerequisites are satisfied" if valid else "space-defense prerequisites are not satisfied")
    if priority == "Military_BuildSTOSquadron":
        military = _boolean(view, "military")
        capability = _boolean(view, "canBuildSTO")
        boost = _boolean(view, "hasBoostRegion")
        if military is None or capability is None or boost is None:
            return _unknown(*(
                field for field, value in (("military", military), ("canBuildSTO", capability), ("hasBoostRegion", boost))
                if value is None
            ))
        valid = military and capability and boost
        return PriorityValidityResult(valid, "STO prerequisites are satisfied" if valid else "STO prerequisites are not satisfied")
    return _unknown("priority", reason=f"priority validity is not modeled: {priority}")
