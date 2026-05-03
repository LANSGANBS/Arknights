from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShortageRecord:
    rank: int
    item_id: str
    name: str
    blue_equivalent: float
    weight_factor: float
    weighted_equivalent: float

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


@dataclass(frozen=True)
class PlanResult:
    has_weights: bool
    shortages: list[ShortageRecord]
    unknown_item_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "hasWeights": self.has_weights,
            "shortages": [item.to_dict() for item in self.shortages],
            "unknownItemIds": self.unknown_item_ids,
        }
