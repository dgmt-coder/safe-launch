# 数据库迁移器

PostgreSQL + Alembic 迁移全流程向导：检测变更 → 生成迁移 → 执行 → 验证 → 回滚。

## 职责

管理数据库 schema 变更的完整生命周期：
- 对比 SQLAlchemy Model 与当前数据库状态，自动生成迁移脚本
- 审查和修正自动生成的脚本
- 执行迁移并验证
- 出问题时回滚到指定版本

## 输入

- **action**: `detect` | `generate` | `upgrade` | `downgrade` | `history` | `verify`
- **message**:（generate 时）迁移消息，如 `"add_review_records_table"`
- **revision**:（downgrade 时）目标版本号，`"head"` 表示最新，`"-1"` 表示回退一步
- **auto_apply**: 生成后是否自动执行，默认 false

## 项目配置约定

`alembic.ini` 和 `alembic/env.py` 中：
- 使用异步引擎：`sqlalchemy.ext.asyncio.create_async_engine`
- `target_metadata = Base.metadata`
- 数据库 URL 从环境变量 `DATABASE_URL` 读取
- 迁移文件编码：UTF-8，使用 `sa.func.now()` 而非 `datetime.now()`

## 执行步骤

### 1. detect — 检测变更

```bash
alembic revision --autogenerate -m "temp_check" 2>&1
```

- 对比 `Base.metadata` 和当前数据库 schema
- 列出新增/修改/删除的表和列
- 如果无变更：报告"数据库与模型一致，无需迁移"
- 如果是首次迁移（无 `alembic_version` 表）：提示需要用 `--init` 初始化

### 2. generate — 生成迁移脚本

```bash
alembic revision --autogenerate -m "{message}"
```

生成后自动审查以下问题：

| 检查项 | 说明 |
|--------|------|
| UUID 默认值 | PostgreSQL 必须用 `sa.text("gen_random_uuid()")`，而非 Python `uuid.uuid4` |
| 时间戳默认值 | 用 `server_default=sa.func.now()`，不要遗漏 `onupdate` |
| 外键 ondelete | 检查是否与 Model 定义一致 |
| 索引 | 确认 `op.create_index` 在 `upgrade` 中，`op.drop_index` 在 `downgrade` 中 |
| 数据丢失风险 | DROP COLUMN / DROP TABLE 导致数据丢失 → 标注 warning |
| 可空列 | 新增 NOT NULL 列无默认值 → 标注 error |
| 枚举新增 | PostgreSQL ENUM 新增需手动 `ALTER TYPE ... ADD VALUE` |

### 3. upgrade — 执行迁移

```bash
alembic upgrade head
```

- 执行前自动备份当前版本号
- 执行后验证：对比 schema 是否与 Model 一致
- 输出执行日志（成功/失败的 revision）

### 4. downgrade — 回滚

```bash
alembic downgrade {revision}
```

- 回滚前警告：数据可能丢失（DROPPED columns）
- 确认后再执行
- 回滚后验证：schema 是否与目标版本一致

### 5. history — 查看历史

```bash
alembic history
```

输出迁移历史表格。

### 6. verify — 一致性验证

对比当前数据库 schema 与所有 Model 定义：
- 运行 `alembic check`（Alembic 1.13+）
- 没有 check 命令时，执行一次空 autogenerate 看是否有差异
- 列出不一致项并给出修复建议

## 常见问题处理

### 空迁移（检测不到变更）

原因：`target_metadata` 未正确配置或 Model 未导入。
处理：检查 `alembic/env.py` 是否导入了所有 Model 的 Base。

### 迁移生成不完整

原因：Alembic 无法检测某些变更（表重命名、列类型变更、ENUM 修改）。
处理：手动补充迁移脚本，并标注 `# Manual adjustment`。

### 迁移冲突

原因：多人同时生成迁移，分支上有不同的 head。
处理：`alembic merge` 创建合并迁移，或 rebase 后重新生成。

### 生产环境安全规则

- **绝不** `downgrade` 到有数据丢失的版本
- **绝不** 手动修改已应用的生产数据库
- 所有迁移先在 staging 环境验证
- 迁移脚本纳入 Git，与代码一起 Code Review

## 输出格式

```
## 迁移报告

**操作**: {action}
**数据库**: {database_url 脱敏}

### 状态

{成功/失败/无变更}

### 变更详情（detect 时）

| 类型 | 对象 | 说明 |
|------|------|------|
| 新增表 | review_records | 8 列, 2 索引 |
| 新增列 | keyword_rules.priority | Integer, nullable |

### 审查结果（generate 时）

| 检查项 | 状态 | 备注 |
|--------|------|------|
| UUID 默认值 | ✅ | gen_random_uuid() |
| 时间戳默认值 | ✅ | func.now() |
| 外键 ondelete | ⚠️ | keyword_rules.category_id 缺少 ondelete |
| 数据丢失风险 | ✅ | 无 |
| NOT NULL 默认值 | ✅ | 均有默认值 |

### 执行日志（upgrade/downgrade 时）

{revision} → {revision}: OK
```

## 关键规则

- PostgreSQL 特化：UUID 用 `gen_random_uuid()`，JSON 用 `JSONB`
- 异步引擎：迁移脚本中的连接必须用 `run_async`
- 迁移文件不可删除，只可新增
- 每次迁移只做一件事（一个业务变更一个 revision）
- 自动检测不准时坦诚告知需要手动调整的部分
- 生产环境操作额外确认
