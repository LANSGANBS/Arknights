from __future__ import annotations

from functools import lru_cache
from statistics import mean

from arknights_planner.domain.models import PlanResult, ShortageRecord
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS, CRAFTING_RULES, MATERIALS, UPGRADE_RULES


class PlannerError(Exception):
    pass


class InventoryPlanner:
    def __init__(self) -> None:
        self.materials = MATERIALS
        self.blue_material_ids = BLUE_MATERIAL_IDS
        self.crafting_rules = CRAFTING_RULES
        self.upgrade_rules = UPGRADE_RULES

    def plan(self, inventory: dict[str, int], top_n: int = 5, weights: dict[str, float] | None = None, weight_mode: str = "equal") -> PlanResult:
        unknown = sorted(item_id for item_id in inventory if item_id not in self.materials)
        blue_totals: dict[str, float] = {item_id: 0.0 for item_id in self.blue_material_ids}
        for item_id, count in inventory.items():
            if count == 0 or item_id not in self.materials:
                continue
            normalized = self.normalize_to_blue(item_id)
            for blue_item_id, blue_count in normalized.items():
                blue_totals[blue_item_id] += count * blue_count

        weight_factors = self._resolve_weight_factors(weights)
        shortages = []
        for blue_item_id, equivalent_count in blue_totals.items():
            factor = weight_factors[blue_item_id]
            shortages.append(
                ShortageRecord(
                    rank=0,
                    item_id=blue_item_id,
                    name=self.materials[blue_item_id].name,
                    blue_equivalent=equivalent_count,
                    weight_factor=factor,
                    weighted_equivalent=equivalent_count / factor,
                )
            )

        shortages.sort(key=lambda item: (item.weighted_equivalent, item.blue_equivalent, item.name, item.item_id))
        ranked = [
            ShortageRecord(
                rank=index,
                item_id=item.item_id,
                name=item.name,
                blue_equivalent=item.blue_equivalent,
                weight_factor=item.weight_factor,
                weighted_equivalent=item.weighted_equivalent,
            )
            for index, item in enumerate(shortages[:top_n], start=1)
        ]
        return PlanResult(weight_mode=weight_mode, shortages=ranked, unknown_item_ids=unknown)

    @lru_cache(maxsize=None)
    def _normalize_pairs(self, item_id: str) -> tuple[tuple[str, float], ...]:
        if item_id not in self.materials:
            raise PlannerError(f"未知材料 ID: {item_id}")
        definition = self.materials[item_id]
        if definition.tier == 3:
            return ((item_id, 1.0),)
        if definition.tier < 3:
            upgrade = self.upgrade_rules.get(item_id)
            if not upgrade:
                raise PlannerError(f"材料 {item_id} 缺少向上折算规则，无法换算到蓝材。")
            target_item_id, target_cost = upgrade
            normalized = dict(self._normalize_pairs(target_item_id))
            return tuple(sorted((blue_item_id, value / target_cost) for blue_item_id, value in normalized.items()))
        rule = self.crafting_rules.get(item_id)
        if not rule:
            raise PlannerError(f"材料 {item_id} 缺少折算规则，无法换算到蓝材。")
        totals: dict[str, float] = {}
        for cost_item_id, cost_count in rule.items():
            for blue_item_id, blue_value in self._normalize_pairs(cost_item_id):
                totals[blue_item_id] = totals.get(blue_item_id, 0.0) + blue_value * cost_count
        return tuple(sorted(totals.items()))

    def normalize_to_blue(self, item_id: str) -> dict[str, float]:
        return dict(self._normalize_pairs(item_id))

    def _resolve_weight_factors(self, weights: dict[str, float] | None) -> dict[str, float]:
        if not weights:
            return {item_id: 1.0 for item_id in self.blue_material_ids}

        selected = {item_id: value for item_id, value in weights.items() if item_id in self.blue_material_ids and value > 0}
        if not selected:
            return {item_id: 1.0 for item_id in self.blue_material_ids}

        baseline = mean(selected.values())
        factors = {item_id: 1.0 for item_id in self.blue_material_ids}
        for item_id, value in selected.items():
            factors[item_id] = value / baseline
        return factors


def run_cli(inventory: dict[str, int], top_n: int = 5, weights: dict[str, float] | None = None, weight_mode: str = "equal") -> PlanResult:
    return InventoryPlanner().plan(inventory=inventory, top_n=top_n, weights=weights, weight_mode=weight_mode)