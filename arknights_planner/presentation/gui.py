from __future__ import annotations

from pathlib import Path

try:
    from tkinter import BOTH, LEFT, RIGHT, TOP, VERTICAL, X, Y, END, PhotoImage, StringVar, Tk, filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ModuleNotFoundError:
    TK_AVAILABLE = False

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import load_app_config, resolve_config_path
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_optional_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS


class PlannerGui:
    def __init__(self) -> None:
        if not TK_AVAILABLE:
            raise RuntimeError("当前 Python 环境未启用 Tk，暂时无法启动 GUI。请安装带 Tk 的 Python，或先继续使用命令行模式。")
        self.root = Tk()
        self.root.title("明日方舟素材均衡规划器")
        self.root.geometry("1160x760")

        self.project_root = Path(__file__).resolve().parents[2]
        self.config_path = self.project_root / "config.yaml"
        self.config_dir = self.config_path.parent
        app_config = load_app_config(self.config_path)

        self.material_image_dir = resolve_config_path(self.config_dir, app_config.material_image_dir)
        self.input_path = StringVar(value=str(resolve_config_path(self.config_dir, app_config.input_path)))
        self.output_path = StringVar(value=str(resolve_config_path(self.config_dir, app_config.output_path)))
        self.weight_path = StringVar(value=str(resolve_config_path(self.config_dir, app_config.weight_path)))
        self.top_n = StringVar(value=str(app_config.top_n))
        self.status = StringVar(value="准备就绪")

        self.current_document: dict[str, object] | None = None
        self.current_inventory: dict[str, int] = {}
        self.image_ref: PhotoImage | None = None

        self._build_layout()
        self._load_preview_image()

    def _runtime_path(self, raw_path: str) -> Path:
        return resolve_config_path(self.config_dir, raw_path)

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=16)
        root_frame.pack(fill=BOTH, expand=True)

        control_frame = ttk.LabelFrame(root_frame, text="控制区", padding=12)
        control_frame.pack(fill=X)

        self._add_file_row(control_frame, 0, "导入文件", self.input_path, self._choose_input)
        self._add_file_row(control_frame, 1, "导出文件", self.output_path, self._choose_output)
        self._add_file_row(control_frame, 2, "权重文件", self.weight_path, self._choose_weight)

        ttk.Label(control_frame, text="输出数量").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=8)
        ttk.Entry(control_frame, textvariable=self.top_n, width=8).grid(row=3, column=1, sticky="w", pady=8)

        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=4, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Button(action_frame, text="导入库存", command=self.load_inventory).pack(side=LEFT)
        ttk.Button(action_frame, text="开始分析", command=self.run_analysis).pack(side=LEFT, padx=8)
        ttk.Button(action_frame, text="导出库存", command=self.export_inventory).pack(side=LEFT)

        content_frame = ttk.Frame(root_frame)
        content_frame.pack(fill=BOTH, expand=True, pady=(16, 0))

        left_frame = ttk.LabelFrame(content_frame, text="分析结果", padding=12)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)

        columns = ("rank", "item_id", "name", "blue_equivalent", "weighted_equivalent")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=22)
        self.tree.heading("rank", text="排名")
        self.tree.heading("item_id", text="ID")
        self.tree.heading("name", text="素材")
        self.tree.heading("blue_equivalent", text="蓝材等效库存")
        self.tree.heading("weighted_equivalent", text="加权后库存")
        self.tree.column("rank", width=60, anchor="center")
        self.tree.column("item_id", width=90, anchor="center")
        self.tree.column("name", width=160, anchor="w")
        self.tree.column("blue_equivalent", width=140, anchor="e")
        self.tree.column("weighted_equivalent", width=140, anchor="e")
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(left_frame, orient=VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        right_frame = ttk.LabelFrame(content_frame, text="图片预留", padding=12)
        right_frame.pack(side=RIGHT, fill=Y, padx=(16, 0))

        self.image_label = ttk.Label(right_frame, text="会从素材图片目录加载一张 PNG/GIF 作为预览。", width=36, anchor="center", justify="center")
        self.image_label.pack(side=TOP, fill=BOTH, expand=True)

        ttk.Label(root_frame, textvariable=self.status).pack(fill=X, pady=(12, 0))

    def _add_file_row(self, parent, row: int, label: str, variable: StringVar, browse_command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable, width=72).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Button(parent, text="浏览", command=browse_command).grid(row=row, column=3, sticky="e", padx=(8, 0), pady=4)
        parent.columnconfigure(1, weight=1)

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(title="选择导入库存 JSON", filetypes=[("JSON", "*.json"), ("All Files", "*")])
        if path:
            self.input_path.set(path)

    def _choose_output(self) -> None:
        path = filedialog.asksaveasfilename(title="选择导出库存 JSON", defaultextension=".json", filetypes=[("JSON", "*.json"), ("All Files", "*")])
        if path:
            self.output_path.set(path)

    def _choose_weight(self) -> None:
        path = filedialog.askopenfilename(title="选择权重文件 JSON", filetypes=[("JSON", "*.json"), ("All Files", "*")])
        if path:
            self.weight_path.set(path)

    def _load_preview_image(self) -> None:
        picture_dir = self.material_image_dir
        candidates = []
        if picture_dir.exists():
            for suffix in ("*.png", "*.gif"):
                candidates.extend(sorted(picture_dir.glob(suffix)))
        if not candidates:
            self.image_label.configure(text=f"未在 {picture_dir} 找到可预览的 PNG/GIF 素材图。")
            return
        try:
            self.image_ref = PhotoImage(file=str(candidates[0]))
        except Exception:
            self.image_label.configure(text=f"无法预览 {candidates[0].name}，请改用 PNG/GIF。")
            return
        self.image_label.configure(image=self.image_ref, text="")

    def load_inventory(self) -> None:
        try:
            self.current_document = load_inventory_document(self._runtime_path(self.input_path.get()))
            self.current_inventory = document_to_inventory(self.current_document)
            self.status.set(f"已导入 {len(self.current_inventory)} 个素材条目")
        except (FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("导入失败", str(exc))

    def run_analysis(self) -> None:
        try:
            if not self.current_inventory:
                self.load_inventory()
            weights = load_optional_weight_profile(self._runtime_path(self.weight_path.get()), set(BLUE_MATERIAL_IDS))
            result = run_cli(
                inventory=self.current_inventory,
                top_n=int(self.top_n.get()),
                weights=weights,
            )
        except (PlannerError, FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("分析失败", str(exc))
            return

        for child in self.tree.get_children():
            self.tree.delete(child)

        for item in result.shortages:
            weighted_display = f"{item.weighted_equivalent:.2f}" if result.has_weights else "-"
            self.tree.insert("", END, values=(item.rank, item.item_id, item.name, f"{item.blue_equivalent:.2f}", weighted_display))

        if result.has_weights:
            self.status.set(f"分析完成，已读取权重文件 {self.weight_path.get()}")
        else:
            self.status.set("分析完成，未读取到权重文件，结果按蓝材等效库存展示")

    def export_inventory(self) -> None:
        try:
            if not self.current_inventory:
                self.load_inventory()
            export_inventory_document(self._runtime_path(self.output_path.get()), inventory=self.current_inventory, template=self.current_document)
            self.status.set(f"已导出到 {self.output_path.get()}")
        except (FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("导出失败", str(exc))

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    if not TK_AVAILABLE:
        print("GUI 启动失败: 当前 Python 环境未启用 Tk。请安装带 Tk 的 Python，或先继续使用命令行模式。")
        return 1
    PlannerGui().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
