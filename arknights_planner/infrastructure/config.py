from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    """应用配置数据类。
    
    所有路径都支持相对路径和绝对路径。
    相对路径会相对于配置文件所在目录解析。
    """
    input_path: str = "data/import.json"
    output_path: str = "data/export.json"
    weight_path: str = "data/weight.json"
    material_image_dir: str = "assets/materials"
    background_image_dir: str = "assets/backgrounds"
    top_n: int = 5
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True


def load_app_config(config_path: Path) -> AppConfig:
    """从 YAML 配置文件加载应用配置。
    
    配置文件格式为简单的 key: value 格式，每行一个配置项。
    支持注释（以 # 开头）和空行。
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        AppConfig 对象，如果文件不存在则返回默认配置
        
    Raises:
        ValueError: 配置文件格式错误时抛出
    """
    if not config_path.exists():
        logger.info(f"配置文件不存在: {config_path}，使用默认配置")
        return AppConfig()

    raw_values: dict[str, object] = {}
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        logger.error(f"无法读取配置文件: {e}")
        raise ValueError(f"无法读取配置文件 {config_path}: {e}") from e

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # 跳过空行和注释
        if not stripped or stripped.startswith("#"):
            continue
        
        # 检查是否包含冒号
        if ":" not in stripped:
            logger.warning(f"配置文件第 {line_num} 行格式错误（缺少冒号）: {stripped}")
            raise ValueError(f"配置文件第 {line_num} 行格式错误（缺少冒号）: {stripped}")
        
        # 分割 key 和 value
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        
        if not key:
            logger.warning(f"配置文件第 {line_num} 行的 key 为空")
            raise ValueError(f"配置文件第 {line_num} 行的 key 为空")
        
        raw_values[key] = _parse_scalar(value)

    # 构建配置对象，使用类型转换和验证
    try:
        return AppConfig(
            input_path=str(raw_values.get("input_path", AppConfig.input_path)),
            output_path=str(raw_values.get("output_path", AppConfig.output_path)),
            weight_path=str(raw_values.get("weight_path", AppConfig.weight_path)),
            material_image_dir=str(raw_values.get("material_image_dir", AppConfig.material_image_dir)),
            background_image_dir=str(raw_values.get("background_image_dir", AppConfig.background_image_dir)),
            top_n=_to_int(raw_values.get("top_n", AppConfig.top_n), "top_n"),
            host=str(raw_values.get("host", AppConfig.host)),
            port=_to_int(raw_values.get("port", AppConfig.port), "port"),
            open_browser=_to_bool(raw_values.get("open_browser", AppConfig.open_browser), "open_browser"),
        )
    except (ValueError, TypeError) as e:
        logger.error(f"配置值类型转换失败: {e}")
        raise ValueError(f"配置值类型转换失败: {e}") from e


def resolve_config_path(base_dir: str | Path, raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(base_dir) / path


def _parse_scalar(raw: str) -> object:
    """解析配置值为相应的 Python 类型。
    
    支持：
    - 字符串（带或不带引号）
    - 布尔值（true/false/yes/no/on/off）
    - 整数
    """
    # 移除引号
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")) and len(raw) >= 2:
        return raw[1:-1]

    # 检查布尔值
    lowered = raw.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    
    # 检查整数
    if raw.lstrip("-").isdigit():
        return int(raw)
    
    # 默认作为字符串返回
    return raw


def _to_int(value: object, field_name: str) -> int:
    """将值转换为整数。
    
    Args:
        value: 要转换的值
        field_name: 字段名（用于错误消息）
        
    Returns:
        转换后的整数
        
    Raises:
        ValueError: 无法转换时抛出
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"配置项 '{field_name}' 的值 '{value}' 不是有效的整数") from None
    raise ValueError(f"配置项 '{field_name}' 的值类型错误，期望整数，得到 {type(value).__name__}")


def _to_bool(value: object, field_name: str) -> bool:
    """将值转换为布尔值。
    
    Args:
        value: 要转换的值
        field_name: 字段名（用于错误消息）
        
    Returns:
        转换后的布尔值
        
    Raises:
        ValueError: 无法转换时抛出
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0"}:
            return False
        raise ValueError(f"配置项 '{field_name}' 的值 '{value}' 不是有效的布尔值")
    raise ValueError(f"配置项 '{field_name}' 的值类型错误，期望布尔值，得到 {type(value).__name__}")
