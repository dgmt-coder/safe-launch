"""文字审核 Controller."""

from __future__ import annotations

from litestar import Controller, post
from litestar.di import Provide

from app.core.config.settings import settings
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services.review_service import ReviewService


class TextReviewController(Controller):
    tags = ["Text Review"]

    @post("/api/v1/review/text")
    async def review_text(
        self,
        data: ReviewCreate,
        review_service: ReviewService,
    ) -> ReviewResponse:
        """单条文字内容审核."""
        return await review_service.create_review(data)

    @post("/api/v1/review/text/batch")
    async def review_text_batch(
        self,
        data: list[ReviewCreate],
        review_service: ReviewService,
    ) -> list[ReviewResponse]:
        """批量文字内容审核."""
        if len(data) > settings.BATCH_MAX_SIZE:
            from litestar.exceptions import ValidationException
            raise ValidationException(
                f"批量数量超过上限: {len(data)} > {settings.BATCH_MAX_SIZE}"
            )
        return await review_service.create_review_batch(
            data, concurrency=settings.BATCH_CONCURRENCY
        )
