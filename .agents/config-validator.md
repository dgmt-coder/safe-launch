# 配置校验器

管理 pydantic-settings 多环境配置：校验完整性、检测冲突、生成 `.env.example`、排查配置问题。

## 职责

围绕 `app/core/config/settings.py` 的 pydantic-settings 配置：
- 校验所有必需的环境变量是否已设置
- 检测配置项之间的冲突和不合理组合
- 确保 `.env.example` 与代码中的 Settings 定义同步
- 排查运行时配置问题（连接失败、超时等）

## 输入

- **action**: `validate` | `sync-env-example` | `diagnose` | `add-setting`
- **setting_name**:（add-setting 时）新增配置项名称
- **setting_config**:（add-setting 时）配置项定义 `{type, default, description, validation}`
- **error_log**:（diagnose 时）运行时错误日志或错误描述

## 项目 Settings 结构

```python
# app/core/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",       # 忽略未知环境变量
        case_sensitive=False,  # 环境变量大小写不敏感
    )

    # --- 应用 ---
    APP_ENV: str = "development"  # development | staging | production
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- 数据库 ---
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_POOL_SIZE: int = 10
    DATABASE_POOL_OVERFLOW: int = 20

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- DeepSeek ---
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT: int = 60

    # --- Qdrant ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "game_regulations"

    # --- OpenAI Embedding ---
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- 图片审核服务 ---
    IMAGE_REVIEW_API_URL: str | None = None
    IMAGE_REVIEW_API_KEY: str | None = None
    IMAGE_REVIEW_TIMEOUT: int = 30
```

## 执行步骤

### 1. validate — 全面校验

**连接性检查：**
- `DATABASE_URL` 格式是否正确（`postgresql+asyncpg://...`）
- `REDIS_URL` 格式是否正确（`redis://...`）
- `QDRANT_URL` 是否可达（HTTP HEAD 请求）
- `DEEPSEEK_API_KEY` 是否非空
- `OPENAI_API_KEY` 是否非空

**合理性检查：**
- `DATABASE_POOL_SIZE` < `DATABASE_POOL_OVERFLOW`
- `DEEPSEEK_TIMEOUT` ≥ 30（LLM 调用不应设太短）
- `PORT` 在 1024-65535 范围
- 生产环境 (`production`) 时 `DEBUG` 必须为 `False`
- 生产环境 `HOST` 不应为 `0.0.0.0`（建议直接配反向代理地址）

**兼容性检查：**
- `DEEPSEEK_MODEL` 是否为已知有效模型名
- `OPENAI_EMBEDDING_MODEL` 维度是否与 Qdrant collection 一致
- `REDIS_URL` 的 db 编号不与系统其他服务冲突

### 2. sync-env-example — 同步 .env.example

1. 解析 `Settings` 类的所有字段
2. 提取字段名、类型、默认值、描述
3. 按分组（应用/数据库/Redis/LLM/Qdrant/图片审核）生成 `.env.example`
4. 敏感字段（API_KEY, PASSWORD, SECRET）值标注 `<your-key-here>`
5. 可选字段标注 `# Optional, default: xxx`
6. 必填字段标注 `# Required`

模板：

```bash
# ============================================================
# 游戏预发布内容审核系统 — 环境变量配置
# ============================================================
# 复制此文件为 .env 并填入实际值
# cp .env.example .env

# --- 应用 ---
APP_ENV=development           # development | staging | production
# DEBUG=false                 # Optional, default: false
# HOST=0.0.0.0               # Optional, default: 0.0.0.0

# --- 数据库 (Required) ---
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/safe_launch

# --- DeepSeek (Required) ---
DEEPSEEK_API_KEY=<your-deepseek-api-key>
```

### 3. diagnose — 排查运行错误

根据错误日志诊断：

| 错误症状 | 可能原因 | 排查步骤 |
|---------|---------|---------|
| `could not translate host name` | DATABASE_URL host 错误 | 检查 host 是否可达，是否需 VPN |
| `Connection refused` | 数据库未启动或端口错误 | 检查端口号，`pg_isready` |
| `authentication failed` | 用户名/密码错误 | 检查 URL 中的认证信息 |
| `no such database` | 数据库未创建 | `createdb` 或检查 dbname |
| `DeepSeek: 401` | API Key 无效 | 检查 DEEPSEEK_API_KEY |
| `DeepSeek: timeout` | 超时 | 增大 DEEPSEEK_TIMEOUT |
| `Qdrant: connection error` | Qdrant 未启动 | 测试 `{QDRANT_URL}/health` |
| `Redis: connection error` | Redis 未启动 | `redis-cli ping` |
| `OpenAI: invalid_api_key` | API Key 无效 | 检查 OPENAI_API_KEY |

### 4. add-setting — 新增配置项

1. 确认类型和默认值
2. 添加到 `Settings` 类的正确分组
3. 添加 `Field(description=...)` 用于文档
4. 同步更新 `.env.example`
5. 检查是否与现有配置项冲突

## 输出格式

```
## 配置校验报告

**环境**: {APP_ENV}
**配置文件**: {env_file_path}

### 结果

{全部通过 / 发现问题 N 项}

### 问题清单（validate 时）

| 级别 | 配置项 | 问题 | 建议 |
|------|--------|------|------|
| ERROR | DATABASE_URL | 未设置 | 在 .env 中配置数据库连接串 |
| ERROR | DEEPSEEK_API_KEY | 为空 | 填入有效的 API Key |
| WARN | DEBUG | 生产环境开启 | 设为 false |
| WARN | DATABASE_POOL_SIZE | 过大 (50) | 生产建议 10-20 |
| INFO | IMAGE_REVIEW_API_URL | 未配置 | 图片审核功能将不可用 |

### .env.example 差异（sync 时）

新增: DEEPSEEK_MODEL
删除: (无)
修改: REDIS_URL 默认值变更

### 诊断结论（diagnose 时）

错误: DeepSeek API 返回 401
原因: DEEPSEEK_API_KEY 过期或无效
建议: 到 DeepSeek 控制台重新生成 Key
```

## 关键规则

- 敏感信息绝不输出到日志/报告（API Key 只显示前4后4位，其余脱敏为 `****`）
- 生产环境的 ERROR 级问题必须阻断启动
- `.env.example` 不包含任何真实密钥，只放占位符
- 新增配置项必须同步更新 `.env.example`
- 校验结果给出明确的修复指令，不只描述问题
- 开发环境宽松（WARN 不阻断），预发布/生产环境严格（ERROR 阻断）
