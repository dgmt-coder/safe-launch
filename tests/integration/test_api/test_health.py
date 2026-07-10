"""GET /health 集成测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthAPI:
    """健康检查 API 测试."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, test_client: AsyncClient):
        """GET /health 应返回 200 + ok."""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_response_schema(self, test_client: AsyncClient):
        """响应应符合 HealthResponse schema."""
        response = await test_client.get("/health")
        data = response.json()
        assert "database" in data
        assert "redis" in data
