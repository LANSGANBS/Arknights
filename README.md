# 明日方舟素材均衡规划器

这个项目的出发点很直接：
明日方舟里并不缺“为了某个目标材料该去刷哪关”的计算器，但似乎没有人单独做一个“我现在整体最缺哪几种蓝材”的工具。

这个工具就是为了解决这个空缺。
它不围绕某个单独材料做刷图建议，而是把你当前仓库里的素材统一折算到蓝色品质素材口径，然后告诉你现在整体最缺哪几种，并按从少到多排好序。

它更适合这类玩家：

- 已经有一定库存，不是刚入坑的新号
- 不想先选某个目标材料，再倒推去哪刷
- 更关心整个仓库是否失衡，而不是单次刷图收益
- 想先看“最缺什么”，再自己决定后续刷取计划

Web 界面默认先展示最缺的前 5 个蓝材，也可以展开查看完整排序。

## 配置文件

程序默认读取项目根目录下的 `config.yaml`。

第一次运行前，先复制一份示范配置：

```bash
cp config.example.yaml config.yaml
```

默认推荐把运行数据统一放在 `data/` 目录下。

默认配置项包括：

- `input_path`：导入库存文件
- `output_path`：导出库存文件
- `weight_path`：权重文件
- `material_image_dir`：素材图片目录
- `background_image_dir`：背景轮播图目录
- `top_n`：默认输出前几个素材
- `host` / `port`：Web 服务地址

如果你想改默认文件位置、默认输出数量或默认权重文件位置，直接改 `config.yaml`。

## 启动方式

如果你是第一次拉下仓库，推荐顺序是：

```bash
cp config.example.yaml config.yaml
./start.sh
```

直接运行：

```bash
./start.sh
```

默认会启动本地 Web 界面，并自动尝试打开浏览器。

当前 Web 前端已经迁移为 React + Liquid Glass 实现，构建产物由 Python Web 服务直接托管。

### 前置要求

- **Python 3.10+** - 核心运行环境
- **Node.js 18+ 和 npm** - 用于前端构建（首次运行或修改前端代码时需要）

### 首次运行

如果你是第一次运行，启动脚本会自动检查 `frontend/dist/` 是否存在或是否过期：

- 缺少前端依赖时会自动执行 `npm ci`（没有 `package-lock.json` 时退回 `npm install`）
- 缺少或过期的构建产物时会自动执行 `npm run build`

### Windows 用户指南

Windows 用户有三种启动方式：

#### 方式 1: PowerShell（推荐）

```powershell
.\start.ps1
```

如果遇到执行策略错误，请先运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 方式 2: 批处理脚本（CMD）

```cmd
start.bat
```

#### 方式 3: Git Bash 或 WSL

```bash
./start.sh
```

#### 方式 4: 脚本失效时手动启动

如果 `start.ps1` / `start.bat` 无法正常工作，可以直接一步一步执行。

PowerShell：

```powershell
Copy-Item config.example.yaml config.yaml
Set-Location frontend
npm install
npm run build
Set-Location ..
python -m arknights_planner.presentation.web --open-browser
```

CMD：

```cmd
copy config.example.yaml config.yaml
cd frontend
npm install
npm run build
cd ..
python -m arknights_planner.presentation.web --open-browser
```

如果你已经装好了前端依赖，并且 `frontend/dist` 也是最新的，可以跳过 `npm install` 和 `npm run build`。

### macOS 和 Linux 用户

```bash
./start.sh
```

Web 界面支持：

- 在页面中直接加减或修改素材数量
- 重新分析最缺少的蓝色素材
- 导出当前编辑后的库存状态
- 自动读取 `weight_path` 对应的权重文件，并直接展示加权结果
- 读取素材图目录和背景图目录作为页面资源

结果区标题旁提供了两个外链：

- 掉落推荐关卡：https://ark.yituliu.cn/
- 权重下载：https://ark.yituliu.cn/material/value

### 导入格式

本工具支持导入与企鹅物流一致的 JSON 格式。如果你已经在企鹅物流规划器中配置了库存，可以直接导出并导入到本工具中。

**推荐方式**：使用 [MAA（明日方舟视觉自动化方案）](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 自动识别游戏内的素材库存，然后导出为企鹅物流格式，再导入到本工具中。

导入文件位置由 `config.yaml` 中的 `input_path` 指定，默认为 `data/import.json`。

说明：

- Web 页面不再手动填写文件路径
- Web 和 GUI 默认从 `config.yaml` 读取导入、导出、权重文件和输出数量
- CLI 默认读取 `config.yaml` 里的导入和权重文件，但不会自动导出，只有显式传入 `--output` 才会写文件
- 默认输出数量是 5 个

如果你想使用命令行模式：

```bash
./start.sh --cli
```

如果你想尝试桌面 GUI 入口：

```bash
./start.sh --desktop
```

说明：

- 当前默认推荐使用 Web 界面
- 桌面 GUI 依赖 Tk 环境，不一定每台机器都可用

如果你修改了 `frontend/` 里的前端源码，也可以手动重新构建：

```bash
cd frontend
npm install
npm run build
```

## 权重文件

程序会默认尝试读取 `data/weight.json`，用于让高价值素材在排序里更敏感。

如果你需要重新获取权重文件，可以从 https://ark.yituliu.cn/material/value 下载 JSON 后替换 `data/weight.json`。

说明：

- 程序只读取素材项
- `data/weight.json` 里混入其他物品不会报错
- 非素材条目会被自动忽略
- 如果未找到权重文件，界面里的“加权后”会显示 `-`

## 常见用法

输出前 20 个最缺素材：

```bash
./start.sh --cli --top 20
```

指定别的导入文件和导出文件：

```bash
./start.sh --cli --input my_inventory.json --output my_result.json
```

指定别的权重文件：

```bash
./start.sh --cli --weight-file my_weight.json
```

## 导出功能是什么意思

这里的“导出”指的是：

- 你先从 `data/import.json` 导入一份初始库存
- 再在 Web 界面里修改当前素材数量
- 最后把你当前编辑后的库存另存为 `data/export.json`

导出不会反向修改导入文件。

`data/export.json` 会保持和 `data/import.json` 相同的通用库存格式：

- 不新增字段
- 不减少字段
- 保留 `@type`、`items`、`options`、`excludes`

分析结果只显示在终端或 Web 界面中，不写入 `export.json`。

## 项目结构

- `arknights_planner/`：正式包目录，核心逻辑、存储、表现层都在这里
- `frontend/`：React 前端源码目录，构建后输出到 `frontend/dist/`
- `assets/materials/`：素材图片目录
- `assets/backgrounds/`：背景轮播图目录
- `data/`：默认运行数据目录，存放导入库存、导出库存、权重文件
- `config.yaml`：统一默认配置入口

根目录不再保留单独的 `planner.py` 启动壳，命令行入口已经并回包内模块。

## 使用口径

- 只关注素材，不关注芯片、经验书、龙门币等其他物品
- 所有品质的素材都会强制折算到蓝色素材口径
- 高级素材会按真实工坊配方拆成多个蓝色素材贡献
- 结果的意义是帮助你把素材库存尽量拉平
