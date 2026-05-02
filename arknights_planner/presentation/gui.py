from __future__ import annotations

from pathlib import Path

try:
    from tkinter import BOTH, LEFT, RIGHT, TOP, VERTICAL, X, Y, END, PhotoImage, StringVar, Tk, filedialog, messagebox, ttk
    TK_AVAILABLE = True
except ModuleNotFoundError:
    TK_AVAILABLE = False

from arknights_planner.application.planning_service import PlannerError, run_cli
from arknights_planner.infrastructure.config import load_app_config
from arknights_planner.infrastructure.json_storage import (
    document_to_inventory,
    export_inventory_document,
    load_inventory_document,
    load_weight_profile,
)
from arknights_planner.infrastructure.material_catalog import BLUE_MATERIAL_IDS


class PlannerGui:
    def __init__(self) -> None:
        if not TK_AVAILABLE:
            raise RuntimeError("当前 Python 环境未启用 Tk，暂时无法启动 GUI。请安装带 Tk 的 Python，或先继续使用命令行模式。")
        self.root = Tk()
        self.root.title("明日方舟素材均衡规划器")
        self.root.geometry("1160x760")

        project_root = Path(__file__).resolve().parents[2]
        app_config = load_app_config(project_root / "config.yaml")

        self.input_path = StringVar(value=app_config.input_path)
        self.output_path = StringVar(value=app_config.output_path)
        self.weight_path = StringVar(value=app_config.weight_path)
        self.weight_mode = StringVar(value=app_config.weight_mode)
        self.top_n = StringVar(value=str(app_config.top_n))
        self.status = StringVar(value="准备就绪")

        self.current_document: dict[str, object] | None = None
        self.current_inventory: dict[str, int] = {}
        self.image_ref: PhotoImage | None = None

        self._build_layout()
        self._load_preview_image()

    def _build_layout(self) -> None:
        root_frame = ttk.Frame(self.root, padding=16)
        root_frame.pack(fill=BOTH, expand=True)

        control_frame = ttk.LabelFrame(root_frame, text="控制区", padding=12)
        control_frame.pack(fill=X)

        self._add_file_row(control_frame, 0, "导入文件", self.input_path, self._choose_input)
        self._add_file_row(control_frame, 1, "导出文件", self.output_path, self._choose_output)
        self._add_file_row(control_frame, 2, "权重文件", self.weight_path, self._choose_weight)

        ttk.Label(control_frame, text="权重模式").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=8)
        ttk.Combobox(control_frame, textvariable=self.weight_mode, values=["equal", "custom"], state="readonly", width=16).grid(row=3, column=1, sticky="w", pady=8)

        ttk.Label(control_frame, text="输出数量").grid(row=3, column=2, sticky="w", padx=(16, 8), pady=8)
        ttk.Entry(control_frame, textvariable=self.top_n, width=8).grid(row=3, column=3, sticky="w", pady=8)

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

        self.image_label = ttk.Label(right_frame, text="picture 目录中放入 PNG/GIF 后会显示在这里。", width=36, anchor="center", justify="center")
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
        picture_dir = Path.cwd() / "picture"
        candidates = []
        if picture_dir.exists():
            for suffix in ("*.png", "*.gif"):
                candidates.extend(sorted(picture_dir.glob(suffix)))
        if not candidates:
            return
        try:
            self.image_ref = PhotoImage(file=str(candidates[0]))
        except Exception:
            return
        self.image_label.configure(image=self.image_ref, text="")

    def load_inventory(self) -> None:
        try:
            self.current_document = load_inventory_document(self.input_path.get())
            self.current_inventory = document_to_inventory(self.current_document)
            self.status.set(f"已导入 {len(self.current_inventory)} 个素材条目")
        except (FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("导入失败", str(exc))

    def run_analysis(self) -> None:
        try:
            if not self.current_inventory:
                self.load_inventory()
            weights = None
            if self.weight_mode.get() == "custom":
                weights = load_weight_profile(self.weight_path.get(), set(BLUE_MATERIAL_IDS))
            result = run_cli(
                inventory=self.current_inventory,
                top_n=int(self.top_n.get()),
                weights=weights,
                weight_mode=self.weight_mode.get(),
            )
        except (PlannerError, FileNotFoundError, OSError, ValueError) as exc:
            messagebox.showerror("分析失败", str(exc))
            return

        for child in self.tree.get_children():
            self.tree.delete(child)

        for item in result.shortages:
            weighted_display = f"{item.weighted_equivalent:.2f}" if result.weight_mode == "custom" else "-"
            self.tree.insert("", END, values=(item.rank, item.item_id, item.name, f"{item.blue_equivalent:.2f}", weighted_display))

        self.status.set(f"分析完成，当前权重模式: {result.weight_mode}")

    def export_inventory(self) -> None:
        try:
            if not self.current_inventory:
                self.load_inventory()
            export_inventory_document(self.output_path.get(), inventory=self.current_inventory, template=self.current_document)
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