"""图片审核 Controller."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from litestar import Controller, post

from app.schemas.review import LayerResult, ReviewResponse
from app.modules.image_review.external_detector import ExternalDetector
from app.modules.image_review.validator import ImageValidator


class ImageReviewController(Controller):
    tags = ["Image Review"]

    @post("/api/v1/review/image")
    async def review_image(
        self,
        data: bytes,
        filename: str = "",
    ) -> ReviewResponse:
        """单张图片内容审核."""
        img_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # 1. 格式校验
        validator = ImageValidator()
        validation = validator.validate(data, filename)

        layers: list[LayerResult] = []
        if not validation["valid"]:
            layers.append(LayerResult(
                layer="validator",
                is_violation=True,
                details={"errors": validation["errors"]},
                processing_time_ms=0,
            ))

        # 2. 外部检测
        detector = ExternalDetector()
        try:
            detect_result = await detector.detect(data)
            layers.append(LayerResult(
                layer="external_detector",
                is_violation=detect_result.get("is_violation"),
                details=detect_result,
                processing_time_ms=0,
            ))
        except Exception as e:
            layers.append(LayerResult(
                layer="external_detector",
                is_violation=None,
                details={"error": str(e), "status": "manual_review"},
                processing_time_ms=0,
            ))

        is_violation = any(l.is_violation for l in layers if l.is_violation is not None)
        risk_level = "high" if is_violation else "low"

        return ReviewResponse(
            id=img_id,
            content=hashlib.sha256(data).hexdigest()[:32],
            content_type="image",
            review_dimension="art_assets",
            status="completed",
            risk_level=risk_level,
            is_violation=is_violation,
            layers=layers,
            processing_time_ms=0,
            created_at=now,
            updated_at=now,
        )
