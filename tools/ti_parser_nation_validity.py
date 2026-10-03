"""Shared value-only nation priority validity contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


ALWAYS_VALID_PRIORITIES = frozenset({
    "Economy", "Welfare", "Knowledge", "Unity", "Spoils",
})

# Audited from TINationState.canBuildNavy in Assembly-CSharp.dll.  These are
# compiled mechanics values, not save- or template-provided catalog data.
MIN_CONTROL_POINTS_FOR_NAVY = 4
MIN_CONTROL_POINTS_FOR_NAVY_EXCEPTION = 3
PCGDP_FOR_NAVY_EXCEPTION = 40_000.0


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


def can_build_navy(view: Mapping[str, Any]) -> bool | None:
    """Return the DLL's ``TINationState.canBuildNavy`` predicate, or unknown.

    ``armyCount`` is the full live standard-army list and ``navyCount`` is its
    Naval subset.  Therefore ``armyCount > navyCount`` exactly represents the
    game's requirement for at least one convertible non-naval army.
    """

    military = _boolean(view, "military")
    fields = {
        name: _number(view, name)
        for name in (
            "armyCount",
            "navyCount",
            "coastalRegions",
            "controlPointCount",
            "perCapitaGDP",
            "minControlPointsForNavy",
            "minControlPointsForNavyException",
            "pcgdpForNavyException",
        )
    }
    if military is None or any(value is None for value in fields.values()):
        return None
    return bool(
        military
        and fields["armyCount"] > fields["navyCount"]
        and fields["coastalRegions"] > 0
        and (
            fields["controlPointCount"] >= fields["minControlPointsForNavy"]
            or (
                fields["controlPointCount"] == fields["minControlPointsForNavyException"]
                and fields["perCapitaGDP"] >= fields["pcgdpForNavyException"]
                and fields["navyCount"] == 0
            )
        )
    )


def evaluate_priority_validity(priority: str, view: Mapping[str, Any]) -> PriorityValidityResult:
    """Evaluate only validity; callers precompute mechanics-specific derived inputs."""

    if priority in ALWAYS_VALID_PRIORITIES:
        return PriorityValidityResult(True, "always valid for an existing nation")
    if priority == "Government":
        democracy = _number(view, "democracy")
        can_legitimize = _boolean(view, "canAccumulateLegitimizeClaimTriggers")
        if democracy is not None and democracy < 10.0:
            return PriorityValidityResult(True, "democracy is below the cap")
        if can_legitimize is True:
            return PriorityValidityResult(True, "cached legitimize-claim triggers are available")
        if democracy is None or can_legitimize is None:
            return _unknown(*(
                field for field, value in (
                    ("democracy", democracy),
                    ("canAccumulateLegitimizeClaimTriggers", can_legitimize),
                ) if value is None
            ))
        return PriorityValidityResult(False, "democracy is capped and cached legitimize-claim triggers are unavailable")
    if priority == "Environment":
        sustainability = _number(view, "sustainability")
        best_sustainability = _number(view, "bestCurrentSustainabilityValue")
        can_decontaminate = _boolean(view, "canAccumulateDecontaminateTriggers")
        if can_decontaminate is True:
            return PriorityValidityResult(True, "cached decontaminate triggers are available")
        if sustainability is not None and sustainability <= 0.0:
            return PriorityValidityResult(True, "sustainability is at or below zero")
        if sustainability is not None and best_sustainability is not None and sustainability > best_sustainability:
            return PriorityValidityResult(True, "sustainability is above the current best value")
        if sustainability is None or best_sustainability is None or can_decontaminate is None:
            return _unknown(*(
                field for field, value in (
                    ("sustainability", sustainability),
                    ("bestCurrentSustainabilityValue", best_sustainability),
                    ("canAccumulateDecontaminateTriggers", can_decontaminate),
                ) if value is None
            ))
        return PriorityValidityResult(False, "sustainability is at its current best and no cached decontaminate trigger is available")
    if priority == "Oppression":
        military = _boolean(view, "military")
        return _unknown("military") if military is None else PriorityValidityResult(
            military,
            "military capability exists" if military else "military capability is absent",
        )
    if priority == "Military":
        military = _boolean(view, "military")
        if military is False:
            return PriorityValidityResult(False, "military capability is absent")
        if military is None:
            return _unknown("military")
        current = _number(view, "militaryTechLevel")
        maximum = _number(view, "maxMilitaryTechLevel")
        if current is None or maximum is None:
            return _unknown(*(
                field for field, value in (
                    ("militaryTechLevel", current),
                    ("maxMilitaryTechLevel", maximum),
                ) if value is None
            ))
        valid = current < maximum
        return PriorityValidityResult(valid, "military technology is below its cap" if valid else "military technology reached its cap")
    if priority == "LaunchFacilities":
        program = _boolean(view, "spaceFlightProgram")
        federation = _boolean(view, "federationSpaceProgram")
        if program is True or federation is True:
            return PriorityValidityResult(True, "the nation or federation has a space program")
        if program is None or federation is None:
            return _unknown(*(
                field for field, value in (
                    ("spaceFlightProgram", program),
                    ("federationSpaceProgram", federation),
                ) if value is None
            ))
        return PriorityValidityResult(
            federation,
            "federation has a space program" if federation else "neither nation nor federation has a space program",
        )
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
        if candidate is False:
            return PriorityValidityResult(False, "regional mission-control capacity is full")
        if program is False:
            federation = _boolean(view, "federationSpaceProgram")
            if federation is False:
                return PriorityValidityResult(False, "spaceflight is unavailable to the nation and federation")
            if federation is None:
                return _unknown("federationSpaceProgram")
        elif program is None:
            federation = _boolean(view, "federationSpaceProgram")
            if federation is not True:
                return _unknown(*(
                    field for field, value in (
                        ("spaceFlightProgram", program),
                        ("federationSpaceProgram", federation),
                    ) if value is None
                ))
        if candidate is None:
            return _unknown("missionControlHasCapacity")
        return PriorityValidityResult(
            candidate,
            "regional mission-control capacity remains" if candidate else "regional mission-control capacity is full",
        )
    if priority == "Military_BuildArmy":
        military = _boolean(view, "military")
        allowed = _number(view, "allowedArmies")
        current = _number(view, "currentArmies")
        if military is False:
            return PriorityValidityResult(False, "military capability is absent")
        if allowed is not None and current is not None and allowed <= current:
            return PriorityValidityResult(False, "army capacity is full")
        if military is None or allowed is None or current is None:
            return _unknown(*(
                field for field, value in (
                    ("military", military),
                    ("allowedArmies", allowed),
                    ("currentArmies", current),
                ) if value is None
            ))
        valid = allowed > current
        return PriorityValidityResult(valid, "army capacity remains" if valid else "army capacity is full")
    if priority == "Military_BuildNavy":
        valid = _boolean(view, "canBuildNavy")
        return _unknown("canBuildNavy") if valid is None else PriorityValidityResult(
            valid,
            "navy prerequisites are satisfied" if valid else "navy prerequisites are not satisfied",
        )
    if priority == "Military_FoundMilitary":
        military = _boolean(view, "military")
        return _unknown("military") if military is None else PriorityValidityResult(not military, "military capability is absent" if not military else "military already exists")
    if priority == "Civilian_InitiateSpaceflightProgram":
        program = _boolean(view, "spaceFlightProgram")
        return _unknown("spaceFlightProgram") if program is None else PriorityValidityResult(not program, "spaceflight program is absent" if not program else "spaceflight program already exists")
    if priority == "Military_InitiateNuclearProgram":
        military = _boolean(view, "military")
        nuclear = _boolean(view, "nuclearProgram")
        no_nukes = _boolean(view, "policy_noNukes")
        if military is False or nuclear is True or no_nukes is True:
            reason = (
                "military capability is absent" if military is False else
                "a nuclear program already exists" if nuclear is True else
                "no-nukes policy blocks initiation"
            )
            return PriorityValidityResult(False, reason)
        if military is None or nuclear is None or no_nukes is None:
            return _unknown(*(
                field for field, value in (
                    ("military", military),
                    ("nuclearProgram", nuclear),
                    ("policy_noNukes", no_nukes),
                ) if value is None
            ))
        return PriorityValidityResult(True, "military exists, no nuclear program exists, and policy permits nukes")
    if priority == "Military_BuildNuclearWeapons":
        nuclear = _boolean(view, "nuclearProgram")
        no_nukes = _boolean(view, "policy_noNukes")
        if nuclear is False or no_nukes is True:
            return PriorityValidityResult(False, "nuclear program or policy blocks weapon construction")
        if nuclear is None or no_nukes is None:
            return _unknown(*(
                field for field, value in (
                    ("nuclearProgram", nuclear), ("policy_noNukes", no_nukes),
                ) if value is None
            ))
        return PriorityValidityResult(True, "nuclear program exists and policy permits nukes")
    if priority == "Military_BuildSpaceDefenses":
        military = _boolean(view, "military")
        capability = _boolean(view, "canBuildSpaceDefenses")
        complete = _boolean(view, "completeAntiSpaceDefenses")
        if military is False or capability is False or complete is True:
            reason = (
                "military capability is absent" if military is False else
                "space-defense capability is absent" if capability is False else
                "all regions have anti-space defenses"
            )
            return PriorityValidityResult(False, reason)
        if military is None or capability is None or complete is None:
            return _unknown(*(
                field for field, value in (
                    ("military", military),
                    ("canBuildSpaceDefenses", capability),
                    ("completeAntiSpaceDefenses", complete),
                ) if value is None
            ))
        return PriorityValidityResult(True, "at least one region lacks anti-space defenses")
    if priority == "Military_BuildSTOSquadron":
        military = _boolean(view, "military")
        capability = _boolean(view, "canBuildSTO")
        boost = _number(view, "rawBoostPerYear_dekatons")
        capacity = _boolean(view, "hasSTOFighterCapacity")
        if military is False or capability is False or (boost is not None and boost <= 0.0) or capacity is False:
            reason = (
                "military capability is absent" if military is False else
                "STO capability is absent" if capability is False else
                "nation has no annual boost" if boost is not None and boost <= 0.0 else
                "no region has STO fighter capacity"
            )
            return PriorityValidityResult(False, reason)
        if military is None or capability is None or boost is None or capacity is None:
            return _unknown(*(
                field for field, value in (
                    ("military", military),
                    ("canBuildSTO", capability),
                    ("rawBoostPerYear_dekatons", boost),
                    ("hasSTOFighterCapacity", capacity),
                ) if value is None
            ))
        return PriorityValidityResult(True, "all STO squadron prerequisites are satisfied")
    return _unknown("priority", reason=f"priority validity is not modeled: {priority}")
