"""审核历史 Controller."""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.review import ReviewListResponse, ReviewResponse, ReviewStats
from app.services.repos.review_repo import ReviewRepository


class HistoryController(Controller):
    path = "/api/v1/history"
    tags = ["History"]

    @get("/records")
    async def list_records(
        self,
        db_session: AsyncSession,
        page: int = Parameter(default=1, ge=1),
        page_size: int = Parameter(default=20, ge=1, le=100),
        status: str | None = None,
        review_dimension: str | None = None,
    ) -> ReviewListResponse:
        """分页查询审核记录."""
        repo = ReviewRepository(db_session)
        records, total = await repo.list(
            page=page,
            page_size=page_size,
            status=status,
            review_dimension=review_dimension,
        )
        items = [
            ReviewResponse(
                id=r.id,
                content=r.content,
                content_type=r.content_type,
                review_dimension=r.review_dimension,
                status=r.status,
                risk_level=r.risk_level,
                degraded=r.degraded,
                skipped_layers=r.skipped_layers or [],
                processing_time_ms=r.processing_time_ms,
                error_message=r.error_message,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]
        return ReviewListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @get("/records/{record_id:uuid}")
    async def get_record(
        self,
        db_session: AsyncSession,
        record_id: UUID,
    ) -> ReviewResponse:
        """查询单条审核记录详情."""
        repo = ReviewRepository(db_session)
        try:
            r = await repo.get_by_id(record_id)
        except Exception:
            raise NotFoundException(f"审核记录不存在: {record_id}")
        return ReviewResponse(
            id=r.id,
            content=r.content,
            content_type=r.content_type,
            review_dimension=r.review_dimension,
            status=r.status,
            risk_level=r.risk_level,
            degraded=r.degraded,
            skipped_layers=r.skipped_layers or [],
            processing_time_ms=r.processing_time_ms,
            error_message=r.error_message,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    @get("/stats")
    async def get_stats(
        self,
        db_session: AsyncSession,
    ) -> ReviewStats:
        """获取审核统计数据."""
        repo = ReviewRepository(db_session)
        status_result = await repo.count_by_status()
        dim_result = await repo.count_by_dimension()
        risk_result = await repo.count_by_risk_level()

        total = sum(r["count"] for r in status_result)
        completed = next((r["count"] for r in status_result if r["status"] == "completed"), 0)
        degraded = next((r["count"] for r in status_result if r["status"] == "degraded"), 0)

        return ReviewStats(
            total_records=total,
            by_status={r["status"]: r["count"] for r in status_result},
            by_dimension={r["dimension"]: r["count"] for r in dim_result},
            by_risk_level={r["risk_level"]: r["count"] for r in risk_result},
            violation_rate=0.0,
            degraded_rate=degraded / total if total > 0 else 0.0,
            avg_processing_time_ms=0.0,
        )
