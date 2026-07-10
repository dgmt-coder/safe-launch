"""单元测试 Mock fixture."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


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
    """Mock RagRetriever."""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[])
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
