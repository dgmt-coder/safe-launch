"""Web 页面 Controller — 返回 Jinja2 模板渲染的 HTML 页面."""

from __future__ import annotations

from litestar import Controller, get
from litestar.response import Template
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ReviewDimension, ReviewStatus
from app.services.repos.review_repo import ReviewRepository


class PagesController(Controller):
    path = "/"
    tags = ["Pages"]

    @get()
    async def dashboard(self, db_session: AsyncSession) -> Template:
        """审核仪表盘."""
        repo = ReviewRepository(db_session)
        status_counts = await repo.count_by_status()
        dim_counts = await repo.count_by_dimension()
        risk_counts = await repo.count_by_risk_level()
        recent, _ = await repo.list(page=1, page_size=10)

        total = sum(r["count"] for r in status_counts)
        completed = next((r["count"] for r in status_counts if r["status"] == "completed"), 0)
        degraded = next((r["count"] for r in status_counts if r["status"] == "degraded"), 0)

        return Template(
            template_name="dashboard.html",
            context={
                "total_records": total,
                "by_status": {r["status"]: r["count"] for r in status_counts},
                "by_dimension": {r["dimension"]: r["count"] for r in dim_counts},
                "by_risk_level": {r["risk_level"]: r["count"] for r in risk_counts},
                "degraded_rate": round(degraded / total * 100, 1) if total > 0 else 0.0,
                "recent_records": recent,
            },
        )

    @get("/review")
    async def review_page(self) -> Template:
        """文字审核页面."""
        return Template(
            template_name="review.html",
            context={
                "dimensions": [
                    {"value": d.value, "label": d.name}
                    for d in ReviewDimension
                ],
            },
        )

    @get("/history")
    async def history_page(self) -> Template:
        """审核历史页面."""
        return Template(
            template_name="history.html",
            context={
                "statuses": [s.value for s in ReviewStatus],
                "dimensions": [d.value for d in ReviewDimension],
            },
        )
