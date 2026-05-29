import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import ti_save_parser as ti


def ref(state_id):
    return {"value": state_id}


def add_state(gamestates, type_name, state_id, value):
    value = dict(value)
    value.setdefault("ID", ref(state_id))
    gamestates.setdefault(type_name, []).append({"Key": ref(state_id), "Value": value})
    return value


def build_hab_fixture(*, tier, owned_sector_count, occupied_slots):
    gamestates = {}
    faction_id = 1
    hab_id = 10
    next_id = 100
    sector_slot_counts = [5, 4, 4, 4, 4]
    sector_refs = []
    owned_sector_refs = []
    templates = {}
    remaining_occupied = occupied_slots

    for sector_num, slot_count in enumerate(sector_slot_counts):
        sector_id = next_id
        next_id += 1
        module_refs = []
        sector_owned = sector_num < owned_sector_count
        for slot in range(slot_count):
            module_id = next_id
            next_id += 1
            template_name = ""
            if remaining_occupied > 0:
                template_name = f"Module{module_id}"
                templates[template_name] = {"dataName": template_name, "friendlyName": template_name}
                remaining_occupied -= 1
            add_state(
                gamestates,
                "TIHabModuleState",
                module_id,
                {
                    "templateName": template_name,
                    "constructionCompleted": bool(template_name),
                    "powered": bool(template_name),
                    "destroyed": False,
                    "decommissioning": False,
                },
            )
            module_refs.append(ref(module_id))

        sector = add_state(
            gamestates,
            "TISectorState",
            sector_id,
            {
                "sectorNum": sector_num,
                "faction": ref(faction_id) if sector_owned else None,
                "hab": ref(hab_id),
                "habModules": module_refs,
            },
        )
        sector_refs.append(ref(sector_id))
        if sector_owned:
            owned_sector_refs.append(ref(sector_id))

    add_state(
        gamestates,
        "TIFactionState",
        faction_id,
        {
            "templateName": "ResistCouncil",
            "displayName": "Resistance",
            "habSectors": owned_sector_refs,
        },
    )
    hab = add_state(
        gamestates,
        "TIHabState",
        hab_id,
        {
            "displayName": f"Tier {tier} test hab",
            "habType": "Station",
            "tier": tier,
            "faction": ref(faction_id),
            "sectors": sector_refs,
        },
    )
    indexed = ti.build_index({"gamestates": gamestates})
    return indexed, hab, templates


class HabSlotSummaryTests(unittest.TestCase):
    def assert_slot_summary(self, tier, owned_sector_count, occupied_slots, expected):
        indexed, hab, templates = build_hab_fixture(
            tier=tier,
            owned_sector_count=owned_sector_count,
            occupied_slots=occupied_slots,
        )
        records = ti.hab_module_records(indexed, hab, templates)

        self.assertEqual(ti.hab_slot_summary(records), expected)
        self.assertEqual(records[0]["habFactionId"], 1)
        self.assertTrue(records[0]["sectorOwnedByHabFaction"])
        if owned_sector_count < 5:
            self.assertFalse(records[-1]["sectorOwnedByHabFaction"])
        else:
            self.assertTrue(records[-1]["sectorOwnedByHabFaction"])

        result = ti.calculate_hab_slots(indexed, None, "ResistCouncil", include_all=True)
        self.assertEqual(result["habs"][0]["slots"], expected)
        filtered = ti.calculate_hab_slots(indexed, None, "ResistCouncil", include_all=False)
        self.assertEqual(len(filtered["habs"]), 1 if expected["empty"] > 0 else 0)

    def test_t1_outpost_future_placeholders_are_locked(self):
        self.assert_slot_summary(
            tier=1,
            owned_sector_count=1,
            occupied_slots=5,
            expected={
                "raw": 21,
                "usable": 5,
                "occupied": 5,
                "empty": 0,
                "locked": 16,
                "lockedEmpty": 16,
            },
        )

    def test_t3_colony_all_sectors_are_usable(self):
        self.assert_slot_summary(
            tier=3,
            owned_sector_count=5,
            occupied_slots=13,
            expected={
                "raw": 21,
                "usable": 21,
                "occupied": 13,
                "empty": 8,
                "locked": 0,
                "lockedEmpty": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
