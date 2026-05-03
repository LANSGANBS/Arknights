from __future__ import annotations

import argparse
from pathlib import Path

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import load_app_config, resolve_config_path
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_optional_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS, MATERIALS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="明日方舟素材均衡规划器")
    parser.add_argument("--config", default=None, help="配置文件路径，默认使用项目根目录下的 config.yaml")
    parser.add_argument("--input", default=None, help="导入库存 JSON，默认读取 config.yaml")
    parser.add_argument("--output", default=None, help="如需导出库存 JSON，请显式指定输出路径")
    parser.add_argument("--top", type=int, default=None, help="输出前多少个最缺少的蓝色素材，默认读取 config.yaml")
    parser.add_argument("--weight-file", default=None, help="自定义权重文件，默认读取 config.yaml")
    return parser


def format_console_output(result) -> str:
    lines = ["最缺少的蓝色素材："]
    for item in result.shortages:
        material_name = MATERIALS[item.item_id].name if item.item_id in MATERIALS else item.name
        if not result.has_weights:
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
    project_root = Path(__file__).resolve().parents[2]
    config_path = Path(args.config) if args.config else project_root / "config.yaml"
    if args.config is None:
        config_path = project_root / "config.yaml"
    elif not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        config = load_app_config(config_path)
        config_dir = config_path.parent
        input_path = Path(args.input) if args.input else resolve_config_path(config_dir, config.input_path)
        top_n = args.top if args.top is not None else config.top_n
        weight_file = Path(args.weight_file) if args.weight_file else resolve_config_path(config_dir, config.weight_path)

        document = load_inventory_document(input_path)
        inventory = document_to_inventory(document)
        weights = load_optional_weight_profile(weight_file, set(BLUE_MATERIAL_IDS))
        result = run_cli(inventory=inventory, top_n=top_n, weights=weights)
        print(format_console_output(result))
        if args.output:
            output_path = Path(args.output)
            export_inventory_document(output_path, inventory=inventory, template=document)
            print(f"\n已导出到 {output_path}")
    except (PlannerError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"运行失败: {exc}")
        return 1
    return 0
