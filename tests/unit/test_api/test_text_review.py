"""POST /api/v1/review/text API 单元测试 — 覆盖正常、违规、校验错误等场景."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar import Litestar
from litestar.di import Provide
from litestar.testing import AsyncTestClient

from app.api.controllers.text_review import TextReviewController
from app.core.exception_handlers import create_exception_handlers
from app.schemas.review import LayerResult, ReviewResponse
from app.services.review_service import ReviewService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_review_response(
    *,
    content: str = "测试内容",
    is_violation: bool = False,
    violation_type: str | None = None,
    confidence: float = 0.95,
    risk_level: str = "low",
    reasoning: str = "未检测到明显违规",
    layers: list[LayerResult] | None = None,
) -> ReviewResponse:
    """构建测试用 ReviewResponse."""
    if layers is None:
        layers = [
            LayerResult(
                layer="keyword",
                is_violation=False,
                details={"hits": [], "count": 0},
                processing_time_ms=5,
            ),
            LayerResult(
                layer="llm",
                is_violation=False,
                details={"confidence": 0.95, "reasoning": "合规"},
                processing_time_ms=200,
            ),
        ]
    now = _now()
    return ReviewResponse(
        id=uuid.uuid4(),
        content=content,
        content_type="text",
        review_dimension="legal",
        status="completed",
        risk_level=risk_level,
        is_violation=is_violation,
        violation_type=violation_type,
        confidence=confidence,
        reasoning=reasoning,
        layers=layers,
        degraded=False,
        skipped_layers=[],
        processing_time_ms=250,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_review_service():
    """创建 Mock ReviewService — 默认返回合规结果."""
    svc = MagicMock(spec=ReviewService)
    svc.create_review = AsyncMock(
        return_value=_make_review_response()
    )
    svc.create_review_batch = AsyncMock()
    return svc


@pytest.fixture
async def review_test_client(mock_review_service: MagicMock):
    """创建 TextReviewController 测试客户端，注入 mock ReviewService."""
    async def _get_mock() -> ReviewService:
        return mock_review_service

    app = Litestar(
        route_handlers=[TextReviewController],
        dependencies={"review_service": Provide(_get_mock)},
        exception_handlers=create_exception_handlers(),
        debug=True,
    )
    async with AsyncTestClient(app=app) as client:
        yield client


class TestTextReviewAPI:
    """POST /api/v1/review/text 测试."""

    # ------------------------------------------------------------------
    # 1. 正常内容 — 无违规
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_normal_content_returns_200(
        self, review_test_client: AsyncTestClient
    ):
        """提交正常内容应返回 200 + 审核通过."""
        response = await review_test_client.post(
            "/api/v1/review/text",
            json={
                "content": "今天天气真好，适合出去散步。晚上约了朋友一起吃火锅。",
                "content_type": "text",
                "review_dimension": "legal",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_violation"] is False
        assert data["risk_level"] == "low"
        assert data["status"] == "completed"

    # ------------------------------------------------------------------
    # 2. 触发单个关键词 — 政治类违规
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_single_keyword_violation(
        self, review_test_client: AsyncTestClient, mock_review_service: MagicMock
    ):
        """包含政治敏感词应返回违规结果."""
        mock_review_service.create_review = AsyncMock(
            return_value=_make_review_response(
                content="最近在网上看到一些关于台独的错误言论。",
                is_violation=True,
                violation_type="political",
                risk_level="high",
                confidence=0.9,
                reasoning="关键词命中: 台独",
                layers=[
                    LayerResult(
                        layer="keyword",
                        is_violation=True,
                        details={
                            "hits": [
                                {"keyword": "台独", "category": "political", "position": 12, "severity": "critical"}
                            ],
                            "count": 1,
                        },
                        processing_time_ms=3,
                    ),
                ],
            )
        )

        response = await review_test_client.post(
            "/api/v1/review/text",
            json={
                "content": "最近在网上看到一些关于台独的错误言论，我们应该警惕这些分裂势力的渗透。",
                "content_type": "text",
                "review_dimension": "legal",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_violation"] is True
        assert data["violation_type"] == "political"
        assert data["risk_level"] == "high"

    # ------------------------------------------------------------------
    # 3. 触发多个关键词 — 高危违规
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_multiple_keyword_violations(
        self, review_test_client: AsyncTestClient, mock_review_service: MagicMock
    ):
        """包含多个高危关键词应返回 critical 风险等级."""
        mock_review_service.create_review = AsyncMock(
            return_value=_make_review_response(
                content="台独分子散布港独言论，号召实施恐怖袭击。",
                is_violation=True,
                violation_type="political",
                risk_level="critical",
                confidence=0.95,
                reasoning="关键词命中: 台独, 港独, 恐怖袭击",
                layers=[
                    LayerResult(
                        layer="keyword",
                        is_violation=True,
                        details={
                            "hits": [
                                {"keyword": "台独", "category": "political", "position": 0, "severity": "critical"},
                                {"keyword": "港独", "category": "political", "position": 6, "severity": "critical"},
                                {"keyword": "恐怖袭击", "category": "violence", "position": 13, "severity": "critical"},
                            ],
                            "count": 3,
                        },
                        processing_time_ms=5,
                    ),
                ],
            )
        )

        response = await review_test_client.post(
            "/api/v1/review/text",
            json={
                "content": "台独分子散布港独言论，号召实施恐怖袭击和杀人行动，法轮功组织也在背后策动自杀式袭击。",
                "content_type": "text",
                "review_dimension": "legal",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_violation"] is True
        assert data["risk_level"] == "critical"
        assert data["layers"][0]["details"]["count"] == 3

    # ------------------------------------------------------------------
    # 4. 空 content — 触发 400 校验错误
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_empty_content_returns_400(
        self, review_test_client: AsyncTestClient, mock_review_service: MagicMock
    ):
        """空内容应返回 400 错误."""
        response = await review_test_client.post(
            "/api/v1/review/text",
            json={
                "content": "",
                "content_type": "text",
                "review_dimension": "legal",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "code" in data
        # ReviewService 不应被调用
        mock_review_service.create_review.assert_not_called()

    # ------------------------------------------------------------------
    # 5. 非法 review_dimension — 触发 400 校验错误
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_invalid_dimension_returns_400(
        self, review_test_client: AsyncTestClient, mock_review_service: MagicMock
    ):
        """非法审核维度应返回 400 错误."""
        response = await review_test_client.post(
            "/api/v1/review/text",
            json={
                "content": "测试内容",
                "content_type": "text",
                "review_dimension": "invalid",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "code" in data
        # ReviewService 不应被调用
        mock_review_service.create_review.assert_not_called()
