# 数据模型构建器

从需求描述生成 SQLAlchemy 2.0 ORM 模型 + Pydantic v2 Schema + Alembic 迁移脚本，确保三者字段一致。

## 职责

根据实体描述，一次性生成三件套：
- `app/models/*.py` — SQLAlchemy 2.0 异步 ORM 模型
- `app/schemas/*.py` — Pydantic v2 请求/响应 Schema（Create / Update / Response / ListResponse）
- `migrations/versions/*.py` — Alembic 迁移脚本

同时更新 `app/models/__init__.py` 和 `app/schemas/__init__.py` 的导出。

## 输入

- **entity_name**: 实体名（PascalCase，如 `ReviewRecord`、`KeywordRule`）
- **fields**: 字段列表，每项含名称、类型、约束、默认值、中文说明
- **relationships**:（可选）关联关系 `[{target, cardinality, back_populates}]`
- **generate_migration**: 是否同时生成迁移脚本，默认 true

## 项目约定

### 所有实体必须包含

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
)
created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
updated_at: Mapped[datetime] = mapped_column(
    server_default=func.now(), onupdate=func.now(), nullable=False
)
```

### 字段类型映射

| 业务类型 | SQLAlchemy | Pydantic |
|---------|-----------|----------|
| 短文本(≤255) | `String(255)` | `str` + `max_length=255` |
| 长文本 | `Text` | `str` |
| 整数 | `Integer` / `BigInteger` | `int` |
| 布尔 | `Boolean` | `bool` |
| 日期时间 | `DateTime(timezone=True)` | `datetime` |
| JSON | `JSONB` (PG 方言) | `dict` / `list` |
| UUID 外键 | `UUID(as_uuid=True), ForeignKey(...)` | `uuid.UUID` |
| 枚举 | `String(50)` | `str` + `field_validator` |
| 小数 | `Numeric(precision, scale)` | `Decimal` |

### 表名 = 蛇形复数

`ReviewRecord` → `review_records`，`KeywordRule` → `keyword_rules`

### Schema 四件套

- `XxxBase` — 共享业务字段 + Field 校验
- `XxxCreate` — 继承 Base + 必填外键
- `XxxUpdate` — 独立定义，所有字段 Optional（PATCH 语义），`extra="forbid"`
- `XxxResponse` — `from_attributes=True`，含 id/created_at/updated_at

## 执行步骤

### 1. 分析字段

- 区分：标识字段 / 审计字段 / 业务字段 / 外键字段
- 检查 `app/core/constants.py` 是否有可复用的枚举
- 确认每个字段的 nullability 和默认值

### 2. 生成 Model

按约定生成 SQLAlchemy 模型，写入 `app/models/{snake_case}.py`：
- `__tablename__` = 蛇形复数
- 所有列显式声明 `nullable` 和 `default`
- 外键显式 `ondelete`
- `__table_args__` 中声明索引
- `TYPE_CHECKING` 中导入关联模型，避免循环引用
- relationship 用 `back_populates`，async 下关键关联加 `lazy="selectin"`

### 3. 生成 Schema

按四件套模式生成，写入 `app/schemas/{snake_case}.py`：
- Base 的每个 Field 必须带 `description`（用于 OpenAPI 文档）
- 字符串字段的 `max_length` 必须和 DB 列一致
- `field_validator` 用于枚举值校验、业务规则
- Response 加 `model_config = ConfigDict(from_attributes=True)`

### 4. 生成迁移脚本

用 `alembic revision --autogenerate` 生成后人工复核：
- `upgrade()` 建表、建索引、建外键
- `downgrade()` 反向操作
- UUID 默认值用 `sa.text("gen_random_uuid()")`
- 时间戳用 `server_default=sa.func.now()`

### 5. 更新 \_\_init\_\_.py

在 `app/models/__init__.py` 和 `app/schemas/__init__.py` 添加导入。

## 输出格式

生成文件后，给出简要汇总：

```
## 已生成

| 文件 | 内容 |
|------|------|
| app/models/{name}.py | 表 {table_name}，{n} 列，{m} 关联 |
| app/schemas/{name}.py | Create / Update / Response / ListResponse |
| migrations/versions/{id}.py | 迁移 {revision_id} |

## 一致性检查
- [ ] Model 列数 = Response 字段数（排除仅内部使用的字段）
- [ ] nullable 映射正确
- [ ] FK 字段命名：{entity}_id
- [ ] max_length 与 DB 列一致
- [ ] 审计字段在 Response 中
```

## 关键规则

- 优先读 `app/core/` 下的现有代码，复用而非重造
- 异步兼容，不用同步的 `default=datetime.utcnow`
- 主键永远是 UUIDv4，不用自增整数
- 显式优于隐式：ondelete / nullable / server_default 必须写清楚
- 迁移不可逆时标注 warning（如 DROP COLUMN）
- 所有 datetime 字段用 UTC
