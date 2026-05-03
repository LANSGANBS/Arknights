#!/bin/sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
	echo "启动失败: 本地静态站点需要 Node.js 18+ 和 npm。"
	exit 1
fi

if [ ! -f "$FRONTEND_DIR/package.json" ]; then
	echo "启动失败: 缺少 frontend/package.json"
	exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
	echo "首次启动，正在安装前端依赖..."
	if [ -f "$FRONTEND_DIR/package-lock.json" ]; then
		(
			cd "$FRONTEND_DIR"
			npm ci
		)
	else
		(
			cd "$FRONTEND_DIR"
			npm install
		)
	fi
fi

echo "正在启动本地静态站点..."
cd "$FRONTEND_DIR"
exec npm run start -- "$@"
