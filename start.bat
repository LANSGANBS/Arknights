@echo off
REM Windows 批处理启动脚本 - 明日方舟素材均衡规划器
REM 用法: start.bat [--cli|--desktop]

setlocal enabledelayedexpansion

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM 查找 Python 解释器
set PYTHON_BIN=
set PYTHON_EXTRA_ARG=

REM 优先级 1: 检查虚拟环境
if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        set PYTHON_BIN=%VIRTUAL_ENV%\Scripts\python.exe
    )
)

REM 优先级 2: 检查本地 .venv
if "!PYTHON_BIN!"=="" (
    if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
        set PYTHON_BIN=%SCRIPT_DIR%.venv\Scripts\python.exe
    )
)

REM 优先级 3: 检查系统 PATH 中的 python3
if "!PYTHON_BIN!"=="" (
    for /f "delims=" %%i in ('where python3 2^>nul') do (
        set PYTHON_BIN=%%i
        goto :found_python
    )
)

REM 优先级 4: 检查系统 PATH 中的 python
if "!PYTHON_BIN!"=="" (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        set PYTHON_BIN=%%i
        goto :found_python
    )
)

REM 优先级 5: 检查系统 PATH 中的 py
if "!PYTHON_BIN!"=="" (
    for /f "delims=" %%i in ('where py 2^>nul') do (
        set PYTHON_BIN=%%i
        set PYTHON_EXTRA_ARG=-3
        goto :found_python
    )
)

:found_python
if "!PYTHON_BIN!"=="" (
    echo 启动失败: 未找到可用的 Python 3.10+ 解释器。
    echo 请先安装 Python，并确保 python3、python 或 py 可用。
    echo.
    echo 下载 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 Python 版本
"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo 启动失败: 需要 Python 3.10 或更高版本。
    echo 当前 Python 路径: !PYTHON_BIN!
    echo 请升级 Python 或修改 PYTHON_BIN 环境变量。
    pause
    exit /b 1
)

REM 检查必要的 Python 模块
"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -c "for m in ('json', 'http.server', 'pathlib', 'webbrowser'): __import__(m)" >nul 2>&1
if errorlevel 1 (
    echo 启动失败: 缺少必要的 Python 模块。
    pause
    exit /b 1
)

REM 检查项目结构
if not exist "arknights_planner" (
    echo 启动失败: 当前目录缺少 arknights_planner 包目录
    pause
    exit /b 1
)

REM 检查配置文件
if not exist "config.yaml" (
    echo 提示: 当前目录没有 config.yaml，将使用内置默认配置。
)

REM 处理命令行参数
if "%1"=="--cli" goto :run_cli
if "%1"=="--desktop" goto :run_desktop

REM 检查和构建前端
call :ensure_frontend_dist
if errorlevel 1 exit /b 1

REM 获取端口号
for /f "delims=" %%i in ('"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -c "
from pathlib import Path
port = 8765
config_path = Path('config.yaml')
if config_path.exists():
    for line in config_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or ':' not in stripped:
            continue
        key, value = stripped.split(':', 1)
        if key.strip() == 'port':
            candidate = value.strip().strip('\"').strip(\"'\")
            if candidate.lstrip('-').isdigit():
                port = int(candidate)
            break
print(port)
"') do set PORT=%%i

REM 启动 Web 服务
echo 正在启动 Web 服务...
"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -m arknights_planner.presentation.web --open-browser %*
exit /b !errorlevel!

REM ============================================
REM 子程序: 检查和构建前端
REM ============================================
:ensure_frontend_dist
setlocal enabledelayedexpansion

set FRONTEND_DIR=%SCRIPT_DIR%frontend
set DIST_INDEX=%FRONTEND_DIR%\dist\index.html
set NEEDS_INSTALL=0
set NEEDS_BUILD=0
set NPM_BIN=

if not exist "%FRONTEND_DIR%\package.json" (
    echo 启动失败: 缺少前端配置文件 frontend/package.json
    endlocal
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    set NEEDS_INSTALL=1
    set NEEDS_BUILD=1
)

if !NEEDS_BUILD! equ 0 (
    for /f "delims=" %%i in ('set "PLANNER_FRONTEND_DIR=%FRONTEND_DIR%" ^&^& "%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -c "from pathlib import Path; import os; frontend = Path(os.environ['PLANNER_FRONTEND_DIR']); dist = frontend / 'dist' / 'index.html'; watch_files = [path for path in (frontend / 'src').rglob('*') if path.is_file()]; watch_files.extend(path for path in (frontend / 'index.html', frontend / 'package.json', frontend / 'package-lock.json', frontend / 'vite.config.js') if path.exists()); print(1 if (not dist.exists() or any(path.stat().st_mtime ^> dist.stat().st_mtime for path in watch_files)) else 0)"') do set NEEDS_BUILD=%%i
)

if !NEEDS_INSTALL! equ 1 (
    goto :check_npm
)

if !NEEDS_BUILD! equ 1 (
    goto :check_npm
)

goto :install_or_build

:check_npm
for /f "delims=" %%i in ('where npm 2^>nul') do (
    set NPM_BIN=%%i
    goto :install_or_build
)
if "!NPM_BIN!"=="" (
    echo 启动失败: Web 前端需要 Node.js 和 npm。
    echo 请先安装 Node.js 18+。
    echo 下载 Node.js: https://nodejs.org/
    endlocal
    exit /b 1
)

:install_or_build
if !NEEDS_INSTALL! equ 1 (
    echo 首次启动，正在安装前端依赖...
    if exist "%FRONTEND_DIR%\package-lock.json" (
        cd /d "%FRONTEND_DIR%"
        call "!NPM_BIN!" ci
        if errorlevel 1 (
            echo 前端依赖安装失败
            endlocal
            exit /b 1
        )
        cd /d "%SCRIPT_DIR%"
    ) else (
        cd /d "%FRONTEND_DIR%"
        call "!NPM_BIN!" install
        if errorlevel 1 (
            echo 前端依赖安装失败
            endlocal
            exit /b 1
        )
        cd /d "%SCRIPT_DIR%"
    )
)

if !NEEDS_BUILD! equ 1 (
    echo 正在构建 Web 前端...
    cd /d "%FRONTEND_DIR%"
    call "!NPM_BIN!" run build
    if errorlevel 1 (
        echo 前端构建失败
        endlocal
        exit /b 1
    )
    cd /d "%SCRIPT_DIR%"
    
    if not exist "%DIST_INDEX%" (
        echo 启动失败: 前端构建未生成 frontend/dist/index.html
        endlocal
        exit /b 1
    )
)

endlocal
exit /b 0

:run_cli
shift
"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -m arknights_planner %*
exit /b %errorlevel%

:run_desktop
shift
"%PYTHON_BIN%" %PYTHON_EXTRA_ARG% -m arknights_planner.presentation.gui %*
exit /b %errorlevel%
