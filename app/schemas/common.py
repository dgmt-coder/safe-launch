"""通用 Schema — 分页、错误响应等."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应."""

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(..., ge=0, description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")


class ErrorResponse(BaseModel):
    """通用错误响应."""

    detail: str = Field(..., description="错误描述")
    code: str | None = Field(None, description="错误码")
