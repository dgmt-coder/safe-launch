# 游戏预发布内容审核系统

基于 **Litestar** + **DeepSeek** + **Qdrant** 的智能内容审核平台。

## 技术栈

| 层面 | 选型 |
|------|------|
| Web 框架 | Litestar 2.8+ |
| ORM | SQLAlchemy 2.0 异步 + asyncpg |
| 数据校验 | Pydantic v2 + pydantic-settings |
| LLM | DeepSeek API (Chat + JSON Mode) |
| 向量数据库 | Qdrant |
| Embedding | OpenAI text-embedding-3-small |
| 缓存 | Redis |
| 数据库 | PostgreSQL |
| 迁移 | Alembic (异步) |
| HTTP 客户端 | httpx (异步) |
| 包管理 | uv |
| 代码质量 | Ruff + Mypy (strict) |
| 测试 | pytest + pytest-asyncio + pytest-cov |

## 分层架构

```
Controller (app/api/controllers/)  — HTTP 参数校验、路由
    ↓
Service (app/services/)            — 业务编排、事务管理
    ↓
Repository (app/services/repos/)   — 纯数据访问
Module (app/modules/)              — 领域算法、外部 API 调用
    ↓
Model (app/models/)                — SQLAlchemy ORM
Schema (app/schemas/)              — Pydantic v2 校验
    ↓
Core (app/core/)                   — 配置、常量、基础设施
```

**依赖方向铁律**: 只能从上向下依赖，绝不反向。

## 三层检测架构（文字审核）

```
L1: 违规关键词匹配 → 毫秒级，精确命中
L2: RAG 法规检索  → Qdrant + OpenAI Embedding，语义匹配
L3: DeepSeek LLM  → 深度语义分析，JSON 结构化输出

各层独立运行，缺失时优雅降级
```

## 审核维度

| 维度 | 说明 | 权重 |
|------|------|------|
| 法律法规红线 | 政治敏感、色情、暴力、赌博、毒品等 | 1.0 |
| 游戏基本原则 | 健康向上、社会主义核心价值观 | 0.9 |
| 游戏内合规要求 | 版号、实名认证、防沉迷等 | 0.8 |
| 美术资源内容审核 | 美术资源合规性 | 0.7 |

## 项目结构

```
safe-launch/
├── app/
│   ├── api/controllers/     # 5 个 Controller (11 个端点)
│   ├── core/                # 配置、常量、数据库、Redis、异常
│   ├── models/              # SQLAlchemy 2.0 ORM
│   ├── schemas/             # Pydantic v2 数据校验
│   ├── modules/             # 领域模块
│   │   ├── text_review/     # L1 关键词 + L2 RAG桥接 + L3 LLM
│   │   ├── rag/             # Embedding + Qdrant + 检索器
│   │   └── image_review/    # 图片校验 + 外部检测服务
│   └── services/            # 业务编排 + Repository
├── tests/                   # 36 个测试 (unit + integration)
│   ├── unit/                # Schema / Module / Service 单测
│   ├── integration/         # API / Database 集成测试
│   └── factories/           # 测试数据工厂
├── data/
│   ├── keywords/            # L1 关键词库 (按违规类别分文件)
│   └── regulations/         # RAG 法规文档种子数据
├── migrations/              # Alembic 异步迁移
├── scripts/                 # 启动脚本
└── .agents/                 # 7 个开发辅助 Agent
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/review/text` | 单条文字审核 |
| POST | `/api/v1/review/text/batch` | 批量文字审核 |
| POST | `/api/v1/review/image` | 单张图片审核 |
| POST | `/api/v1/review/image/batch` | 批量图片审核 |
| POST | `/api/v1/rag/search` | RAG 法规检索 |
| POST | `/api/v1/rag/documents` | 添加知识库文档 |
| DELETE | `/api/v1/rag/documents/{id}` | 删除知识库文档 |
| GET | `/api/v1/history/records` | 审核历史分页查询 |
| GET | `/api/v1/history/records/{id}` | 单条审核记录详情 |
| GET | `/api/v1/history/stats` | 审核统计数据 |

## 快速开始

### 环境要求

- Python >= 3.12
- uv
- PostgreSQL 14+ (需创建数据库 `safe_launch`)
- Redis (可选，默认 localhost)
- Qdrant (可选，默认 localhost)

### 1. 安装依赖

```bash
E:/software_best/miniconda3/envs/py312/Scripts/uv sync
E:/software_best/miniconda3/envs/py312/Scripts/uv sync --extra dev
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置：
#   - DATABASE_URL: PostgreSQL 连接串
#   - DEEPSEEK_API_KEY: DeepSeek API Key
#   - OPENAI_API_KEY: OpenAI API Key (用于 Embedding)
#   - IMAGE_REVIEW_API_URL: 图片检测私有服务地址 (可选)
```

### 3. 数据库迁移

```bash
# 生成首次迁移
uv run alembic revision --autogenerate -m "init"

# 执行迁移
uv run alembic upgrade head

# 回滚一步
uv run alembic downgrade -1

# 查看迁移历史
uv run alembic history

# 生成 SQL 脚本 (离线模式)
uv run alembic upgrade head --sql
```

### 4. 启动服务

Windows (PowerShell):
```powershell
.\scripts\start.ps1
```

Linux / macOS:
```bash
bash scripts/start.sh
```

手动启动:
```bash
uv run litestar run --app app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/health 确认服务正常。

### 5. 运行检查

```bash
# 运行全部测试
uv run pytest tests/ -v

# 仅运行单元测试
uv run pytest tests/unit/ -v

# 运行并生成覆盖率报告
uv run pytest tests/ -v --cov=app --cov-report=html

# 仅运行指定模块测试
uv run pytest tests/unit/test_modules/test_keyword_matcher.py -v

# 代码风格检查
uv run ruff check app/

# 类型检查
uv run mypy app/

# 验证 Core 层可导入
uv run python -c "from app.core.config.settings import settings; from app.core.constants import ReviewDimension; print('Core OK')"

# 验证 Schema 校验
uv run python -c "from app.schemas.review import ReviewCreate; r=ReviewCreate(content='test', content_type='text', review_dimension='legal'); print('Schema OK')"

# 验证应用可创建
uv run python -c "from app.main import create_app; app=create_app(); print('App OK')"
```

## 常用命令速查

| 场景 | 命令 |
|------|------|
| 安装依赖 | `uv sync && uv sync --extra dev` |
| 启动服务 | `uv run litestar run --app app.main:app --reload` |
| 运行测试 | `uv run pytest tests/ -v` |
| 覆盖率报告 | `uv run pytest tests/ -v --cov=app --cov-report=html` |
| Lint 检查 | `uv run ruff check app/` |
| Lint 自动修复 | `uv run ruff check app/ --fix` |
| 类型检查 | `uv run mypy app/` |
| 生成迁移 | `uv run alembic revision --autogenerate -m "描述"` |
| 执行迁移 | `uv run alembic upgrade head` |
| 回滚迁移 | `uv run alembic downgrade -1` |
| 迁移历史 | `uv run alembic history` |
| 导入 RAG 种子数据 | 通过 API: `POST /api/v1/rag/documents` |
