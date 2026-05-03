from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import random
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import AppConfig, load_app_config, resolve_config_path
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_optional_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS, MATERIALS

logger = logging.getLogger(__name__)


# 扩展 MIME 类型支持，特别是现代图片格式
EXTENDED_MIME_TYPES = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".mjs": "application/javascript",
    ".json": "application/json",
    ".css": "text/css",
    ".js": "application/javascript",
}


DEFERRED_BACKGROUND_GROUP = {
    "470f3f0f95c6af4f791d28d9aed48079161775300.jpg",
    "53e2cb5c5a243add4bfb67c54d1ecb68161775300.png",
    "6903395f9b2c36474bd762b63d4ccf75161775300.png",
}


FRONTEND_WATCH_PATHS = (
    "index.html",
    "package.json",
    "package-lock.json",
    "vite.config.js",
)


def _resolve_asset_dir(base_dir: Path, raw_path: str) -> Path:
    return resolve_config_path(base_dir, raw_path)


def _find_material_image(base_dir: Path, app_config: AppConfig, material_name: str) -> str | None:
    picture_dir = _resolve_asset_dir(base_dir, app_config.material_image_dir)
    if not picture_dir.exists():
        return None
    for suffix in (".avif", ".png", ".gif", ".jpg", ".jpeg", ".webp"):
        file_path = picture_dir / f"{material_name}{suffix}"
        if file_path.exists():
            return f"/media/materials/{file_path.name}"
    return None


def _background_images(base_dir: Path, app_config: AppConfig) -> list[str]:
    background_dir = _resolve_asset_dir(base_dir, app_config.background_image_dir)
    if not background_dir.exists():
        return []

    images = []
    for file_path in sorted(background_dir.iterdir()):
        if file_path.suffix.lower() not in {".png", ".gif", ".jpg", ".jpeg", ".webp", ".avif"}:
            continue
        images.append(f"/media/backgrounds/{file_path.name}")

    if not images:
        return []

    deferred_images = {f"/media/backgrounds/{name}" for name in DEFERRED_BACKGROUND_GROUP}
    primary_images = [image for image in images if image not in deferred_images]
    trailing_images = [image for image in images if image in deferred_images]
    random.shuffle(primary_images)
    random.shuffle(trailing_images)
    return [*primary_images, *trailing_images]


@dataclass(frozen=True)
class WebSettings:
    host: str
    port: int
    project_root: Path
    config_dir: Path
    app_config: AppConfig
    open_browser: bool


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    return resolve_config_path(base_dir, raw_path)


def _resolve_static_dir(project_root: Path) -> Path:
    return project_root / "frontend" / "dist"


def _find_npm_bin() -> str | None:
    candidates = ("npm.cmd", "npm") if shutil.which("npm.cmd") else ("npm",)
    for candidate in candidates:
        npm_bin = shutil.which(candidate)
        if npm_bin:
            return npm_bin
    return None


def _frontend_sources_newer_than(frontend_dir: Path, dist_index: Path) -> bool:
    if not dist_index.exists():
        return True

    dist_mtime = dist_index.stat().st_mtime
    src_dir = frontend_dir / "src"
    if src_dir.exists():
        for file_path in src_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_mtime > dist_mtime:
                return True

    for relative_path in FRONTEND_WATCH_PATHS:
        file_path = frontend_dir / relative_path
        if file_path.exists() and file_path.stat().st_mtime > dist_mtime:
            return True
    return False


def ensure_frontend_dist(project_root: Path) -> None:
    frontend_dir = project_root / "frontend"
    dist_index = frontend_dir / "dist" / "index.html"

    if not (frontend_dir / "package.json").exists():
        raise RuntimeError("缺少前端配置文件 frontend/package.json")

    needs_install = not (frontend_dir / "node_modules").exists()
    needs_build = needs_install or _frontend_sources_newer_than(frontend_dir, dist_index)
    if not (needs_install or needs_build):
        return

    npm_bin = _find_npm_bin()
    if not npm_bin:
        raise RuntimeError("Web 前端需要 Node.js 和 npm。请先安装 Node.js 18+。")

    if needs_install:
        install_command = [npm_bin, "ci"] if (frontend_dir / "package-lock.json").exists() else [npm_bin, "install"]
        subprocess.run(install_command, cwd=frontend_dir, check=True)

    if needs_build:
        subprocess.run([npm_bin, "run", "build"], cwd=frontend_dir, check=True)
        if not dist_index.exists():
            raise RuntimeError("前端构建未生成 frontend/dist/index.html")


def _materials_payload(base_dir: Path, app_config: AppConfig) -> tuple[list[dict[str, object]], list[str]]:
    materials = []
    missing_images = []
    for material in sorted(MATERIALS.values(), key=lambda item: (-item.tier, item.item_id)):
        image_url = _find_material_image(base_dir, app_config, material.name)
        if image_url is None:
            missing_images.append(material.name)
        materials.append({"id": material.item_id, "name": material.name, "tier": material.tier, "imageUrl": image_url})
    return materials, missing_images


class PlannerRequestHandler(BaseHTTPRequestHandler):
    server: "PlannerWebServer"

    def _normalized_path(self) -> str:
        parsed = urlparse(self.path)
        path = parsed.path
        project_prefix = f"/{self.server.project_root.name}"
        if path == project_prefix:
            return "/"
        if path.startswith(project_prefix + "/"):
            return path[len(project_prefix) :]
        return path

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = self._normalized_path()
        if path == "/":
            self._serve_static("index.html", content_type="text/html; charset=utf-8")
            return
        if path.startswith("/assets/"):
            self._serve_static_path(path.removeprefix("/"))
            return
        if path.startswith("/media/materials/"):
            self._serve_media(
                _resolve_asset_dir(self.server.settings.config_dir, self.server.settings.app_config.material_image_dir),
                path.removeprefix("/media/materials/"),
                "Material image not found",
            )
            return
        if path.startswith("/media/backgrounds/"):
            self._serve_media(
                _resolve_asset_dir(self.server.settings.config_dir, self.server.settings.app_config.background_image_dir),
                path.removeprefix("/media/backgrounds/"),
                "Background image not found",
            )
            return
        if path == "/api/bootstrap":
            self._handle_bootstrap(parsed)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        path = self._normalized_path()
        if path == "/api/analyze":
            self._handle_analyze()
            return
        if path == "/api/export":
            self._handle_export()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_static(self, filename: str, content_type: str) -> None:
        """提供静态文件（如 index.html）。
        
        Args:
            filename: 文件名（相对于 static_dir）
            content_type: 响应的 Content-Type 头
        """
        file_path = self.server.static_dir / filename
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_static_path(self, relative_path: str) -> None:
        # 规范化路径分隔符，确保跨平台兼容（Windows 使用 \ 但 HTTP 使用 /）
        normalized_path = relative_path.replace("\\", "/").replace("//", "/")
        # 防止目录遍历攻击
        if ".." in normalized_path or normalized_path.startswith("/"):
            self.send_error(HTTPStatus.FORBIDDEN, "Access denied")
            return
        
        file_path = self.server.static_dir / normalized_path
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return
        
        # 确保文件在 static_dir 内（防止目录遍历）
        try:
            file_path.resolve().relative_to(self.server.static_dir.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Access denied")
            return
        
        # 获取 MIME 类型，优先使用扩展类型表
        suffix = file_path.suffix.lower()
        mime_type = EXTENDED_MIME_TYPES.get(suffix) or mimetypes.guess_type(str(file_path))[0]
        
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_media(self, base_dir: Path, filename: str, not_found_message: str) -> None:
        """提供媒体文件（图片等）。
        
        Args:
            base_dir: 媒体文件的基础目录
            filename: 文件名（URL 编码）
            not_found_message: 文件不存在时的错误消息
        """
        file_path = base_dir / unquote(filename)
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, not_found_message)
            return
        
        # 获取 MIME 类型，优先使用扩展类型表
        suffix = file_path.suffix.lower()
        mime_type = EXTENDED_MIME_TYPES.get(suffix) or mimetypes.guess_type(str(file_path))[0]
        
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length) if content_length else b"{}"
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle_bootstrap(self, parsed) -> None:
        """处理初始化请求，返回应用所需的所有初始数据。"""
        del parsed  # 未使用的参数
        input_path = self.server.settings.app_config.input_path
        output_path = self.server.settings.app_config.output_path
        weight_path = self.server.settings.app_config.weight_path
        top_n = self.server.settings.app_config.top_n

        document: dict[str, object]
        inventory: dict[str, int]
        try:
            document = load_inventory_document(_resolve_path(self.server.settings.config_dir, input_path))
            inventory = document_to_inventory(document)
        except FileNotFoundError:
            document = {
                "@type": "@penguin-statistics/planner/config",
                "items": [],
                "options": {},
                "excludes": [],
            }
            inventory = {}

        weights = load_optional_weight_profile(_resolve_path(self.server.settings.config_dir, weight_path), set(BLUE_MATERIAL_IDS))

        materials, missing_images = _materials_payload(self.server.settings.config_dir, self.server.settings.app_config)
        background_images = _background_images(self.server.settings.config_dir, self.server.settings.app_config)
        result = run_cli(inventory=inventory, top_n=top_n, weights=weights)
        full_result = run_cli(inventory=inventory, top_n=len(BLUE_MATERIAL_IDS), weights=weights)
        self._send_json(
            {
                "inputPath": input_path,
                "outputPath": output_path,
                "weightPath": weight_path,
                "topN": top_n,
                "weightsAvailable": result.has_weights,
                "document": document,
                "inventory": inventory,
                "materials": materials,
                "backgroundImages": background_images,
                "missingPictureNames": missing_images,
                "result": result.to_dict(),
                "fullResult": full_result.to_dict(),
            }
        )

    def _handle_analyze(self) -> None:
        """处理分析请求。"""
        try:
            payload = self._read_json_body()
            inventory = {str(item_id): int(count) for item_id, count in dict(payload.get("inventory", {})).items()}
            top_n = self.server.settings.app_config.top_n
            weight_path = self.server.settings.app_config.weight_path
            weights = load_optional_weight_profile(_resolve_path(self.server.settings.config_dir, weight_path), set(BLUE_MATERIAL_IDS))
            result = run_cli(inventory=inventory, top_n=top_n, weights=weights)
            full_result = run_cli(inventory=inventory, top_n=len(BLUE_MATERIAL_IDS), weights=weights)
            self._send_json({"weightsAvailable": result.has_weights, "result": result.to_dict(), "fullResult": full_result.to_dict()})
        except FileNotFoundError as exc:
            logger.warning(f"分析请求失败: 文件不存在 - {exc}")
            self._send_json({"error": "所需文件不存在"}, status=HTTPStatus.BAD_REQUEST)
        except PlannerError as exc:
            logger.error(f"分析请求失败: 规划器错误 - {exc}")
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except (ValueError, TypeError) as exc:
            logger.error(f"分析请求失败: 数据格式错误 - {exc}")
            self._send_json({"error": "请求数据格式错误"}, status=HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            logger.error(f"分析请求失败: 系统错误 - {exc}")
            self._send_json({"error": "系统错误，请稍后重试"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_export(self) -> None:
        """处理导出请求。"""
        try:
            payload = self._read_json_body()
            output_path = self.server.settings.app_config.output_path
            inventory = {str(item_id): int(count) for item_id, count in dict(payload.get("inventory", {})).items()}
            template_document = payload.get("templateDocument")
            if template_document is not None and not isinstance(template_document, dict):
                raise ValueError("templateDocument 必须是 JSON 对象")
            export_inventory_document(
                _resolve_path(self.server.settings.config_dir, output_path),
                inventory=inventory,
                template=template_document,
            )
            logger.info(f"导出成功: {output_path}")
            self._send_json({"ok": True, "outputPath": output_path})
        except FileNotFoundError as exc:
            logger.warning(f"导出失败: 文件不存在 - {exc}")
            self._send_json({"error": "输出目录不存在"}, status=HTTPStatus.BAD_REQUEST)
        except (ValueError, TypeError) as exc:
            logger.error(f"导出失败: 数据格式错误 - {exc}")
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            logger.error(f"导出失败: 系统错误 - {exc}")
            self._send_json({"error": "无法写入文件，请检查权限"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


class PlannerWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, settings: WebSettings) -> None:
        super().__init__(server_address, handler_class)
        self.settings = settings
        self.project_root = settings.project_root
        self.static_dir = _resolve_static_dir(settings.project_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="明日方舟素材均衡规划器 Web 界面")
    parser.add_argument("--config", default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[2]
    config_path = Path(args.config) if args.config else project_root / "config.yaml"
    if args.config and not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        ensure_frontend_dist(project_root)
    except subprocess.CalledProcessError as exc:
        print(f"Web 前端准备失败: 命令执行异常（退出码 {exc.returncode}）")
        return exc.returncode or 1
    except RuntimeError as exc:
        print(f"Web 前端准备失败: {exc}")
        return 1

    app_config = load_app_config(config_path)
    host = args.host or app_config.host
    port = args.port if args.port is not None else app_config.port
    open_browser = app_config.open_browser
    if args.open_browser:
        open_browser = True
    if args.no_browser:
        open_browser = False

    settings = WebSettings(
        host=host,
        port=port,
        project_root=project_root,
        config_dir=config_path.parent,
        app_config=app_config,
        open_browser=open_browser,
    )

    server = PlannerWebServer((settings.host, settings.port), PlannerRequestHandler, settings)
    url = f"http://{settings.host}:{settings.port}/"
    print(f"Web 界面已启动: {url}")
    if settings.open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
