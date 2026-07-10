"""全局测试 fixture."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient

from app.api.controllers.health import HealthController
from app.api.controllers.history import HistoryController
from app.api.controllers.rag import RagController
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Session 级事件循环."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_app() -> Litestar:
    """创建测试用 Litestar 应用 — 注册 Controller 但不依赖数据库."""
    return Litestar(
        route_handlers=[
            HealthController,
            HistoryController,
            RagController,
        ],
        debug=True,
    )


@pytest.fixture
async def test_client(test_app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """异步 HTTP 测试客户端."""
    async with AsyncTestClient(app=test_app) as client:
        yield client
