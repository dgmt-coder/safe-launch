"""ReviewService 单元测试."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import DegradedException
from app.schemas.review import ReviewCreate
from app.services.review_service import ReviewService
from tests.factories.review_factory import build_review_create, build_review_record


class TestReviewService:
    """审核编排服务测试."""

    @pytest.fixture
    def service(self, mock_review_repo, mock_keyword_matcher, mock_rag_retriever, mock_llm_judge):
        """创建 ReviewService 实例（Mock 所有注入依赖）."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        svc = ReviewService(
            mock_session,
            keyword_matcher=mock_keyword_matcher,
            rag_retriever=mock_rag_retriever,
            llm_judge=mock_llm_judge,
        )
        svc._repo = mock_review_repo
        return svc

    @pytest.mark.asyncio
    async def test_create_review_passes_content(self, service, mock_review_repo, mock_llm_judge):
        """合规内容审核 — 应返回通过."""
        # Arrange
        record = build_review_record()
        mock_review_repo.create.return_value = record
        mock_llm_judge.analyze.return_value = {
            "is_violation": False,
            "violation_type": None,
            "confidence": 0.98,
            "reasoning": "合规",
        }

        # Act
        data = build_review_create()
        result = await service.create_review(data)

        # Assert
        assert result.is_violation is False
        assert result.status == "completed"
        assert not result.degraded

    @pytest.mark.asyncio
    async def test_create_review_detects_violation(self, service, mock_review_repo, mock_llm_judge):
        """违规内容审核 — 应返回违规."""
        record = build_review_record()
        mock_review_repo.create.return_value = record
        mock_llm_judge.analyze.return_value = {
            "is_violation": True,
            "violation_type": "political",
            "confidence": 0.95,
            "reasoning": "包含敏感内容",
        }

        data = build_review_create(content="敏感内容")
        result = await service.create_review(data)

        assert result.is_violation is True
        assert result.violation_type == "political"

    @pytest.mark.asyncio
    async def test_all_layers_fail_raises_degraded_exception(
        self, service, mock_review_repo, mock_keyword_matcher, mock_rag_retriever, mock_llm_judge
    ):
        """所有层均异常应抛出 DegradedException."""
        record = build_review_record()
        mock_review_repo.create.return_value = record
        mock_keyword_matcher.match.side_effect = RuntimeError("关键词库损坏")
        mock_rag_retriever.search.side_effect = RuntimeError("Qdrant 不可用")
        mock_llm_judge.analyze.side_effect = RuntimeError("LLM 超时")

        data = build_review_create()

        with pytest.raises(DegradedException, match="所有审核层均不可用"):
            await service.create_review(data)

    @pytest.mark.asyncio
    async def test_partial_degraded_sets_degraded_flag(
        self, service, mock_review_repo, mock_keyword_matcher, mock_llm_judge
    ):
        """部分降级应设置 degraded=True."""
        record = build_review_record()
        mock_review_repo.create.return_value = record
        mock_keyword_matcher.match.side_effect = RuntimeError("关键词库损坏")
        mock_llm_judge.analyze.return_value = {
            "is_violation": False, "violation_type": None,
            "confidence": 0.8, "reasoning": "合规",
        }

        data = build_review_create()
        result = await service.create_review(data)

        assert result.degraded is True
        assert "keyword" in result.skipped_layers
