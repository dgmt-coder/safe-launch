"""健康检查 Schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应."""

    status: str = Field(default="ok", description="服务状态")
    version: str = Field(..., description="应用版本")
    database: str = Field(default="unknown", description="数据库状态")
    redis: str = Field(default="unknown", description="Redis 状态")
