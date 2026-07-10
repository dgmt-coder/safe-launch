"""审核记录 Schema — Create / Update / Response / ListResponse."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ContentType, ReviewDimension


class ReviewBase(BaseModel):
    """审核请求共享字段."""

    content: str = Field(..., min_length=1, max_length=10000, description="待审核内容")
    content_type: str = Field(default="text", description="内容类型: text / image")
    review_dimension: str = Field(default="legal", description="审核维度")

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in ContentType:
            raise ValueError(f"不支持的内容类型: {v}，合法值: {[e.value for e in ContentType]}")
        return v

    @field_validator("review_dimension")
    @classmethod
    def validate_review_dimension(cls, v: str) -> str:
        if v not in ReviewDimension:
            raise ValueError(
                f"不支持的审核维度: {v}，合法值: {[e.value for e in ReviewDimension]}"
            )
        return v


class ReviewCreate(ReviewBase):
    """创建审核请求."""
    pass


class ReviewUpdate(BaseModel):
    """更新审核记录 — 所有字段可选 (PATCH 语义)."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    risk_level: Optional[str] = None
    review_result: Optional[dict[str, Any]] = None


class LayerResult(BaseModel):
    """单层检测结果."""

    layer: str = Field(..., description="层标识: keyword / rag / llm")
    is_violation: bool | None = Field(None, description="是否违规，None 表示该层未生效")
    details: dict[str, Any] = Field(default_factory=dict, description="该层详细结果")
    processing_time_ms: int = Field(0, ge=0, description="该层处理耗时")


class ReviewResponse(BaseModel):
    """审核响应 — 包含完整检测结果."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    content_type: str
    review_dimension: str
    status: str
    risk_level: str | None = None

    # 审核结论
    is_violation: bool | None = Field(None, description="是否违规")
    violation_type: str | None = Field(None, description="违规类型")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="置信度")
    reasoning: str | None = Field(None, description="判定理由")

    # 各层详情
    layers: list[LayerResult] = Field(default_factory=list, description="各层检测结果")

    # 降级
    degraded: bool = False
    skipped_layers: list[str] = Field(default_factory=list)
    error_message: str | None = None

    # 性能
    processing_time_ms: int | None = None

    # 审计
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    """审核记录分页响应."""

    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int


class ReviewStats(BaseModel):
    """审核统计数据."""

    total_records: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    violation_rate: float = 0.0
    degraded_rate: float = 0.0
    avg_processing_time_ms: float = 0.0
