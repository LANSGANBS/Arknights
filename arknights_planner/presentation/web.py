from __future__ import annotations

import argparse
import json
import mimetypes
import random
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import AppConfig, load_app_config
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS, MATERIALS


DEFERRED_BACKGROUND_GROUP = {
    "470f3f0f95c6af4f791d28d9aed48079161775300.jpg",
    "53e2cb5c5a243add4bfb67c54d1ecb68161775300.png",
    "6903395f9b2c36474bd762b63d4ccf75161775300.png",
}


def _resolve_asset_dir(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return project_root / path


def _find_material_image(project_root: Path, app_config: AppConfig, material_name: str) -> str | None:
    picture_dir = _resolve_asset_dir(project_root, app_config.material_image_dir)
    if not picture_dir.exists():
        return None
    for suffix in (".avif", ".png", ".gif", ".jpg", ".jpeg", ".webp"):
        file_path = picture_dir / f"{material_name}{suffix}"
        if file_path.exists():
            return f"/media/materials/{file_path.name}"
    return None


def _background_images(project_root: Path, app_config: AppConfig) -> list[str]:
    background_dir = _resolve_asset_dir(project_root, app_config.background_image_dir)
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
    app_config: AppConfig
    open_browser: bool


def _resolve_path(project_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return project_root / path


def _materials_payload(project_root: Path, app_config: AppConfig) -> tuple[list[dict[str, object]], list[str]]:
    materials = []
    missing_images = []
    for material in sorted(MATERIALS.values(), key=lambda item: (-item.tier, item.item_id)):
        image_url = _find_material_image(project_root, app_config, material.name)
        if image_url is None:
            missing_images.append(material.name)
        materials.append({"id": material.item_id, "name": material.name, "tier": material.tier, "imageUrl": image_url})
    return materials, missing_images


class PlannerRequestHandler(BaseHTTPRequestHandler):
    server: "PlannerWebServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_static("index.html", content_type="text/html; charset=utf-8")
            return
        if parsed.path.startswith("/assets/"):
            self._serve_static_path(parsed.path.removeprefix("/"))
            return
        if parsed.path.startswith("/media/materials/"):
            self._serve_media(
                _resolve_asset_dir(self.server.project_root, self.server.settings.app_config.material_image_dir),
                parsed.path.removeprefix("/media/materials/"),
                "Material image not found",
            )
            return
        if parsed.path.startswith("/media/backgrounds/"):
            self._serve_media(
                _resolve_asset_dir(self.server.project_root, self.server.settings.app_config.background_image_dir),
                parsed.path.removeprefix("/media/backgrounds/"),
                "Background image not found",
            )
            return
        if parsed.path == "/api/bootstrap":
            self._handle_bootstrap(parsed)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            self._handle_analyze()
            return
        if parsed.path == "/api/export":
            self._handle_export()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_static(self, filename: str, content_type: str) -> None:
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
        file_path = self.server.static_dir / relative_path
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return
        mime_type, _ = mimetypes.guess_type(str(file_path))
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_media(self, base_dir: Path, filename: str, not_found_message: str) -> None:
        file_path = base_dir / unquote(filename)
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, not_found_message)
            return
        mime_type, _ = mimetypes.guess_type(str(file_path))
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
        del parsed
        input_path = self.server.settings.app_config.input_path
        output_path = self.server.settings.app_config.output_path
        weight_path = self.server.settings.app_config.weight_path
        top_n = self.server.settings.app_config.top_n
        weight_mode = self.server.settings.app_config.weight_mode

        document: dict[str, object]
        inventory: dict[str, int]
        try:
            document = load_inventory_document(_resolve_path(self.server.project_root, input_path))
            inventory = document_to_inventory(document)
        except FileNotFoundError:
            document = {
                "@type": "@penguin-statistics/planner/config",
                "items": [],
                "options": {},
                "excludes": [],
            }
            inventory = {}

        weights = None
        if weight_mode == "custom":
            try:
                weights = load_weight_profile(_resolve_path(self.server.project_root, weight_path), set(BLUE_MATERIAL_IDS))
            except FileNotFoundError:
                weights = {}

        materials, missing_images = _materials_payload(self.server.project_root, self.server.settings.app_config)
        background_images = _background_images(self.server.project_root, self.server.settings.app_config)
        result = run_cli(inventory=inventory, top_n=top_n, weights=weights, weight_mode=weight_mode)
        full_result = run_cli(inventory=inventory, top_n=len(BLUE_MATERIAL_IDS), weights=weights, weight_mode=weight_mode)
        self._send_json(
            {
                "inputPath": input_path,
                "outputPath": output_path,
                "weightPath": weight_path,
                "topN": top_n,
                "weightMode": weight_mode,
                "useCustomWeights": weight_mode == "custom",
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
        try:
            payload = self._read_json_body()
            inventory = {str(item_id): int(count) for item_id, count in dict(payload.get("inventory", {})).items()}
            weight_mode = "custom" if bool(payload.get("useCustomWeights", False)) else "equal"
            top_n = self.server.settings.app_config.top_n
            weights = None
            if weight_mode == "custom":
                weight_path = self.server.settings.app_config.weight_path
                weights = load_weight_profile(_resolve_path(self.server.project_root, weight_path), set(BLUE_MATERIAL_IDS))
            result = run_cli(inventory=inventory, top_n=top_n, weights=weights, weight_mode=weight_mode)
            full_result = run_cli(inventory=inventory, top_n=len(BLUE_MATERIAL_IDS), weights=weights, weight_mode=weight_mode)
            self._send_json({"result": result.to_dict(), "fullResult": full_result.to_dict()})
        except (PlannerError, FileNotFoundError, OSError, ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_export(self) -> None:
        try:
            payload = self._read_json_body()
            output_path = self.server.settings.app_config.output_path
            inventory = {str(item_id): int(count) for item_id, count in dict(payload.get("inventory", {})).items()}
            template_document = payload.get("templateDocument")
            if template_document is not None and not isinstance(template_document, dict):
                raise ValueError("templateDocument 必须是 JSON 对象")
            export_inventory_document(
                _resolve_path(self.server.project_root, output_path),
                inventory=inventory,
                template=template_document,
            )
            self._send_json({"ok": True, "outputPath": output_path})
        except (FileNotFoundError, OSError, ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)


class PlannerWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, settings: WebSettings) -> None:
        super().__init__(server_address, handler_class)
        self.settings = settings
        self.project_root = settings.project_root
        self.static_dir = settings.project_root / "frontend" / "dist"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="明日方舟素材均衡规划器 Web 界面")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[2]
    app_config = load_app_config(project_root / args.config)
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