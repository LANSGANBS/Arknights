@echo off
setlocal

set SCRIPT_DIR=%~dp0
set FRONTEND_DIR=%SCRIPT_DIR%frontend

where npm >nul 2>nul
if errorlevel 1 (
    echo 启动失败: 本地静态站点需要 Node.js 18+ 和 npm。
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo 启动失败: 缺少 frontend\package.json
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo 首次启动，正在安装前端依赖...
    cd /d "%FRONTEND_DIR%"
    if exist "package-lock.json" (
        call npm ci
    ) else (
        call npm install
    )
    if errorlevel 1 (
        echo 前端依赖安装失败
        pause
        exit /b 1
    )
)

echo 正在启动本地静态站点...
cd /d "%FRONTEND_DIR%"
call npm run start -- %*
exit /b %errorlevel%
