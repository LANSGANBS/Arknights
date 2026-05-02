from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from arknights_planner.application.planning_service import InventoryPlanner
from arknights_planner.infrastructure.json_storage import (
    export_inventory_document,
    load_inventory_document,
    load_inventory_json,
    load_weight_profile,
)


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = InventoryPlanner()

    def test_normalize_to_blue_supports_low_and_high_tiers(self) -> None:
        self.assertEqual(self.planner.normalize_to_blue("30014"), {"30013": 4.0})
        self.assertAlmostEqual(self.planner.normalize_to_blue("30011")["30013"], 1 / 15)
        self.assertEqual(
            self.planner.normalize_to_blue("30135"),
            {
                "30013": 2.0,
                "30033": 1.0,
                "30043": 1.0,
                "30053": 1.0,
                "30063": 1.0,
                "30073": 1.0,
                "30083": 2.0,
                "30093": 1.0,
                "30103": 1.0,
            },
        )
        self.assertEqual(self.planner.normalize_to_blue("31114"), {"30063": 1.0, "31103": 1.0, "31113": 1.0})

    def test_plan_sorts_using_weighted_equivalent(self) -> None:
        inventory = {"30013": 20, "30023": 20, "31113": 20}
        weights = {"30013": 10.0, "30023": 20.0, "31113": 40.0}
        result = self.planner.plan(inventory=inventory, top_n=3, weights=weights, weight_mode="custom")

        ranked = {item.item_id: item.weighted_equivalent for item in self.planner.plan(inventory=inventory, top_n=100, weights=weights, weight_mode="custom").shortages}
        self.assertLess(ranked["31113"], ranked["30023"])
        self.assertLess(ranked["30023"], ranked["30013"])

    def test_load_and_export_json(self) -> None:
        payload = {
            "@type": "@penguin-statistics/planner/config",
            "items": [{"id": "30013", "have": 3}, {"id": "30013", "have": 2}],
            "options": {},
            "excludes": [],
        }
        weight_payload = [
            {"id": "30013", "apValue": 10},
            {"id": "irrelevant", "apValue": 999},
        ]

        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            input_path = temp / "import.json"
            weight_path = temp / "weight.json"
            output_path = temp / "export.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            weight_path.write_text(json.dumps(weight_payload, ensure_ascii=False), encoding="utf-8")

            document = load_inventory_document(input_path)
            inventory = load_inventory_json(input_path)
            weights = load_weight_profile(weight_path, {"30013"})
            export_inventory_document(output_path, inventory=inventory, template=document)

            exported = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(inventory["30013"], 5)
        self.assertEqual(weights, {"30013": 10.0})
        self.assertEqual(exported["@type"], payload["@type"])
        self.assertEqual(exported["options"], payload["options"])
        self.assertEqual(exported["excludes"], payload["excludes"])
        self.assertEqual(exported["items"][0]["id"], "30013")
        self.assertEqual(exported["items"][0]["have"], 5)


if __name__ == "__main__":
    unittest.main()