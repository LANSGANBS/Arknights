# PowerShell 本地启动脚本 - 静态前端版
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$FRONTEND_DIR = Join-Path $SCRIPT_DIR "frontend"

try {
    $npm_bin = (Get-Command npm -ErrorAction Stop).Source
} catch {
    Write-Host "启动失败: 本地静态站点需要 Node.js 18+ 和 npm。" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

if (-not (Test-Path (Join-Path $FRONTEND_DIR "package.json"))) {
    Write-Host "启动失败: 缺少 frontend\package.json" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
    exit 1
}

if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
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

Write-Host "正在启动本地静态站点..." -ForegroundColor Green
Push-Location $FRONTEND_DIR
try {
    & $npm_bin run start -- @Arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
