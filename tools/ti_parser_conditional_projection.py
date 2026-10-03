"""Visible-input conditional projection for an explicitly isolated nation model.

This module never loads a save or a save adapter.  It builds a narrow synthetic
state from caller-reported observations, explicit assumptions, and packaged
ModernScenario catalogs, then delegates projection mechanics to the normal
nation projection engine.
"""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

from ti_parser_catalogs import RuntimeCatalogs
from ti_parser_mechanics import mechanic_diagnostics
import ti_parser_nation_projection as projection_engine


CONTEXT_SCHEMA_VERSION = "conditional-nation-v1"
MODEL_ID = "isolated-nation-v1"
SIMULATION_DAYS = 180
_PRIORITIES = ("Knowledge", "Welfare")


def _object(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise projection_engine.ProjectionInputError(f"{name} must be an object")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown:
        raise projection_engine.ProjectionInputError(
            f"{name} contains unsupported keys: {sorted(unknown)}"
        )
    if missing:
        raise projection_engine.ProjectionInputError(
            f"{name} is missing required keys: {sorted(missing)}"
        )
    return value


def _finite_number(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive_minimum: bool = False,
) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise projection_engine.ProjectionInputError(f"{name} must be a finite number")
    result = float(value)
    if minimum is not None and (result <= minimum if exclusive_minimum else result < minimum):
        comparator = "greater than" if exclusive_minimum else "at least"
        raise projection_engine.ProjectionInputError(f"{name} must be {comparator} {minimum}")
    if maximum is not None and result > maximum:
        raise projection_engine.ProjectionInputError(f"{name} must be at most {maximum}")
    return result


def _integer(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise projection_engine.ProjectionInputError(f"{name} must be an integer at least {minimum}")
    if maximum is not None and value > maximum:
        raise projection_engine.ProjectionInputError(f"{name} must be at most {maximum}")
    return value


def _text(value: Any, name: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise projection_engine.ProjectionInputError(
            f"{name} must be a non-empty string of at most {maximum} characters"
        )
    return value.strip()


def _json_safe(value: Any, path: str) -> None:
    """Reject non-JSON values and non-finite numbers in identity metadata."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise projection_engine.ProjectionInputError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_safe(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise projection_engine.ProjectionInputError(f"{path} object keys must be strings")
            _json_safe(item, f"{path}.{key}")
        return
    raise projection_engine.ProjectionInputError(f"{path} contains a non-JSON value")


def _validate_identity(identity: Any) -> dict[str, Any]:
    expected = {
        "schemaVersion", "fingerprint", "gameDate", "scenario", "latestSaveVersion",
        "campaignStartVersion", "campaign", "playerFaction",
    }
    required = {"schemaVersion", "gameDate", "scenario", "campaign", "playerFaction"}
    if not isinstance(identity, dict) or set(identity) - expected or required - set(identity):
        raise projection_engine.ProjectionInputError("peer.saveIdentity fields are invalid")
    _json_safe(identity, "peer.saveIdentity")
    if identity["schemaVersion"] != 1 or isinstance(identity["schemaVersion"], bool):
        raise projection_engine.ProjectionInputError("peer.saveIdentity.schemaVersion must be 1")
    if identity.get("fingerprint") is not None:
        fingerprint = _object(identity["fingerprint"], "peer.saveIdentity.fingerprint", {"algorithm", "value"})
        _text(fingerprint["algorithm"], "peer fingerprint algorithm")
        value = _text(fingerprint["value"], "peer fingerprint value", maximum=256)
        if fingerprint["algorithm"] == "sha256-canonical-save-json-v1" and (
                len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
            raise projection_engine.ProjectionInputError("peer fingerprint value must be a lowercase SHA-256 digest")
    if identity["scenario"] is not None and not isinstance(identity["scenario"], str):
        raise projection_engine.ProjectionInputError("peer.saveIdentity.scenario must be a string or null")
    for field in ("latestSaveVersion", "campaignStartVersion"):
        if identity.get(field) is not None and not isinstance(identity[field], str):
            raise projection_engine.ProjectionInputError(f"peer.saveIdentity.{field} must be a string or null")
    campaign = _object(identity["campaign"], "peer.saveIdentity.campaign", {"realWorldCampaignStart"})
    _json_safe(campaign["realWorldCampaignStart"], "peer.saveIdentity.campaign.realWorldCampaignStart")
    faction = identity["playerFaction"]
    if not isinstance(faction, dict) or faction.get("status") != "resolved":
        raise projection_engine.ProjectionInputError("peer.saveIdentity.playerFaction must be resolved")
    if set(faction) - {"status", "id", "template", "display"} or not {"status", "id", "template"} <= set(faction):
        raise projection_engine.ProjectionInputError("peer player-faction fields are invalid")
    if type(faction["id"]) is not int:
        raise projection_engine.ProjectionInputError("peer player-faction identity requires an id")
    _text(faction["template"], "peer playerFaction.template")
    if faction.get("display") is not None and not isinstance(faction["display"], str):
        raise projection_engine.ProjectionInputError("peer playerFaction.display must be a string or null")
    return identity


def _validate_context(document: Any) -> dict[str, Any]:
    root = _object(
        document,
        "context",
        {"schemaVersion", "model", "assumptionsAcknowledged", "peer", "observations", "assumptions"},
    )
    if root["schemaVersion"] != CONTEXT_SCHEMA_VERSION:
        raise projection_engine.ProjectionInputError(
            f"context.schemaVersion must be {CONTEXT_SCHEMA_VERSION!r}"
        )
    if root["model"] != MODEL_ID:
        raise projection_engine.ProjectionInputError(f"context.model must be {MODEL_ID!r}")
    if root["assumptionsAcknowledged"] is not True:
        raise projection_engine.ProjectionInputError("assumptionsAcknowledged must be true")

    peer = _object(root["peer"], "peer", {"saveIdentity", "selectedNationId"})
    _validate_identity(peer["saveIdentity"])
    if peer["saveIdentity"].get("scenario") != "ModernScenario":
        raise projection_engine.ProjectionInputError("isolated-nation-v1 supports only ModernScenario peer identity")
    selected_nation_id = _integer(peer["selectedNationId"], "peer.selectedNationId")

    observations = _object(root["observations"], "observations", {"source", "precision", "nation"})
    source = _text(observations["source"], "observations.source", maximum=256)
    if observations["precision"] != "reported":
        raise projection_engine.ProjectionInputError("observations.precision must be 'reported'")
    nation = _object(
        observations["nation"],
        "observations.nation",
        {
            "id", "name", "playerFactionId", "asOf", "gdp", "inequality", "education",
            "democracy", "cohesion", "unrest", "sustainability", "militaryTech", "fundingYear",
            "regions", "controlPoints",
        },
    )
    nation_id = _integer(nation["id"], "observations.nation.id")
    if nation_id != selected_nation_id:
        raise projection_engine.ProjectionInputError(
            "peer.selectedNationId must match observations.nation.id"
        )
    nation_name = _text(nation["name"], "observations.nation.name")
    player_faction_id = _integer(nation["playerFactionId"], "observations.nation.playerFactionId")
    identity_faction_id = peer["saveIdentity"]["playerFaction"]["id"]
    try:
        normalized_identity_faction_id = int(identity_faction_id)
    except (TypeError, ValueError):
        normalized_identity_faction_id = -1
    if normalized_identity_faction_id != player_faction_id:
        raise projection_engine.ProjectionInputError(
            "observations.nation.playerFactionId must match peer.saveIdentity.playerFaction.id"
        )
    as_of_text = _text(nation["asOf"], "observations.nation.asOf", maximum=64)
    try:
        as_of = datetime.fromisoformat(as_of_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise projection_engine.ProjectionInputError(
            "observations.nation.asOf must be an ISO 8601 date-time"
        ) from exc
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise projection_engine.ProjectionInputError("observations.nation.asOf must include a UTC offset")
    as_of = as_of.astimezone(timezone.utc).replace(tzinfo=None)

    scalar_ranges = {
        "gdp": (0.0, 1.0e16, True),
        "inequality": (1.0, 9.0, False),
        "education": (1.0, 255.0, False),
        "democracy": (0.0, 10.0, False),
        "cohesion": (0.0, 10.0, False),
        "unrest": (0.0, 10.0, False),
        "sustainability": (0.0, 10.0, False),
        "militaryTech": (0.0, 20.0, False),
        "fundingYear": (0.0, 1.0e9, False),
    }
    observed_values = {
        name: _finite_number(
            nation[name],
            f"observations.nation.{name}",
            minimum=bounds[0],
            maximum=bounds[1],
            exclusive_minimum=bounds[2],
        )
        for name, bounds in scalar_ranges.items()
    }

    raw_regions = nation["regions"]
    if not isinstance(raw_regions, list) or not raw_regions:
        raise projection_engine.ProjectionInputError("observations.nation.regions must be a non-empty array")
    regions: list[dict[str, Any]] = []
    region_ids: set[int] = set()
    region_names: set[str] = set()
    total_population = 0.0
    for index, raw_region in enumerate(raw_regions):
        raw_region = _object(
            raw_region,
            f"observations.nation.regions[{index}]",
            {"id", "name", "template", "populationMillions", "missionControl"},
        )
        region_id = _integer(raw_region["id"], f"regions[{index}].id")
        region_name = _text(raw_region["name"], f"regions[{index}].name")
        template_name = _text(raw_region["template"], f"regions[{index}].template")
        population = _finite_number(
            raw_region["populationMillions"],
            f"regions[{index}].populationMillions",
            minimum=0.0,
            maximum=2000.0,
            exclusive_minimum=True,
        )
        mission_control = _integer(raw_region["missionControl"], f"regions[{index}].missionControl", maximum=1000)
        if region_id in region_ids:
            raise projection_engine.ProjectionInputError(f"Duplicate region id: {region_id}")
        if region_name.casefold() in region_names:
            raise projection_engine.ProjectionInputError(f"Duplicate region name: {region_name}")
        region_ids.add(region_id)
        region_names.add(region_name.casefold())
        total_population += population
        regions.append({
            "id": region_id,
            "name": region_name,
            "template": template_name,
            "populationMillions": population,
            "missionControl": mission_control,
        })
    if total_population > 2000.0:
        raise projection_engine.ProjectionInputError("Total nation population must be at most 2000 million")

    raw_control_points = nation["controlPoints"]
    if not isinstance(raw_control_points, list) or len(raw_control_points) != 6:
        raise projection_engine.ProjectionInputError("observations.nation.controlPoints must contain six entries")
    control_points: list[dict[str, int]] = []
    control_point_ids: set[int] = set()
    positions: set[int] = set()
    for index, raw_cp in enumerate(raw_control_points):
        raw_cp = _object(
            raw_cp,
            f"observations.nation.controlPoints[{index}]",
            {"id", "position", "ownerFactionId"},
        )
        cp_id = _integer(raw_cp["id"], f"controlPoints[{index}].id")
        position = _integer(raw_cp["position"], f"controlPoints[{index}].position", maximum=5)
        owner_id = _integer(raw_cp["ownerFactionId"], f"controlPoints[{index}].ownerFactionId")
        if cp_id in control_point_ids:
            raise projection_engine.ProjectionInputError(f"Duplicate control point id: {cp_id}")
        if position in positions:
            raise projection_engine.ProjectionInputError(f"Duplicate control point position: {position}")
        if owner_id != player_faction_id:
            raise projection_engine.ProjectionInputError(
                "isolated-nation-v1 requires every observed control point to belong to playerFactionId"
            )
        control_point_ids.add(cp_id)
        positions.add(position)
        control_points.append({"id": cp_id, "position": position, "ownerFactionId": owner_id})
    if positions != set(range(6)):
        raise projection_engine.ProjectionInputError("control point positions must be exactly 0 through 5")

    assumptions = _object(
        root["assumptions"],
        "assumptions",
        {
            "daysInCampaign", "currentQuarter", "nationPopulationGrowthModifier", "startTimeTemplate",
            "initialProgress", "world", "regions",
        },
    )
    campaign_age = _finite_number(
        assumptions["daysInCampaign"], "assumptions.daysInCampaign", minimum=0.0, maximum=100000.0
    )
    current_quarter = _integer(assumptions["currentQuarter"], "assumptions.currentQuarter", maximum=10000)
    nation_growth_modifier = _finite_number(
        assumptions["nationPopulationGrowthModifier"],
        "assumptions.nationPopulationGrowthModifier",
        minimum=-100.0,
        maximum=100.0,
    )
    start_time_template = _text(assumptions["startTimeTemplate"], "assumptions.startTimeTemplate")
    initial_progress_raw = _object(assumptions["initialProgress"], "assumptions.initialProgress", set(_PRIORITIES))
    initial_progress = {
        priority: _finite_number(
            initial_progress_raw[priority],
            f"assumptions.initialProgress.{priority}",
            minimum=0.0,
            maximum=100000.0,
        )
        for priority in _PRIORITIES
    }
    world_raw = _object(
        assumptions["world"],
        "assumptions.world",
        {
            "temperatureAnomalyC", "endOfOil", "pcgdpToReduceUnrestByOne", "cohesionFixedImpact",
            "unrestFixedImpact", "initialCohesionRest", "initialUnrestRest",
        },
    )
    world = {
        "temperatureAnomalyC": _finite_number(
            world_raw["temperatureAnomalyC"], "assumptions.world.temperatureAnomalyC", minimum=-100.0, maximum=100.0
        ),
        "endOfOil": world_raw["endOfOil"],
        "pcgdpToReduceUnrestByOne": _finite_number(
            world_raw["pcgdpToReduceUnrestByOne"],
            "assumptions.world.pcgdpToReduceUnrestByOne",
            minimum=0.0,
            maximum=1.0e9,
            exclusive_minimum=True,
        ),
        "cohesionFixedImpact": _finite_number(
            world_raw["cohesionFixedImpact"], "assumptions.world.cohesionFixedImpact", minimum=-100.0, maximum=100.0
        ),
        "unrestFixedImpact": _finite_number(
            world_raw["unrestFixedImpact"], "assumptions.world.unrestFixedImpact", minimum=-100.0, maximum=100.0
        ),
        "initialCohesionRest": _finite_number(
            world_raw["initialCohesionRest"], "assumptions.world.initialCohesionRest", minimum=0.0, maximum=10.0
        ),
        "initialUnrestRest": _finite_number(
            world_raw["initialUnrestRest"], "assumptions.world.initialUnrestRest", minimum=0.0, maximum=10.0
        ),
    }
    if not isinstance(world_raw["endOfOil"], bool):
        raise projection_engine.ProjectionInputError("assumptions.world.endOfOil must be a boolean")

    raw_assumption_regions = assumptions["regions"]
    if not isinstance(raw_assumption_regions, list):
        raise projection_engine.ProjectionInputError("assumptions.regions must be an array")
    assumed_regions: dict[int, dict[str, Any]] = {}
    for index, raw_region in enumerate(raw_assumption_regions):
        raw_region = _object(
            raw_region,
            f"assumptions.regions[{index}]",
            {"id", "annualPopulationGrowthModifier", "xenoformingLevel", "nuclearDetonations"},
        )
        region_id = _integer(raw_region["id"], f"assumptions.regions[{index}].id")
        if region_id in assumed_regions:
            raise projection_engine.ProjectionInputError(f"Duplicate region assumption id: {region_id}")
        assumed_regions[region_id] = {
            "annualPopulationGrowthModifier": _finite_number(
                raw_region["annualPopulationGrowthModifier"],
                f"assumptions.regions[{index}].annualPopulationGrowthModifier",
                minimum=-100.0,
                maximum=100.0,
            ),
            "xenoformingLevel": _finite_number(
                raw_region["xenoformingLevel"],
                f"assumptions.regions[{index}].xenoformingLevel",
                minimum=0.0,
                maximum=20.0,
            ),
            "nuclearDetonations": _integer(
                raw_region["nuclearDetonations"],
                f"assumptions.regions[{index}].nuclearDetonations",
                maximum=1000,
            ),
        }
    if set(assumed_regions) != region_ids:
        raise projection_engine.ProjectionInputError(
            "assumptions.regions ids must match observations.nation.regions exactly"
        )

    return {
        "peer": peer,
        "observations": {
            "source": source,
            "precision": "reported",
            "nation": {
                **observed_values,
                "id": nation_id,
                "name": nation_name,
                "playerFactionId": player_faction_id,
                "asOf": as_of,
                "asOfText": as_of_text,
                "regions": regions,
                "controlPoints": control_points,
            },
        },
        "assumptions": {
            "daysInCampaign": campaign_age,
            "currentQuarter": current_quarter,
            "nationPopulationGrowthModifier": nation_growth_modifier,
            "startTimeTemplate": start_time_template,
            "initialProgress": initial_progress,
            "world": world,
            "regions": assumed_regions,
        },
    }


def _catalog_region_geometry(
    template_name: str,
    region_templates: Mapping[str, Mapping[str, Any]],
    map_templates: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    region_template = region_templates.get(template_name)
    if not isinstance(region_template, Mapping):
        raise projection_engine.ProjectionInputError(
            f"Region template is absent from ModernScenario public catalog: {template_name}"
        )
    map_name = region_template.get("mapRegionName")
    map_template = map_templates.get(map_name) if isinstance(map_name, str) else None
    if not isinstance(map_template, Mapping):
        raise projection_engine.ProjectionInputError(
            f"Region template has no packaged map geography: {template_name}"
        )
    for field_name in ("latitude", "longitude"):
        value = map_template.get(field_name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
        ):
            raise projection_engine.ProjectionInputError(
                f"Packaged map geography is missing {field_name}: {template_name}"
            )
    if region_template.get("environment") not in {"Standard", "Beneficiary", "Vulnerable"}:
        raise projection_engine.ProjectionInputError(
            f"Packaged region environment is missing or unsupported: {template_name}"
        )
    if not isinstance(region_template.get("mineCapable"), bool) or not isinstance(region_template.get("oilCapable"), bool):
        raise projection_engine.ProjectionInputError(
            f"Packaged region capability flags are incomplete: {template_name}"
        )
    return region_template, map_template


def _input_provenance(
    normalized: Mapping[str, Any],
    expanded_assumptions: Mapping[str, Any],
    catalog_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    observations = normalized["observations"]
    nation = observations["nation"]
    source = observations["source"]
    field_sources: dict[str, dict[str, str]] = {}
    for field in (
        "id", "name", "playerFactionId", "asOf", "gdp", "inequality", "education", "democracy",
        "cohesion", "unrest", "sustainability", "militaryTech", "fundingYear",
    ):
        path = f"/observations/nation/{field}"
        field_sources[path] = {"kind": "callerReportedObservation", "precision": "reported", "source": source}
    for region in nation["regions"]:
        for field in ("id", "name", "template", "populationMillions", "missionControl"):
            path = f"/observations/nation/regions/{region['id']}/{field}"
            field_sources[path] = {"kind": "callerReportedObservation", "precision": "reported", "source": source}
        field_sources[f"/observations/nation/regions/{region['id']}/geography"] = {
            "kind": "packagedPublicCatalog", "catalog": "ModernScenario.nationDevelopment.mapRegionTemplates"
        }
    for cp in nation["controlPoints"]:
        for field in ("id", "position", "ownerFactionId"):
            path = f"/observations/nation/controlPoints/{cp['position']}/{field}"
            field_sources[path] = {"kind": "callerReportedObservation", "precision": "reported", "source": source}
    assumption_paths = [
        "/assumptions/daysInCampaign", "/assumptions/currentQuarter",
        "/assumptions/nationPopulationGrowthModifier", "/assumptions/startTimeTemplate",
        "/assumptions/initialProgress/Knowledge", "/assumptions/initialProgress/Welfare",
    ]
    for field in normalized["assumptions"]["world"]:
        assumption_paths.append(f"/assumptions/world/{field}")
    for region_id, values in normalized["assumptions"]["regions"].items():
        assumption_paths.extend(f"/assumptions/regions/{region_id}/{field}" for field in values)
    return {
        "peer": copy.deepcopy(normalized["peer"]),
        "observations": {"source": source, "precision": "reported", "fields": field_sources},
        "assumptions": {
            "acknowledged": True,
            "model": MODEL_ID,
            "submitted": {
                "daysInCampaign": normalized["assumptions"]["daysInCampaign"],
                "currentQuarter": normalized["assumptions"]["currentQuarter"],
                "nationPopulationGrowthModifier": normalized["assumptions"]["nationPopulationGrowthModifier"],
                "startTimeTemplate": normalized["assumptions"]["startTimeTemplate"],
                "initialProgress": copy.deepcopy(normalized["assumptions"]["initialProgress"]),
                "world": copy.deepcopy(normalized["assumptions"]["world"]),
                "regions": [
                    {"id": region_id, **copy.deepcopy(values)}
                    for region_id, values in sorted(normalized["assumptions"]["regions"].items())
                ],
            },
            "fieldSources": {
                path: {"kind": "callerDeclaredAssumption", "model": MODEL_ID}
                for path in assumption_paths
            },
            "expanded": copy.deepcopy(expanded_assumptions),
        },
        "catalogs": copy.deepcopy(dict(catalog_diagnostics)),
    }


def build_conditional_state(
    document: Any,
) -> tuple[
    projection_engine.NationProjectionState,
    projection_engine.ProjectionContext,
    dict[str, Any],
]:
    """Build a fresh synthetic state without consulting a save or save adapter."""

    normalized = _validate_context(document)
    catalogs = RuntimeCatalogs.load("ModernScenario")
    development = catalogs.nation_development
    priorities = development.get("priorities")
    global_config = development.get("globalConfig")
    region_templates = development.get("regionTemplates")
    map_templates = development.get("mapRegionTemplates")
    start_templates = development.get("startTimeTemplates")
    diversity_bonuses = development.get("diversityBonuses")
    if not all(isinstance(value, dict) for value in (
        priorities, global_config, region_templates, map_templates, start_templates, diversity_bonuses,
    )):
        raise projection_engine.ProjectionInputError("ModernScenario packaged nation development catalog is incomplete")
    missing_priorities = set(_PRIORITIES) - set(priorities)
    if missing_priorities:
        raise projection_engine.ProjectionInputError(
            f"ModernScenario catalog lacks required priorities: {sorted(missing_priorities)}"
        )

    assumptions = normalized["assumptions"]
    for priority in _PRIORITIES:
        cost = priorities[priority].get("investmentCost")
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or not math.isfinite(cost) or cost <= 0:
            raise projection_engine.ProjectionInputError("Priority completion cost is unavailable")
        if assumptions["initialProgress"][priority] >= cost:
            raise projection_engine.ProjectionInputError("Initial progress must precede the next completion")
    start_template_name = assumptions["startTimeTemplate"]
    start_template = start_templates.get(start_template_name)
    if not isinstance(start_template, Mapping):
        raise projection_engine.ProjectionInputError(
            f"startTimeTemplate is absent from ModernScenario catalog: {start_template_name}"
        )
    regression_years = start_template.get("populationRegressionPeriod_years")
    if not isinstance(regression_years, (int, float)) or isinstance(regression_years, bool) or regression_years <= 0:
        raise projection_engine.ProjectionInputError(
            f"startTimeTemplate has no valid population regression period: {start_template_name}"
        )

    obs_nation = normalized["observations"]["nation"]
    player_faction_id = obs_nation["playerFactionId"]
    region_states: dict[int, projection_engine.RegionProjectionState] = {}
    expanded_region_assumptions: list[dict[str, Any]] = []
    for order, observation in enumerate(obs_nation["regions"]):
        assumption = assumptions["regions"][observation["id"]]
        template, map_template = _catalog_region_geometry(
            observation["template"], region_templates, map_templates
        )
        expanded_region_assumptions.append({
            "id": observation["id"],
            "annualPopulationGrowthModifier": assumption["annualPopulationGrowthModifier"],
            "xenoformingLevel": assumption["xenoformingLevel"],
            "nuclearDetonations": assumption["nuclearDetonations"],
            "resourceRegion": False,
            "oilRegion": False,
            "coreEconomicRegion": False,
            "colony": False,
            "permanentColony": False,
            "fullyOccupied": False,
            "boostPerYear": 0.0,
            "welfareColonyCounter": None,
            "economyRegionCounters": {},
            "latitude": float(map_template["latitude"]),
            "longitude": float(map_template["longitude"]),
            "environment": template["environment"],
            "mineCapable": template["mineCapable"],
            "oilCapable": template["oilCapable"],
        })
        region_states[observation["id"]] = projection_engine.RegionProjectionState(
            id=observation["id"],
            population_millions=observation["populationMillions"],
            boost_per_year=0.0,
            mission_control=observation["missionControl"],
            annual_population_growth_modifier=assumption["annualPopulationGrowthModifier"],
            region_order=order,
            template_name=observation["template"],
            latitude=float(map_template["latitude"]),
            longitude=float(map_template["longitude"]),
            environment=str(template["environment"]),
            xenoforming_level=assumption["xenoformingLevel"],
            nuclear_detonations=assumption["nuclearDetonations"],
            colony=False,
            permanent_colony=False,
            resource_region=False,
            oil_region=False,
            core_economic_region=False,
            mine_capable=bool(template["mineCapable"]),
            oil_capable=bool(template["oilCapable"]),
            capital=False,
            occupation_fraction=0.0,
            fully_occupied=False,
            anti_space_defenses=False,
            num_sto_fighters=0,
            welfare_colony_counter=None,
            economy_region_counters={},
        )

    cp_states = {
        cp["id"]: projection_engine.ControlPointProjectionState(
            id=cp["id"],
            position=cp["position"],
            owner_faction_id=cp["ownerFactionId"],
            benefits_disabled=False,
            control_point_type=None,
            pips={"Knowledge": 0, "Welfare": 0},
            priority_bonuses={"Knowledge": 0.0, "Welfare": 0.0},
        )
        for cp in obs_nation["controlPoints"]
    }
    region_count = len(region_states)
    if region_count == 0:
        raise projection_engine.ProjectionInputError("At least one region is required")
    total_mission_control = sum(region.mission_control for region in region_states.values())
    world = assumptions["world"]
    state = projection_engine.NationProjectionState(
        nation_id=obs_nation["id"],
        at=obs_nation["asOf"],
        gdp=obs_nation["gdp"],
        inequality=obs_nation["inequality"],
        education=obs_nation["education"],
        democracy=obs_nation["democracy"],
        cohesion=obs_nation["cohesion"],
        cohesion_rest=world["initialCohesionRest"],
        unrest=obs_nation["unrest"],
        unrest_rest=world["initialUnrestRest"],
        sustainability=obs_nation["sustainability"],
        military_tech=obs_nation["militaryTech"],
        funding_year=obs_nation["fundingYear"],
        economy_score=0.0,
        occupation_factor=1.0,
        army_maintenance=0.0,
        progress=dict(assumptions["initialProgress"]),
        regions=region_states,
        control_points=cp_states,
        advisors=(),
        mission_control=total_mission_control,
        army_count=0,
        navy_count=0,
        nuclear_weapons=0,
        space_defenses=0,
        sto_fighters=0,
        days_in_campaign=assumptions["daysInCampaign"],
        current_quarter=assumptions["currentQuarter"],
        pcgdp_tracker={},
        military=False,
        cached_can_accumulate_legitimize=False,
        cached_can_accumulate_decontaminate=False,
        cached_can_accumulate_decolonize=False,
        best_current_sustainability_value=None,
        max_military_tech_level=None,
        policy_no_nukes=False,
        space_flight_program=False,
        federation_space_program=False,
        nuclear_program=False,
        can_build_space_defenses=False,
        can_build_sto=False,
        num_control_points_unclamped=6,
        legitimize_counter=0.0,
        hostile_region_ids=set(),
        hostile_region_ids_complete=True,
        executive_faction_id=player_faction_id,
        public_opinion_context={},
        public_opinion={},
        public_opinion_expected_transition=False,
        rest_state_context={
            "sourceBacked": False,
            "provenance": "explicitConditionalAssumption",
            "cohesionFixedImpact": world["cohesionFixedImpact"],
            "unrestFixedImpact": world["unrestFixedImpact"],
            "pcgdpToReduceUnrestBy1": world["pcgdpToReduceUnrestByOne"],
            "wars": [],
            "rivals": [],
            "neighbors": [],
            "alienHabSurveillanceStrength": 0.0,
            "alliedArmies": [],
            "alienNation": False,
        },
        armies=[],
        world_market={},
        world_context={
            "temperatureAnomaly_C": world["temperatureAnomalyC"],
            "endOfOil": world["endOfOil"],
            "pcgdpToReduceUnrestBy1": world["pcgdpToReduceUnrestByOne"],
            "resourceMarketValues": {},
        },
        world_context_provenance="explicitConditionalAssumption",
        population_mean_path=False,
        federation_economy_bonus=0.0,
        in_federation=False,
        cached_num_mining_regions=0,
        cached_num_oil_regions=0,
        cached_num_core_economic_regions=0,
        cached_can_accumulate_core_economy=False,
        cached_can_accumulate_core_mining=False,
        cached_can_accumulate_core_oil=False,
        policy_no_oil_development=False,
        policy_no_mineral_development=False,
        world_market_blockers={"marketValuesNotSuppliedInIsolatedNationV1"},
        faction_effect_contexts={player_faction_id: {}},
        faction_effect_expirations={player_faction_id: {}},
        faction_priority_bonus_cache={player_faction_id: {"Knowledge": 0.0, "Welfare": 0.0}},
        advisor_policy=(),
        advisor_mission_schedule=None,
        advisor_current_phase_assignments=(),
        advisor_assignment_prepaid_ids=frozenset(),
    )
    context = projection_engine.ProjectionContext(
        faction_id=player_faction_id,
        priorities=priorities,
        global_config=global_config,
        diversity_bonuses=diversity_bonuses,
        national_ip_multiplier=1.0,
        initial_funding_pool_year=obs_nation["fundingYear"],
        initial_own_funding_year=obs_nation["fundingYear"],
        initial_boost_pool_year=0.0,
        knowledge_sector_owned=False,
        financial_sector_owned=False,
        knowledge_sector_bonus=1.0,
        financial_sector_bonus=1.0,
        research_effect_factor=1.0,
        nation_template={"popGrowthModifier": assumptions["nationPopulationGrowthModifier"]},
        region_templates=region_templates,
        start_template=start_template,
        faction_priority_modifiers={player_faction_id: {}},
        faction_ideologies={},
        ideology_templates=development.get("ideologyTemplates") or {},
        permanent_allies={player_faction_id: (player_faction_id,)},
        faction_effect_contexts={player_faction_id: {}},
        effect_templates=catalogs.effects,
        faction_priority_bonus_bases={player_faction_id: {"Knowledge": 0.0, "Welfare": 0.0}},
    )
    projection_engine._refresh_economy_score(state, context)

    expanded_assumptions = {
        "model": MODEL_ID,
        "acknowledged": True,
        "simulationDays": SIMULATION_DAYS,
        "campaignAgeDays": assumptions["daysInCampaign"],
        "currentQuarter": assumptions["currentQuarter"],
        "nationPopulationGrowthModifier": assumptions["nationPopulationGrowthModifier"],
        "startTimeTemplate": {
            "name": start_template_name,
            "populationRegressionPeriod_years": float(regression_years),
            "source": "packagedModernScenarioCatalog",
        },
        "initialProgress": dict(assumptions["initialProgress"]),
        "world": dict(world),
        "regions": expanded_region_assumptions,
        "controlPoints": [
            {
                "id": cp["id"],
                "position": cp["position"],
                "ownerFactionId": cp["ownerFactionId"],
                "benefitsDisabled": False,
                "controlPointType": None,
                "initialPips": {"Knowledge": 0, "Welfare": 0},
            }
            for cp in obs_nation["controlPoints"]
        ],
        "namedModelConstants": {
            "allControlPointsOwnedBySubject": True,
            "armyCount": 0,
            "navyCount": 0,
            "nuclearWeapons": 0,
            "spaceDefenses": 0,
            "stoFighters": 0,
            "inFederation": False,
            "federationEconomyBonus": 0.0,
            "federationSpaceProgram": False,
            "rivalWarNeighbors": [],
            "alienHabSurveillanceStrength": 0.0,
            "hostileClaims": [],
            "factionEffects": {},
            "priorityBonuses": {"Knowledge": 0.0, "Welfare": 0.0},
            "advisors": [],
            "advisorMissionSchedule": None,
            "colonies": [],
            "resourceInstallations": [],
            "oilInstallations": [],
            "coreEconomicRegions": [],
            "fullyOccupiedRegions": [],
            "hostileRegionIdsComplete": True,
            "publicOpinionDistribution": {},
            "publicOpinionCohesionImpact": 0.0,
            "pcgdpTracker": {},
            "boostPerRegionYear": 0.0,
            "nationalInvestmentPointMultiplier": 1.0,
            "initialOccupationFactor": 1.0,
            "initialArmyMaintenance": 0.0,
            "knowledgeSectorOwned": False,
            "financialSectorOwned": False,
            "knowledgeSectorBonus": 1.0,
            "financialSectorBonus": 1.0,
            "researchEffectFactor": 1.0,
            "initialOwnFundingPoolYear": obs_nation["fundingYear"],
            "initialFederationFundingPoolYear": obs_nation["fundingYear"],
            "initialBoostPoolYear": 0.0,
            "worldMarketValues": None,
            "worldMarketStatus": "not supplied; corresponding engine metrics remain blocked",
            "military": False,
            "spaceFlightProgram": False,
            "nuclearProgram": False,
            "canBuildSpaceDefenses": False,
            "canBuildSTO": False,
            "policyNoNukes": False,
            "numControlPointsUnclamped": 6,
            "legitimizeCounter": 0.0,
            "populationMeanPath": False,
        },
    }
    diagnostics = catalogs.calculation_diagnostics()
    provenance = _input_provenance(normalized, expanded_assumptions, diagnostics)
    return state, context, provenance


def _parse_plans(value: Any, state: projection_engine.NationProjectionState) -> tuple[projection_engine.PriorityPlan, ...]:
    if not isinstance(value, list) or not 2 <= len(value) <= 8:
        raise projection_engine.ProjectionInputError("plans must be an array containing 2 to 8 plans")
    plans: list[projection_engine.PriorityPlan] = []
    names: set[str] = set()
    for index, raw_plan in enumerate(value):
        raw_plan = _object(raw_plan, f"plans[{index}]", {"name", "pips"})
        name = _text(raw_plan["name"], f"plans[{index}].name", maximum=80)
        if name in names:
            raise projection_engine.ProjectionInputError(f"Duplicate plan name: {name}")
        names.add(name)
        pips_raw = _object(raw_plan["pips"], f"plans[{index}].pips", set(_PRIORITIES))
        pips = {
            priority: _integer(pips_raw[priority], f"plans[{index}].pips.{priority}", maximum=3)
            for priority in _PRIORITIES
        }
        if sum(pips.values()) <= 0:
            raise projection_engine.ProjectionInputError(f"plans[{index}] must allocate at least one Knowledge/Welfare pip")
        policies = tuple(
            projection_engine.ControlPointPolicy(cp.id, dict(pips))
            for cp in sorted(state.control_points.values(), key=lambda item: item.position)
        )
        plans.append(projection_engine.PriorityPlan(
            name,
            (projection_engine.PlanSegment(None, None, policies, None),),
        ))
    return tuple(plans)


def _summary_counts(values: list[Any]) -> list[dict[str, Any]]:
    """Count public labels without retaining the engine's repeated event rows."""

    counts = Counter(values)
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (item[0] is None, str(item[0])))
    ]


def _summarize_rule_executions(value: Any) -> dict[str, Any]:
    """Summarize execution records by rule and coverage/provenance status.

    The engine's rule records intentionally carry no event day.  This result
    keeps that limitation explicit instead of inferring timing from adjacent
    transactions.
    """

    executions = value if isinstance(value, list) else []
    grouped: dict[str | None, list[Mapping[str, Any]]] = {}
    for row in executions:
        if not isinstance(row, Mapping):
            continue
        rule_id = row.get("ruleId")
        if rule_id is not None and not isinstance(rule_id, str):
            rule_id = str(rule_id)
        grouped.setdefault(rule_id, []).append(row)
    by_rule = []
    for rule_id, rows in sorted(grouped.items(), key=lambda item: (item[0] is None, str(item[0]))):
        by_rule.append({
            "ruleId": rule_id,
            "count": len(rows),
            "coverageCounts": _summary_counts([row.get("effectiveCoverage") for row in rows]),
            "provenanceCounts": _summary_counts([row.get("provenance") for row in rows]),
            "lastDay": None,
        })
    return {
        "totalCount": len(executions),
        "eventDayAvailability": "not-reported-by-engine",
        "byRule": by_rule,
    }


def _summarize_completions(value: Any) -> dict[str, Any]:
    """Summarize repeated priority completions without exposing transaction logs."""

    completions = value if isinstance(value, list) else []
    grouped: dict[str | None, list[Mapping[str, Any]]] = {}
    for row in completions:
        if not isinstance(row, Mapping):
            continue
        priority = row.get("priority")
        if priority is not None and not isinstance(priority, str):
            priority = str(priority)
        grouped.setdefault(priority, []).append(row)
    by_priority = []
    for priority, rows in sorted(grouped.items(), key=lambda item: (item[0] is None, str(item[0]))):
        days = [row["day"] for row in rows if type(row.get("day")) is int]
        by_priority.append({
            "priority": priority,
            "count": len(rows),
            "statusCounts": _summary_counts([row.get("effectiveCoverage") for row in rows]),
            "firstDay": min(days) if days else None,
            "lastDay": max(days) if days else None,
        })
    return {"totalCount": len(completions), "byPriority": by_priority}


def _intern_metric_coverage(
    value: Any,
    records: list[dict[str, Any]],
    record_indexes: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """Reference full per-metric coverage evidence through a deduplicated table."""

    if not isinstance(value, Mapping):
        return {}
    references: dict[str, dict[str, Any]] = {}
    for metric, raw in value.items():
        if not isinstance(raw, Mapping):
            continue
        record = copy.deepcopy(dict(raw))
        signature = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        index = record_indexes.get(signature)
        if index is None:
            index = len(records)
            record_indexes[signature] = index
            records.append(record)
        references[str(metric)] = {
            "coverage": copy.deepcopy(raw.get("coverage")),
            "evidenceIndex": index,
        }
    return references


def _compact_engine_projection(
    result: Mapping[str, Any],
    metric_coverage_references: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Bound the public conditional payload while retaining states and coverage."""

    compact = {
        key: copy.deepcopy(value)
        for key, value in result.items()
        if key not in {"status", "coverage", "ruleExecutions", "completionEvents"}
    }
    compact["metricCoverage"] = copy.deepcopy(dict(metric_coverage_references))
    compact["executionSummary"] = _summarize_rule_executions(result.get("ruleExecutions", []))
    compact["completionSummary"] = _summarize_completions(result.get("completionEvents", []))
    return compact


def _conditional_priority_coverage(value: Any) -> dict[str, Any]:
    """Expose coverage only for priorities admitted by this conditional API."""

    if not isinstance(value, Mapping):
        return {}
    return {
        priority: copy.deepcopy(value[priority])
        for priority in _PRIORITIES
        if priority in value
    }


def calculate_conditional_projection(document: Any, plans: Any) -> dict[str, Any]:
    """Project narrow Knowledge/Welfare plans over the fixed 180-day scenario."""

    state, context, provenance = build_conditional_state(document)
    parsed_plans = _parse_plans(plans, state)
    plan_results: list[dict[str, Any]] = []
    metric_coverage_records: list[dict[str, Any]] = []
    metric_coverage_record_indexes: dict[str, int] = {}
    used_rule_ids: set[str] = set()
    for plan in parsed_plans:
        result = projection_engine.run_projection(
            state,
            plan,
            context,
            days=SIMULATION_DAYS,
            checkpoints=(0, SIMULATION_DAYS),
            details=False,
        )
        engine_status = str(result.get("status", "incomplete"))
        used_rule_ids.update(str(rule_id) for rule_id in result.get("mechanicRuleIds", []))
        coverage = _conditional_priority_coverage(result.get("coverage", {}))
        metric_coverage_references = _intern_metric_coverage(
            result.get("metricCoverage", {}),
            metric_coverage_records,
            metric_coverage_record_indexes,
        )
        result_without_engine_status = _compact_engine_projection(result, metric_coverage_references)
        plan_results.append({
            "name": plan.name,
            "status": "conditional-complete" if engine_status == "complete" else "conditional-incomplete",
            "engineStatus": engine_status,
            "engineCoverageWithinConditionalScenario": coverage,
            "engineProjection": result_without_engine_status,
        })

    return {
        "schemaVersion": "conditional-nation-projection-result-v1",
        "status": "complete" if all(row["engineStatus"] == "complete" for row in plan_results) else "incomplete",
        "interpretation": "conditionalScenario",
        "authoritativeGameOutcome": False,
        "exactGameOutcome": False,
        "engineCoverageScope": "Mechanics coverage is reported only within this conditional scenario.",
        "simulationDays": SIMULATION_DAYS,
        "peer": copy.deepcopy(provenance["peer"]),
        "inputProvenance": provenance,
        "assumptions": copy.deepcopy(provenance["assumptions"]["expanded"]),
        "catalogs": copy.deepcopy(provenance["catalogs"]),
        "priorityCoverageScope": (
            "Only Knowledge and Welfare coverage is included; all other priorities are outside this accepted plan domain."
        ),
        "metricCoverageEncoding": (
            "Each plan engineProjection.metricCoverage entry contains its coverage label and an evidenceIndex "
            "into this table; each table record is the complete original engine metric-coverage record."
        ),
        "metricCoverageRecords": metric_coverage_records,
        "plans": plan_results,
        "mechanicRuleIds": sorted(used_rule_ids),
        "mechanicRuleDiagnostics": mechanic_diagnostics(used_rule_ids),
    }


def _number_schema(minimum: float | None = None, maximum: float | None = None, *, exclusive_minimum: bool = False) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "number"}
    if minimum is not None:
        schema["exclusiveMinimum" if exclusive_minimum else "minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


def _save_identity_schema() -> dict[str, Any]:
    date_properties = {
        name: {"type": "integer", "minimum": 0}
        for name in ("year", "month", "day", "hour", "minute", "second", "millisecond")
    }
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": 1},
            "fingerprint": {
                "type": ["object", "null"],
                "properties": {
                    "algorithm": {"type": "string", "minLength": 1},
                    "value": {"type": "string", "minLength": 1, "maxLength": 256},
                },
                "required": ["algorithm", "value"],
                "additionalProperties": False,
            },
            "gameDate": {
                "oneOf": [
                    {"type": "string", "format": "date-time"},
                    {
                        "type": "object",
                        "properties": date_properties,
                        "required": ["year", "month", "day"],
                        "additionalProperties": False,
                    },
                ]
            },
            "scenario": {"type": ["string", "null"]},
            "latestSaveVersion": {"type": ["string", "null"]},
            "campaignStartVersion": {"type": ["string", "null"]},
            "campaign": {
                "type": "object",
                "properties": {"realWorldCampaignStart": {}},
                "required": ["realWorldCampaignStart"],
                "additionalProperties": False,
            },
            "playerFaction": {
                "type": "object",
                "properties": {
                    "status": {"const": "resolved"},
                    "id": {"type": "integer"},
                    "template": {"type": "string", "minLength": 1},
                    "display": {"type": ["string", "null"]},
                },
                "required": ["status", "id", "template"],
                "additionalProperties": False,
            },
        },
        "required": [
            "schemaVersion", "gameDate", "scenario", "campaign", "playerFaction",
        ],
        "additionalProperties": False,
    }


def get_context_schema() -> dict[str, Any]:
    """Return the strict input schema for the visible-input scenario context."""

    region_observation = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "name": {"type": "string", "minLength": 1, "maxLength": 160},
            "template": {"type": "string", "minLength": 1, "maxLength": 160},
            "populationMillions": _number_schema(0, 2000, exclusive_minimum=True),
            "missionControl": {"type": "integer", "minimum": 0, "maximum": 1000},
        },
        "required": ["id", "name", "template", "populationMillions", "missionControl"],
        "additionalProperties": False,
    }
    control_point = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "position": {"type": "integer", "minimum": 0, "maximum": 5},
            "ownerFactionId": {"type": "integer", "minimum": 0},
        },
        "required": ["id", "position", "ownerFactionId"],
        "additionalProperties": False,
    }
    region_assumption = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "minimum": 0},
            "annualPopulationGrowthModifier": _number_schema(-100, 100),
            "xenoformingLevel": _number_schema(0, 20),
            "nuclearDetonations": {"type": "integer", "minimum": 0, "maximum": 1000},
        },
        "required": ["id", "annualPopulationGrowthModifier", "xenoformingLevel", "nuclearDetonations"],
        "additionalProperties": False,
    }
    nation_scalar_limits = {
        "gdp": _number_schema(0, 1.0e16, exclusive_minimum=True),
        "inequality": _number_schema(1, 9),
        "education": _number_schema(1, 255),
        "democracy": _number_schema(0, 10),
        "cohesion": _number_schema(0, 10),
        "unrest": _number_schema(0, 10),
        "sustainability": _number_schema(0, 10),
        "militaryTech": _number_schema(0, 20),
        "fundingYear": _number_schema(0, 1.0e9),
    }
    nation_properties: dict[str, Any] = {
        "id": {"type": "integer", "minimum": 0},
        "name": {"type": "string", "minLength": 1, "maxLength": 160},
        "playerFactionId": {"type": "integer", "minimum": 0},
        "asOf": {"type": "string", "format": "date-time"},
        **nation_scalar_limits,
        "regions": {"type": "array", "minItems": 1, "items": region_observation},
        "controlPoints": {"type": "array", "minItems": 6, "maxItems": 6, "items": control_point},
    }
    world_properties = {
        "temperatureAnomalyC": _number_schema(-100, 100),
        "endOfOil": {"type": "boolean"},
        "pcgdpToReduceUnrestByOne": _number_schema(0, 1.0e9, exclusive_minimum=True),
        "cohesionFixedImpact": _number_schema(-100, 100),
        "unrestFixedImpact": _number_schema(-100, 100),
        "initialCohesionRest": _number_schema(0, 10),
        "initialUnrestRest": _number_schema(0, 10),
    }
    return {
        "type": "object",
        "properties": {
            "schemaVersion": {"const": CONTEXT_SCHEMA_VERSION},
            "model": {"const": MODEL_ID},
            "assumptionsAcknowledged": {"const": True},
            "peer": {
                "type": "object",
                "properties": {
                    "saveIdentity": _save_identity_schema(),
                    "selectedNationId": {"type": "integer", "minimum": 0},
                },
                "required": ["saveIdentity", "selectedNationId"],
                "additionalProperties": False,
            },
            "observations": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "minLength": 1, "maxLength": 256},
                    "precision": {"const": "reported"},
                    "nation": {
                        "type": "object",
                        "properties": nation_properties,
                        "required": list(nation_properties),
                        "additionalProperties": False,
                    },
                },
                "required": ["source", "precision", "nation"],
                "additionalProperties": False,
            },
            "assumptions": {
                "type": "object",
                "properties": {
                    "daysInCampaign": _number_schema(0, 100000),
                    "currentQuarter": {"type": "integer", "minimum": 0, "maximum": 10000},
                    "nationPopulationGrowthModifier": _number_schema(-100, 100),
                    "startTimeTemplate": {"type": "string", "minLength": 1, "maxLength": 160},
                    "initialProgress": {
                        "type": "object",
                        "properties": {key: _number_schema(0, 100000) for key in _PRIORITIES},
                        "required": list(_PRIORITIES),
                        "additionalProperties": False,
                    },
                    "world": {
                        "type": "object",
                        "properties": world_properties,
                        "required": list(world_properties),
                        "additionalProperties": False,
                    },
                    "regions": {
                        "type": "array",
                        "minItems": 1,
                        "items": region_assumption,
                    },
                },
                "required": [
                    "daysInCampaign", "currentQuarter", "nationPopulationGrowthModifier", "startTimeTemplate",
                    "initialProgress", "world", "regions",
                ],
                "additionalProperties": False,
            },
        },
        "required": [
            "schemaVersion", "model", "assumptionsAcknowledged", "peer", "observations", "assumptions",
        ],
        "additionalProperties": False,
    }


def get_plans_schema() -> dict[str, Any]:
    """Return the strict JSON schema for 2–8 identical-across-six-CP plans."""

    return {
        "type": "array",
        "minItems": 2,
        "maxItems": 8,
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 80},
                "pips": {
                    "type": "object",
                    "properties": {
                        "Knowledge": {"type": "integer", "minimum": 0, "maximum": 3},
                        "Welfare": {"type": "integer", "minimum": 0, "maximum": 3},
                    },
                    "required": list(_PRIORITIES),
                    "additionalProperties": False,
                    "description": "Each entry applies the same Knowledge/Welfare pips to all six control points; total must be positive.",
                },
            },
            "required": ["name", "pips"],
            "additionalProperties": False,
        },
    }


__all__ = [
    "build_conditional_state",
    "calculate_conditional_projection",
    "get_context_schema",
    "get_plans_schema",
]
