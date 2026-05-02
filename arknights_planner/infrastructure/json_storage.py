from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


def load_inventory_document(input_path: str | Path) -> dict[str, object]:
    raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {
            "@type": "@penguin-statistics/planner/config",
            "items": raw,
            "options": {},
            "excludes": [],
        }
    if not isinstance(raw, dict):
        raise ValueError("导入文件必须是 JSON 对象或 items 数组。")
    return {
        "@type": raw.get("@type", "@penguin-statistics/planner/config"),
        "items": raw.get("items", []),
        "options": raw.get("options", {}),
        "excludes": raw.get("excludes", []),
    }


def document_to_inventory(document: dict[str, object]) -> dict[str, int]:
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise ValueError("导入文件必须是 JSON，且包含 items 数组。")

    inventory: dict[str, int] = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id", "")).strip()
        if not item_id:
            continue
        inventory[item_id] = inventory.get(item_id, 0) + int(entry.get("have", 0))
    return inventory


def load_inventory_json(input_path: str | Path) -> dict[str, int]:
    return document_to_inventory(load_inventory_document(input_path))


def load_weight_profile(weight_path: str | Path, material_ids: set[str]) -> dict[str, float]:
    raw = json.loads(Path(weight_path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("weight.json 必须是数组格式。")

    weights: dict[str, float] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id", "")).strip()
        if item_id not in material_ids:
            continue
        value = entry.get("apValue")
        if value is None:
            continue
        weights[item_id] = float(value)
    return weights


def build_inventory_document(inventory: dict[str, int], template: dict[str, object] | None = None) -> dict[str, object]:
    base = deepcopy(template) if template else {
        "@type": "@penguin-statistics/planner/config",
        "items": [],
        "options": {},
        "excludes": [],
    }

    template_items = base.get("items") if isinstance(base, dict) else []
    ordered_ids: list[str] = []
    if isinstance(template_items, list):
        for entry in template_items:
            if isinstance(entry, dict):
                item_id = str(entry.get("id", "")).strip()
                if item_id and item_id not in ordered_ids:
                    ordered_ids.append(item_id)

    for item_id in sorted(inventory):
        if item_id not in ordered_ids:
            ordered_ids.append(item_id)

    base["items"] = [{"id": item_id, "have": inventory.get(item_id, 0)} for item_id in ordered_ids]
    base.setdefault("options", {})
    base.setdefault("excludes", [])
    base.setdefault("@type", "@penguin-statistics/planner/config")
    return base


def export_inventory_document(output_path: str | Path, inventory: dict[str, int], template: dict[str, object] | None = None) -> None:
    document = build_inventory_document(inventory, template=template)
    Path(output_path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")