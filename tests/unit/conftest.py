"""单元测试 Mock fixture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.rag import PrecedentHit


def _build_mock_precedent(**overrides) -> PrecedentHit:
    """构建 Mock 判例."""
    defaults = {
        "content": "测试判例内容",
        "is_violation": False,
        "violation_type": None,
        "severity": "low",
        "reasoning": "内容合规",
        "review_dimension": "legal",
        "tags": [],
        "similarity": 0.92,
        "source": "测试审查人",
    }
    defaults.update(overrides)
    return PrecedentHit(**defaults)


@pytest.fixture
def mock_review_repo():
    """Mock ReviewRepository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.create = AsyncMock()
    repo.list = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.count_by_dimension = AsyncMock()
    repo.count_by_status = AsyncMock()
    repo.count_by_risk_level = AsyncMock()
    repo.list_recent = AsyncMock()
    return repo


@pytest.fixture
def mock_keyword_matcher():
    """Mock KeywordMatcher."""
    matcher = MagicMock()
    matcher.match = MagicMock(return_value=[])
    matcher.is_loaded = True
    return matcher


@pytest.fixture
def mock_rag_retriever():
    """Mock RagRetriever — 默认返回一条合规判例."""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[_build_mock_precedent()])
    return retriever


@pytest.fixture
def mock_llm_judge():
    """Mock DeepSeekAnalyzer."""
    judge = AsyncMock()
    judge.analyze = AsyncMock(return_value={
        "is_violation": False,
        "violation_type": None,
        "confidence": 0.98,
        "reasoning": "内容合规",
    })
    judge.is_available = True
    return judge


@pytest.fixture
def mock_httpx(mocker):
    """Mock httpx.AsyncClient."""
    return mocker.patch("httpx.AsyncClient", autospec=True)
