# PowerShell 启动脚本 - 明日方舟素材均衡规划器
# 用法: .\start.ps1 [--cli|--desktop]
# 注意: 如果遇到执行策略错误，请运行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# 获取脚本所在目录
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

# 查找 Python 解释器
$PYTHON_BIN = $null
$PYTHON_EXTRA_ARG = ""

# 优先级 1: 检查虚拟环境
if ($env:VIRTUAL_ENV) {
    $venv_python = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    if (Test-Path $venv_python) {
        $PYTHON_BIN = $venv_python
    }
}

# 优先级 2: 检查本地 .venv
if (-not $PYTHON_BIN) {
    $local_venv = Join-Path $SCRIPT_DIR ".venv\Scripts\python.exe"
    if (Test-Path $local_venv) {
        $PYTHON_BIN = $local_venv
    }
}

# 优先级 3: 检查系统 PATH 中的 python3
if (-not $PYTHON_BIN) {
    try {
        $PYTHON_BIN = (Get-Command python3 -ErrorAction Stop).Source
    } catch {
        # 继续下一个优先级
    }
}

# 优先级 4: 检查系统 PATH 中的 python
if (-not $PYTHON_BIN) {
    try {
        $PYTHON_BIN = (Get-Command python -ErrorAction Stop).Source
    } catch {
        # 继续下一个优先级
    }
}

# 优先级 5: 检查系统 PATH 中的 py
if (-not $PYTHON_BIN) {
    try {
        $PYTHON_BIN = (Get-Command py -ErrorAction Stop).Source
        $PYTHON_EXTRA_ARG = "-3"
    } catch {
        # 继续
    }
}

if (-not $PYTHON_BIN) {
    Write-Host "启动失败: 未找到可用的 Python 3.10+ 解释器。" -ForegroundColor Red
    Write-Host "请先安装 Python，并确保 python3、python 或 py 可用。" -ForegroundColor Red
    Write-Host ""
    Write-Host "下载 Python: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查 Python 版本
try {
    $version_check = & $PYTHON_BIN $PYTHON_EXTRA_ARG -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "启动失败: 需要 Python 3.10 或更高版本。" -ForegroundColor Red
        Write-Host "当前 Python 路径: $PYTHON_BIN" -ForegroundColor Red
        Write-Host "请升级 Python 或修改 PYTHON_BIN 环境变量。" -ForegroundColor Red
        Read-Host "按 Enter 键退出"
        exit 1
    }
} catch {
    Write-Host "启动失败: 无法检查 Python 版本。" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查必要的 Python 模块
try {
    & $PYTHON_BIN $PYTHON_EXTRA_ARG -c "for m in ('json', 'http.server', 'pathlib', 'webbrowser'): __import__(m)" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "启动失败: 缺少必要的 Python 模块。" -ForegroundColor Red
        Read-Host "按 Enter 键退出"
        exit 1
    }
} catch {
    Write-Host "启动失败: 无法检查 Python 模块。" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查项目结构
if (-not (Test-Path "arknights_planner")) {
    Write-Host "启动失败: 当前目录缺少 arknights_planner 包目录" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查配置文件
if (-not (Test-Path "config.yaml")) {
    Write-Host "提示: 当前目录没有 config.yaml，将使用内置默认配置。" -ForegroundColor Yellow
}

# 处理命令行参数
if ($Arguments.Count -gt 0) {
    if ($Arguments[0] -eq "--cli") {
        $remainingArguments = if ($Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }
        & $PYTHON_BIN $PYTHON_EXTRA_ARG -m arknights_planner @remainingArguments
        exit $LASTEXITCODE
    }
    
    if ($Arguments[0] -eq "--desktop") {
        $remainingArguments = if ($Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }
        & $PYTHON_BIN $PYTHON_EXTRA_ARG -m arknights_planner.presentation.gui @remainingArguments
        exit $LASTEXITCODE
    }
}

# 检查和构建前端
try {
    Ensure-FrontendDist
} catch {
    Write-Host "前端检查失败: $_" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

# 获取端口号
$PORT = 8765
if (Test-Path "config.yaml") {
    $config_content = Get-Content "config.yaml" -Encoding UTF8
    foreach ($line in $config_content) {
        $line = $line.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains(":")) {
            $parts = $line.Split(":", 2)
            if ($parts[0].Trim() -eq "port") {
                $candidate = $parts[1].Trim().Trim('"').Trim("'")
                if ($candidate -match '^\d+$') {
                    $PORT = [int]$candidate
                }
                break
            }
        }
    }
}

# 启动 Web 服务
Write-Host "正在启动 Web 服务..." -ForegroundColor Green
& $PYTHON_BIN $PYTHON_EXTRA_ARG -m arknights_planner.presentation.web --open-browser @Arguments
exit $LASTEXITCODE

# ============================================
# 函数: 检查和构建前端
# ============================================
function Ensure-FrontendDist {
    $FRONTEND_DIR = Join-Path $SCRIPT_DIR "frontend"
    $DIST_INDEX = Join-Path $FRONTEND_DIR "dist\index.html"
    $NEEDS_INSTALL = $false
    $NEEDS_BUILD = $false

    if (-not (Test-Path (Join-Path $FRONTEND_DIR "package.json"))) {
        throw "缺少前端配置文件 frontend/package.json"
    }

    if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
        $NEEDS_INSTALL = $true
        $NEEDS_BUILD = $true
    }

    if (-not (Test-Path $DIST_INDEX)) {
        $NEEDS_BUILD = $true
    } else {
        $dist_time = (Get-Item $DIST_INDEX).LastWriteTime
        $watchFiles = @()
        $srcDir = Join-Path $FRONTEND_DIR "src"
        if (Test-Path $srcDir) {
            $watchFiles += Get-ChildItem $srcDir -File -Recurse
        }
        foreach ($file in @(
            (Join-Path $FRONTEND_DIR "index.html"),
            (Join-Path $FRONTEND_DIR "package.json"),
            (Join-Path $FRONTEND_DIR "package-lock.json"),
            (Join-Path $FRONTEND_DIR "vite.config.js")
        )) {
            if (Test-Path $file) {
                $watchFiles += Get-Item $file
            }
        }

        foreach ($file in $watchFiles) {
            if ($file.LastWriteTime -gt $dist_time) {
                $NEEDS_BUILD = $true
                break
            }
        }
    }

    if ($NEEDS_INSTALL -or $NEEDS_BUILD) {
        try {
            $npm_bin = (Get-Command npm -ErrorAction Stop).Source
        } catch {
            throw "Web 前端需要 Node.js 和 npm。请先安装 Node.js 18+。`n下载 Node.js: https://nodejs.org/"
        }
    }

    if ($NEEDS_INSTALL) {
        Write-Host "首次启动，正在安装前端依赖..." -ForegroundColor Green
        Push-Location $FRONTEND_DIR
        try {
            if (Test-Path "package-lock.json") {
                & $npm_bin ci
            } else {
                & $npm_bin install
            }
            if ($LASTEXITCODE -ne 0) {
                throw "前端依赖安装失败"
            }
        } finally {
            Pop-Location
        }
    }

    if ($NEEDS_BUILD) {
        Write-Host "正在构建 Web 前端..." -ForegroundColor Green
        Push-Location $FRONTEND_DIR
        try {
            & $npm_bin run build
            if ($LASTEXITCODE -ne 0) {
                throw "前端构建失败"
            }
        } finally {
            Pop-Location
        }
        
        if (-not (Test-Path $DIST_INDEX)) {
            throw "前端构建未生成 frontend/dist/index.html"
        }
    }
}
