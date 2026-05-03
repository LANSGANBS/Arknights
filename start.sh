#!/bin/sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
PYTHON_EXTRA_ARG=""

if [ -z "$PYTHON_BIN" ] && [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
	PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
fi

if [ -z "$PYTHON_BIN" ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
	PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
fi

if [ -z "$PYTHON_BIN" ]; then
	for candidate in python3 python; do
		if command -v "$candidate" >/dev/null 2>&1; then
			PYTHON_BIN="$(command -v "$candidate")"
			break
		fi
	done
fi

if [ -z "$PYTHON_BIN" ] && command -v py >/dev/null 2>&1; then
	PYTHON_BIN="py"
	PYTHON_EXTRA_ARG="-3"
fi

if [ -z "$PYTHON_BIN" ]; then
	echo "启动失败: 未找到可用的 Python 3.10+ 解释器。请先安装 Python，并确保 python3、python 或 py 可用。"
	exit 1
fi

"$PYTHON_BIN" ${PYTHON_EXTRA_ARG:+$PYTHON_EXTRA_ARG} - <<'PY'
import sys

required = (3, 10)
if sys.version_info < required:
		raise SystemExit(f"启动失败: 需要 Python {required[0]}.{required[1]} 或更高版本，当前为 {sys.version.split()[0]}")

for module in ("json", "http.server", "pathlib", "webbrowser"):
		__import__(module)
PY

if [ ! -d "arknights_planner" ]; then
	echo "启动失败: 当前目录缺少 arknights_planner 包目录"
	exit 1
fi

if [ ! -f "config.yaml" ]; then
	echo "提示: 当前目录没有 config.yaml，将使用内置默认配置。"
fi

if [ "${1:-}" = "--cli" ]; then
	shift
	exec "$PYTHON_BIN" -m arknights_planner "$@"
	exit 0
fi

if [ "${1:-}" = "--desktop" ]; then
	shift
	exec "$PYTHON_BIN" -m arknights_planner.presentation.gui "$@"
	exit 0
fi

ensure_frontend_dist() {
	FRONTEND_DIR="$SCRIPT_DIR/frontend"
	DIST_INDEX="$FRONTEND_DIR/dist/index.html"
	NEEDS_INSTALL=0
	NEEDS_BUILD=0

	if [ ! -f "$FRONTEND_DIR/package.json" ]; then
		echo "启动失败: 缺少前端配置文件 frontend/package.json"
		exit 1
	fi

	if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
		NEEDS_INSTALL=1
		NEEDS_BUILD=1
	fi

	if [ ! -f "$DIST_INDEX" ]; then
		NEEDS_BUILD=1
	elif find "$FRONTEND_DIR/src" "$FRONTEND_DIR/index.html" "$FRONTEND_DIR/package.json" "$FRONTEND_DIR/package-lock.json" "$FRONTEND_DIR/vite.config.js" -type f -newer "$DIST_INDEX" | grep -q . 2>/dev/null; then
		NEEDS_BUILD=1
	fi

	if [ "$NEEDS_INSTALL" -eq 1 ] || [ "$NEEDS_BUILD" -eq 1 ]; then
		if ! command -v npm >/dev/null 2>&1; then
			echo "启动失败: Web 前端需要 Node.js 和 npm。请先安装 Node.js 18+。"
			exit 1
		fi
	fi

	if [ "$NEEDS_INSTALL" -eq 1 ]; then
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

	if [ "$NEEDS_BUILD" -eq 1 ]; then
		echo "正在构建 Web 前端..."
		(
			cd "$FRONTEND_DIR"
			npm run build
		)
		if [ ! -f "$DIST_INDEX" ]; then
			echo "启动失败: 前端构建未生成 frontend/dist/index.html"
			exit 1
		fi
	fi
}

ensure_frontend_dist

PIDS=""

PORT="$($PYTHON_BIN - <<'PY'
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
			candidate = value.strip().strip('"').strip("'")
			if candidate.lstrip('-').isdigit():
				port = int(candidate)
			break
print(port)
PY
)"

if command -v lsof >/dev/null 2>&1; then
	PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
	if [ -n "$PIDS" ]; then
		echo "检测到端口 $PORT 已被占用，正在安全停止旧服务..."
		for PID in $PIDS; do
			kill -TERM "$PID" 2>/dev/null || true
		done
		PLANNER_PORT="$PORT" PLANNER_PIDS="$PIDS" "$PYTHON_BIN" ${PYTHON_EXTRA_ARG:+$PYTHON_EXTRA_ARG} - <<'PY'
import os
import signal
import sys
import time

port = int(os.environ['PLANNER_PORT'])
pids = [int(pid) for pid in os.environ.get('PLANNER_PIDS', '').split() if pid.strip()]
deadline = time.time() + 3.0
while time.time() < deadline:
	alive = []
	for pid in pids:
		try:
			os.kill(pid, 0)
			alive.append(pid)
		except OSError:
			pass
	if not alive:
		sys.exit(0)
	time.sleep(0.1)

for pid in alive:
	try:
		os.kill(pid, signal.SIGKILL)
	except OSError:
		pass
PY
	fi
fi

exec env PLANNER_PORT="$PORT" PLANNER_PIDS="$PIDS" "$PYTHON_BIN" ${PYTHON_EXTRA_ARG:+$PYTHON_EXTRA_ARG} -m arknights_planner.presentation.web --open-browser "$@"