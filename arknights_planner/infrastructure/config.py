from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    input_path: str = "data/import.json"
    output_path: str = "data/export.json"
    weight_path: str = "data/weight.json"
    material_image_dir: str = "assets/materials"
    background_image_dir: str = "assets/backgrounds"
    top_n: int = 5
    use_custom_weights: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True

    @property
    def weight_mode(self) -> str:
        return "custom" if self.use_custom_weights else "equal"


def load_app_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        return AppConfig()

    raw_values: dict[str, object] = {}
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"配置文件格式错误: {stripped}")
        key, value = stripped.split(":", 1)
        raw_values[key.strip()] = _parse_scalar(value.strip())

    return AppConfig(
        input_path=str(raw_values.get("input_path", AppConfig.input_path)),
        output_path=str(raw_values.get("output_path", AppConfig.output_path)),
        weight_path=str(raw_values.get("weight_path", AppConfig.weight_path)),
        material_image_dir=str(raw_values.get("material_image_dir", AppConfig.material_image_dir)),
        background_image_dir=str(raw_values.get("background_image_dir", AppConfig.background_image_dir)),
        top_n=int(raw_values.get("top_n", AppConfig.top_n)),
        use_custom_weights=bool(raw_values.get("use_custom_weights", AppConfig.use_custom_weights)),
        host=str(raw_values.get("host", AppConfig.host)),
        port=int(raw_values.get("port", AppConfig.port)),
        open_browser=bool(raw_values.get("open_browser", AppConfig.open_browser)),
    )


def _parse_scalar(raw: str) -> object:
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")) and len(raw) >= 2:
        raw = raw[1:-1]

    lowered = raw.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw