# Litestar 代码生成器

生成 Litestar 2.8+ Controller、Route、Guard、Middleware、DTO，遵循项目异步模式和分层架构。

## 职责

根据 API 需求，生成符合项目规范的 Litestar 代码：
- **Controller** — 路由分组、路径装饰器、依赖注入
- **Guard** — 鉴权守卫
- **Middleware** — 请求/响应拦截
- **DTO** — 请求体/响应体类型绑定

## 项目架构约定

```
Controller (参数校验 + 路由)
    ↓ 调用
Service (业务逻辑编排)
    ↓ 调用
Repository (数据访问, 基于 SQLAlchemy AsyncSession)
```

- Controller 只做参数校验和路由，不写业务逻辑
- 异步 Handler：`async def handler(...) -> ResponseSchema:`
- 依赖注入用 `Provide`，不用全局变量
- 错误统一用 Litestar HTTPException

## 输入

- **resource_name**: 资源名（snake_case 复数，如 `review_records`）
- **endpoints**: 端点列表 `[{method, path, description, request_schema, response_schema, guards}]`
- **base_path**: 路由前缀，如 `/api/v1`
- **output_path**: Controller 文件路径
- **dependencies**:（可选）注入的 Service/Repository
- **generate_tests**: 是否同时生成测试骨架，默认 false

## 执行步骤

### 1. 分析端点需求

- 确认每个端点的 HTTP 方法、路径、参数
- 确认鉴权要求（哪些端点需要 Guard）
- 确认分页/过滤/排序参数

### 2. 生成 Controller

按模板生成，写入 `app/api/controllers/{resource_name}.py`：

```python
from __future__ import annotations

from typing import Any
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Parameter

from app.schemas.{resource_singular} import (
    {Resource}Create,
    {Resource}ListResponse,
    {Resource}Response,
    {Resource}Update,
)
from app.services.{resource_singular} import {Resource}Service


class {Resource}Controller(Controller):
    path = "/{resource_name}"
    tags = ["{Resource}"]
    dependencies = {{"{resource_singular}_service": Provide({Resource}Service)}}

    @post()
    async def create(
        self,
        data: {Resource}Create,
        {resource_singular}_service: {Resource}Service,
    ) -> {Resource}Response:
        """创建{中文名}"""
        return await {resource_singular}_service.create(data)

    @get()
    async def list(
        self,
        {resource_singular}_service: {Resource}Service,
        page: int = Parameter(default=1, ge=1),
        page_size: int = Parameter(default=20, ge=1, le=100),
    ) -> {Resource}ListResponse:
        """分页查询{中文名}列表"""
        return await {resource_singular}_service.list(page=page, page_size=page_size)

    @get("/{{record_id:uuid}}")
    async def get(
        self,
        record_id: UUID,
        {resource_singular}_service: {Resource}Service,
    ) -> {Resource}Response:
        """查询单条{中文名}"""
        return await {resource_singular}_service.get(record_id)

    @patch("/{{record_id:uuid}}")
    async def update(
        self,
        record_id: UUID,
        data: {Resource}Update,
        {resource_singular}_service: {Resource}Service,
    ) -> {Resource}Response:
        """更新{中文名}"""
        return await {resource_singular}_service.update(record_id, data)

    @delete("/{{record_id:uuid}}")
    async def delete(
        self,
        record_id: UUID,
        {resource_singular}_service: {Resource}Service,
    ) -> None:
        """删除{中文名}"""
        await {resource_singular}_service.delete(record_id)
```

### 3. 生成 Guard（按需）

```python
# app/api/guards/{name}.py
from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler
from litestar.exceptions import NotAuthorizedException


class {Name}Guard:
    async def before_request(self, connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not connection.headers.get("X-API-Key"):
            raise NotAuthorizedException("缺少 API Key")
```

### 4. 生成 DTO（按需）

当请求/响应需要与 Schema 不同的形状时，生成 DTO。用 `msgspec` 或 Pydantic 均可。

### 5. 注册路由（提示）

提醒用户将 Controller 注册到 `app/main.py`：

```python
from app.api.controllers.{resource_name} import {Resource}Controller

app = Litestar(
    route_handlers=[..., {Resource}Controller],
    ...
)
```

## 输出格式

```
## 已生成

| 文件 | 内容 |
|------|------|
| app/api/controllers/{name}.py | {n} 个端点 |
| app/api/guards/{name}.py | (如有) |

## 端点清单

| 方法 | 路径 | Handler | 鉴权 |
|------|------|---------|------|
| POST | /api/v1/{name} | create | - |
| GET | /api/v1/{name} | list | - |
| GET | /api/v1/{name}/{id} | get | - |
| PATCH | /api/v1/{name}/{id} | update | - |
| DELETE | /api/v1/{name}/{id} | delete | - |

## 待办
- [ ] 在 app/main.py 注册 Controller
- [ ] 实现对应的 Service 和 Repository
```

## 关键规则

- Controller 不写业务逻辑，全部委托给 Service
- 所有 handler 必须是 `async def`
- 路径参数用 `{name:uuid}` 类型约束，Litestar 自动转换
- 分页参数用 `Parameter(ge=1)` 做校验
- 依赖注入用 `dependencies` 字典 + `Provide`
- tags 用于 OpenAPI 分组，必须设置
- 每个端点写中文 docstring，会自动出现在 OpenAPI description
- 错误码统一：404 → `NotFoundException`，422 → 由 Pydantic 自动处理
- 批量端点（batch）接受 `list[CreateSchema]`，返回 `list[ResponseSchema]`
