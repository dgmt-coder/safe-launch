"""DeepSeekAnalyzer 单元测试."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.text_review.llm_judge import DeepSeekAnalyzer


def _build_mock_response(status_code: int, content: str) -> MagicMock:
    """构建 httpx Response 的 mock — json/raise_for_status 都是同步方法."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    resp.raise_for_status = MagicMock()  # 同步方法
    return resp


class TestDeepSeekAnalyzer:
    """LLM 判定器测试 — Mock HTTP 调用 + Mock 配置."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return DeepSeekAnalyzer()

    @pytest.fixture
    def mock_client(self):
        """Mock httpx AsyncClient — post 是异步的."""
        client = MagicMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_api_key(self):
        """Mock settings 中的 API Key."""
        with patch(
            "app.modules.text_review.llm_judge.settings.DEEPSEEK_API_KEY",
            "test-api-key",
        ):
            yield

    @pytest.mark.asyncio
    async def test_analyze_returns_structured_result(self, analyzer, mock_client, mock_api_key):
        """正常返回结构化 JSON 应正确解析."""
        mock_client.post.return_value = _build_mock_response(
            200,
            json.dumps({
                "is_violation": False,
                "violation_type": None,
                "confidence": 0.98,
                "reasoning": "内容合规",
            }),
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("正常游戏内容")

        assert result["is_violation"] is False
        assert result["confidence"] == 0.98

    @pytest.mark.asyncio
    async def test_analyze_detects_violation(self, analyzer, mock_client, mock_api_key):
        """检测到违规内容应返回违规结果."""
        mock_client.post.return_value = _build_mock_response(
            200,
            json.dumps({
                "is_violation": True,
                "violation_type": "political",
                "confidence": 0.95,
                "reasoning": "包含敏感政治表述",
            }),
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("敏感内容")

        assert result["is_violation"] is True
        assert result["violation_type"] == "political"

    @pytest.mark.asyncio
    async def test_analyze_malformed_json_returns_error(self, analyzer, mock_client, mock_api_key):
        """返回非法 JSON 应返回错误标记."""
        mock_client.post.return_value = _build_mock_response(200, "这不是JSON")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("测试")

        assert result.get("error") == "parse_error"

    @pytest.mark.asyncio
    async def test_analyze_empty_content_raises(self, analyzer, mock_api_key):
        """空内容应在调用 LLM 之前抛出异常."""
        with pytest.raises(ValueError):
            await analyzer.analyze("")

    @pytest.mark.asyncio
    async def test_analyze_timeout_returns_error(self, analyzer, mock_client, mock_api_key):
        """超时应返回错误标记."""
        import httpx
        mock_client.post.side_effect = httpx.TimeoutException("timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("测试")

        assert result.get("error") == "timeout"

    def test_analyzer_not_available_without_api_key(self):
        """无 API Key 时不可用."""
        analyzer = DeepSeekAnalyzer()
        assert not analyzer.is_available
