import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_parser_hab as hab_layer
import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


def build_parity_fixture():
    gamestates = {}
    faction_id = 1
    councilor_id = 2
    org_id = 3
    hab_id = 10
    sector_id = 11
    module_id = 12

    faction = add_state(
        gamestates,
        "TIFactionState",
        faction_id,
        {
            "templateName": "ResistCouncil",
            "displayName": "Resistance",
            "habSectors": [ref(sector_id)],
        },
    )
    add_state(
        gamestates,
        "TICouncilorState",
        councilor_id,
        {
            "displayName": "Support Councilor",
            "detained": False,
            "isAlien": False,
            "orgs": [ref(org_id)],
        },
    )
    add_state(
        gamestates,
        "TIOrgState",
        org_id,
        {
            "displayName": "Mining Org",
            "applyingBonuses": True,
            "miningBonus": 0.25,
        },
    )
    add_state(
        gamestates,
        "TIHabModuleState",
        module_id,
        {
            "templateName": "CoreModule",
            "constructionCompleted": True,
            "powered": True,
            "destroyed": False,
            "decommissioning": False,
        },
    )
    add_state(
        gamestates,
        "TISectorState",
        sector_id,
        {
            "sectorNum": 0,
            "faction": ref(faction_id),
            "hab": ref(hab_id),
            "habModules": [ref(module_id)],
        },
    )
    hab = add_state(
        gamestates,
        "TIHabState",
        hab_id,
        {
            "displayName": "Parity Hab",
            "habType": "Station",
            "tier": 1,
            "faction": ref(faction_id),
            "sectors": [ref(sector_id)],
            "habSite": None,
            "anyCoreCompleted": True,
            "inEarthLEO": True,
        },
    )
    indexed = ti.build_index({"gamestates": gamestates})
    templates = {
        "CoreModule": {
            "dataName": "CoreModule",
            "friendlyName": "Core Module",
            "coreModule": True,
            "crew": 4,
            "incomeMoney_month": 9.0,
            "supportMaterials_month": {"money": 1.0},
            "controlPointCapacity": 2.0,
        }
    }
    return indexed, faction, hab, templates


class HabParserParityTests(unittest.TestCase):
    def test_direct_module_matches_wrapper_calls_for_representative_helpers(self):
        indexed, faction, hab, templates = build_parity_fixture()

        records_direct = hab_layer.hab_module_records(indexed, hab, templates)
        records_wrapper = ti.hab_module_records(indexed, hab, templates)
        self.assertEqual(records_wrapper, records_direct)

        mining_direct = hab_layer.faction_active_org_mining_bonus(
            indexed,
            faction,
            ti.faction_councilor_ids,
        )
        mining_wrapper = ti.faction_active_org_mining_bonus(indexed, faction)
        self.assertEqual(mining_wrapper, mining_direct)

        monthly_direct = hab_layer.hab_monthly_resource_income(
            hab,
            records_direct,
            "Money",
            1.0,
            indexed=indexed,
            faction=faction,
            config=ti.HAB_CONFIG,
            faction_councilor_ids=ti.faction_councilor_ids,
        )
        monthly_wrapper = ti.hab_monthly_resource_income(
            hab,
            records_wrapper,
            "Money",
            1.0,
            indexed=indexed,
            faction=faction,
        )
        self.assertEqual(monthly_wrapper, monthly_direct)

        capacity_direct = hab_layer.hab_control_point_capacity(hab, records_direct)
        capacity_wrapper = ti.hab_control_point_capacity(hab, records_wrapper)
        self.assertEqual(capacity_wrapper, capacity_direct)


if __name__ == "__main__":
    unittest.main()
