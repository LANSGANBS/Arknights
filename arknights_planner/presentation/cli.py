from __future__ import annotations

import argparse
from pathlib import Path

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import load_app_config
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS, MATERIALS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="明日方舟素材均衡规划器")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径，默认 config.yaml")
    parser.add_argument("--input", default=None, help="导入库存 JSON，默认读取 config.yaml")
    parser.add_argument("--output", default=None, help="导出结果 JSON，默认读取 config.yaml")
    parser.add_argument("--top", type=int, default=None, help="输出前多少个最缺少的蓝色素材，默认读取 config.yaml")
    parser.add_argument("--weight-mode", choices=["equal", "custom"], default=None, help="权重模式，默认读取 config.yaml")
    parser.add_argument("--weight-file", default=None, help="自定义权重文件，默认读取 config.yaml")
    return parser


def format_console_output(result) -> str:
    lines = [f"最缺少的蓝色素材（权重模式: {result.weight_mode}）："]
    for item in result.shortages:
        material_name = MATERIALS[item.item_id].name if item.item_id in MATERIALS else item.name
        if result.weight_mode == "equal":
            lines.append(f"{item.rank}. {material_name} ({item.item_id}) - 蓝材等效库存 {item.blue_equivalent:.2f}")
        else:
            lines.append(
                f"{item.rank}. {material_name} ({item.item_id}) - 蓝材等效库存 {item.blue_equivalent:.2f} - 加权后库存 {item.weighted_equivalent:.2f}"
            )
    if result.unknown_item_ids:
        lines.append("")
        lines.append("未识别的素材 ID：" + ", ".join(result.unknown_item_ids))
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = load_app_config(Path(args.config))
        input_path = args.input or config.input_path
        output_path = args.output or config.output_path
        top_n = args.top if args.top is not None else config.top_n
        weight_mode = args.weight_mode or config.weight_mode
        weight_file = args.weight_file or config.weight_path

        document = load_inventory_document(input_path)
        inventory = document_to_inventory(document)
        weights = None
        if weight_mode == "custom":
            weights = load_weight_profile(weight_file, set(BLUE_MATERIAL_IDS))
        result = run_cli(inventory=inventory, top_n=top_n, weights=weights, weight_mode=weight_mode)
        export_inventory_document(output_path, inventory=inventory, template=document)
        print(format_console_output(result))
        print(f"\n已导出到 {output_path}")
    except (PlannerError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"运行失败: {exc}")
        return 1
    return 0