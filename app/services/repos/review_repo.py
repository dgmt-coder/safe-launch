"""ReviewRepository — ReviewRecord 纯数据访问层."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ReviewStatus
from app.core.exceptions import NotFoundException
from app.models.review_record import ReviewRecord
from app.schemas.review import ReviewCreate


class ReviewRepository:
    """审核记录数据访问 — 纯 SQL 操作，不包含业务逻辑."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, record_id: uuid.UUID) -> ReviewRecord:
        """按 ID 查询，不存在抛 NotFoundException."""
        stmt = select(ReviewRecord).where(ReviewRecord.id == record_id)
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundException(f"审核记录不存在: {record_id}")
        return record

    async def find_by_id(self, record_id: uuid.UUID) -> ReviewRecord | None:
        """按 ID 查询，不存在返回 None."""
        stmt = select(ReviewRecord).where(ReviewRecord.id == record_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: ReviewCreate) -> ReviewRecord:
        """创建审核记录."""
        record = ReviewRecord(
            content=data.content,
            content_type=data.content_type,
            review_dimension=data.review_dimension,
            status=ReviewStatus.PROCESSING,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        status: str | None = None,
        content_type: str | None = None,
        review_dimension: str | None = None,
    ) -> tuple[list[ReviewRecord], int]:
        """分页查询审核记录."""
        stmt = select(ReviewRecord)

        if status:
            stmt = stmt.where(ReviewRecord.status == status)
        if content_type:
            stmt = stmt.where(ReviewRecord.content_type == content_type)
        if review_dimension:
            stmt = stmt.where(ReviewRecord.review_dimension == review_dimension)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # 分页
        stmt = stmt.order_by(ReviewRecord.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        records = list(result.scalars().all())

        return records, total

    async def update(self, record_id: uuid.UUID, updates: dict) -> ReviewRecord:
        """更新审核记录字段."""
        record = await self.get_by_id(record_id)
        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def delete(self, record_id: uuid.UUID) -> None:
        """删除审核记录."""
        record = await self.get_by_id(record_id)
        await self._session.delete(record)
        await self._session.flush()

    async def count_by_dimension(self) -> list[dict]:
        """按审核维度统计."""
        stmt = (
            select(ReviewRecord.review_dimension, func.count().label("cnt"))
            .group_by(ReviewRecord.review_dimension)
        )
        result = await self._session.execute(stmt)
        return [{"dimension": row[0], "count": row[1]} for row in result.all()]

    async def count_by_status(self) -> list[dict]:
        """按状态统计."""
        stmt = (
            select(ReviewRecord.status, func.count().label("cnt"))
            .group_by(ReviewRecord.status)
        )
        result = await self._session.execute(stmt)
        return [{"status": row[0], "count": row[1]} for row in result.all()]

    async def count_by_risk_level(self) -> list[dict]:
        """按风险等级统计（只统计已完成的记录）."""
        stmt = (
            select(ReviewRecord.risk_level, func.count().label("cnt"))
            .where(ReviewRecord.status == ReviewStatus.COMPLETED)
            .group_by(ReviewRecord.risk_level)
        )
        result = await self._session.execute(stmt)
        return [{"risk_level": row[0] or "unknown", "count": row[1]} for row in result.all()]

    async def list_recent(self, limit: int = 10) -> list[ReviewRecord]:
        """获取最近 N 条审核记录."""
        stmt = (
            select(ReviewRecord)
            .order_by(ReviewRecord.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
