# safe-launch Windows 启动脚本
# PowerShell

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  safe-launch 游戏预发布内容审核系统" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 uv
$uv = "E:\software_best\miniconda3\envs\py312\Scripts\uv.exe"
if (-not (Test-Path $uv)) {
    Write-Host "ERROR: uv not found at $uv" -ForegroundColor Red
    exit 1
}

# 检查 .env
if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env not found, copying from .env.example" -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[INFO] Please edit .env with your actual settings" -ForegroundColor Yellow
}

# 同步依赖
Write-Host "[1/3] Syncing dependencies..." -ForegroundColor Green
& $uv sync 2>&1 | Out-Null

# 数据库迁移
Write-Host "[2/3] Running database migrations..." -ForegroundColor Green
& $uv run alembic upgrade head 2>&1

# 启动服务
Write-Host "[3/3] Starting server..." -ForegroundColor Green
Write-Host ""
& $uv run litestar run --app app.main:app --reload --host 0.0.0.0 --port 8000
