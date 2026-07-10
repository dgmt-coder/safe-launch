"""审核记录 ORM 模型."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ReviewRecord(Base):
    """审核记录主表.

    存储每次审核的输入内容、各层检测结果、聚合结论.
    """

    __tablename__ = "review_records"

    # --- 主键 ---
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- 审核输入 ---
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="审核内容原文")
    content_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="内容类型: text / image"
    )
    review_dimension: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="审核维度"
    )

    # --- 审核状态 ---
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="审核状态"
    )
    risk_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="风险等级"
    )

    # --- 各层检测结果 (JSONB) ---
    l1_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="L1 关键词匹配结果"
    )
    l2_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="L2 RAG 法规检索结果"
    )
    l3_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="L3 LLM 判定结果"
    )

    # --- 聚合结果 ---
    review_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="最终审核结论"
    )

    # --- 降级信息 ---
    degraded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否降级运行"
    )
    skipped_layers: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="被跳过的检测层列表"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="降级/失败原因"
    )

    # --- 性能 ---
    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="处理耗时（毫秒）"
    )

    # --- 审计 ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --- 索引 ---
    __table_args__ = (
        Index("ix_review_records_status", "status"),
        Index("ix_review_records_risk_level", "risk_level"),
        Index("ix_review_records_dimension", "review_dimension"),
        Index("ix_review_records_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ReviewRecord(id={self.id}, status={self.status}, dim={self.review_dimension})>"
