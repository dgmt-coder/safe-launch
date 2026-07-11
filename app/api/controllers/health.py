"""健康检查 Controller."""

from __future__ import annotations

from litestar import Controller, get

from app.core.config.settings import settings
from app.schemas.health import HealthResponse


class HealthController(Controller):
    tags = ["Health"]
    include_in_schema = True

    @get("/health")
    async def check(self) -> HealthResponse:
        """服务健康检查."""
        return HealthResponse(
            status="ok",
            version=settings.APP_VERSION,
            database="unknown",
            redis="unknown",
        )
