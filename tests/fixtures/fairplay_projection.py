"""Small ModernScenario save input for the developer projection read audit.

This intentionally contains only the state rows needed to run the real public
projection adapter against the repository's packaged runtime catalogs.
"""

from __future__ import annotations


def ref(state_id: int) -> dict[str, int]:
    return {"value": state_id}


def row(state_id: int, **fields: object) -> dict[str, object]:
    return {"Key": ref(state_id), "Value": {"ID": ref(state_id), **fields}}


def make_save_data() -> dict[str, object]:
    """Return a controlled, fully-owned ModernScenario projection fixture."""

    nation_id, region_id = 20, 100
    point_ids = list(range(31, 37))
    faction_id, player_id = 2, 3
    gamestates: dict[str, list[dict[str, object]]] = {
        "TITimeState": [
            row(
                1,
                scenarioMetaTemplateName="ModernScenario",
                templateName="ModernDayStart",
                currentDateTime={"year": 2035, "month": 1, "day": 10},
                daysInCampaign=3300,
                currentQuarterSinceStart=36,
            )
        ],
        "TIFactionState": [
            row(
                faction_id,
                templateName="ResistCouncil",
                displayName="Resistance",
                isHumanPlayer=True,
                player=ref(player_id),
                resources={
                    "Money": 1000.0,
                    "Boost": 0.0,
                    "MissionControl": 0.0,
                    "Research": 0.0,
                    "Influence": 0.0,
                    "Ops": 0.0,
                },
                baseIncomes_year={"Research": 0.0},
                councilors=[],
                habSectors=[],
                controlPoints=[ref(point_id) for point_id in point_ids],
                habitats=[],
                fleets=[],
                researchWeights=[0, 0, 0, 0, 0, 0],
                currentProjectProgress=[],
                availableProjectNames=[],
                finishedProjectNames=[],
                missionControlUsage=0.0,
                showMonthlyIncomesInTopBarAndIntel=True,
            ),
            row(8, templateName="AlienCouncil", displayName="Aliens", habSectors=[]),
        ],
        "TIPlayerState": [row(player_id, faction=ref(faction_id), isAI=False)],
        "TIEffectsState": [row(4, effects=[])],
        "TIGlobalResearchState": [row(5, techProgress=[], finishedTechsNames=[])],
        "TITimeEvent": [
            row(
                7,
                eventName="CouncilorMissionUpdate",
                triggerTime={"year": 2035, "month": 1, "day": 17},
                repeatType="WeekToMonth",
                repeatChangeTriggered=[],
            )
        ],
        "TIGlobalValuesState": [
            row(
                6,
                earthAtmosphericCO2_ppm=420.0,
                earthAtmosphericCH4_ppm=1.9,
                earthAtmosphericN2O_ppm=0.34,
                stratosphericAerosols_ppm=0.0,
                fixedPCGDPToReduceUnrestBy1=10_000.0,
                resourceMarketValues={"Metals": 1.0, "NobleMetals": 1.0},
                endOfOil=False,
            )
        ],
        "TINationState": [
            row(
                nation_id,
                templateName="USA",
                displayName="United States",
                GDP=29_000_000_000_000.0,
                economyScore=9.5,
                inequality=3.0,
                education=12.0,
                democracy=8.0,
                alienNation=False,
                cohesion=5.0,
                cohesionRestState_dailyCache=5.0,
                unrest=0.0,
                unrestRestState_dailyCache=0.0,
                sustainability=4.0,
                militaryTechLevel=5.0,
                spaceFunding_year=120.0,
                military=True,
                spaceFlightProgram=True,
                nuclearProgram=True,
                canBuildSpaceDefenses=True,
                canBuildSTOSquadrons=True,
                numControlPoints=6,
                numControlPoints_unclamped=6,
                controlPoints=[ref(point_id) for point_id in point_ids],
                regions=[ref(region_id)],
                capital=ref(region_id),
                armies=[],
                allies=[],
                rivals=[],
                wars=[],
                currentWarStates=[],
                adjacentNations=[],
                baseInvestmentPoints_month=9.5,
                advisingCouncilors=[],
                _accumulatedInvestmentPoints={},
                hostileClaims=[],
                publicOpinion={"Resist": 1.0, "Undecided": 0.0},
                tracker_PCGDP_ByQuarter=[{"Key": 36, "Value": 725_000.0}],
                numNuclearWeapons=0,
                accumulatedLegitimizeClaimTriggers=0,
                restofFederationECOBonus_dailyCache=0.0,
                numMiningRegions_dailyCache=0,
                numOilRegions_dailyCache=0,
                numCoreEconomicRegions_dailyCache=1,
                canAccumulateCoreEconomyTriggers=True,
                canAccumulateCoreMiningTriggers=True,
                canAccumulateCoreOilTriggers=True,
                policy_noOilDevelopment=False,
                policy_noMineralDevelopment=False,
                canAccumulateLegitimizeClaimTriggers=False,
                canAccumulateDecontaminateTriggers=False,
                maxMilitaryTechLevel=5.0,
                policy_noNukes=False,
            )
        ],
        "TIControlPointState": [
            row(
                point_id,
                positionInNation=position,
                controlPointType="Government",
                faction=ref(faction_id),
                nation=ref(nation_id),
                benefitsDisabled=False,
                controlPointPriorities={"Knowledge": 3, "Welfare": 1},
                totalWeightsForControlPoint=4,
                numPrioritiesWithWeight=2,
                diversityBonus={},
            )
            for position, point_id in enumerate(point_ids)
        ],
        "TIRegionState": [
            row(
                region_id,
                templateName="California",
                displayName="California",
                nation=ref(nation_id),
                populationInMillions=40.0,
                boostPerYear_dekatons=0.0,
                missionControl=4,
                oceanType="None",
                annualPopGrowthModifier=0.0,
                nuclearDetonations=0,
                colonyRegion=False,
                permanentlyDecolonized=False,
                resourceRegion=False,
                oilRegion=False,
                coreEconomicRegion=True,
                accumulatedDecolonizeTriggers=0,
                accumulatedCoreEconomyRegionTriggers=0,
                accumulatedCoreMiningRegionTriggers=0,
                accumulatedCoreOilRegionTriggers=0,
                occupations=[],
                xenoforming=ref(101),
                spaceDefenseFacility=None,
                numSTOFighters=0,
                antiSpaceDefenses=False,
                leadOccupier=None,
            )
        ],
        "TIXenoformingState": [row(101, xenoformingLevel=0.0)],
    }
    return {"currentID": ref(1000), "gamestates": gamestates}
