#!/bin/bash
# safe-launch Unix 启动脚本

set -e

echo "========================================"
echo "  safe-launch 游戏预发布内容审核系统"
echo "========================================"
echo ""

# 检查 uv
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found in PATH, please install uv first"
    exit 1
fi

# 检查 .env
if [ ! -f ".env" ]; then
    echo "[WARN] .env not found, copying from .env.example"
    cp .env.example .env
    echo "[INFO] Please edit .env with your actual settings"
fi

# 同步依赖
echo "[1/3] Syncing dependencies..."
uv sync 2>&1

# 数据库迁移
echo "[2/3] Running database migrations..."
uv run alembic upgrade head

# 启动服务
echo "[3/3] Starting server..."
echo ""
uv run litestar run --app app.main:app --reload --host 0.0.0.0 --port 8000
