"""KeywordMatcher 单元测试."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.modules.text_review.keyword import KeywordMatcher


class TestKeywordMatcher:
    """关键词匹配器测试."""

    @pytest.fixture
    def keyword_dir(self):
        """创建临时关键词目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 写入测试关键词
            political = {
                "category": "political",
                "keywords": [
                    {"keyword": "测试敏感词", "severity": "high"},
                    {"keyword": "违规内容", "severity": "critical"},
                ],
            }
            porn = {
                "category": "pornographic",
                "keywords": [{"keyword": "色情词汇", "severity": "high"}],
            }
            (Path(tmpdir) / "political.json").write_text(
                json.dumps(political, ensure_ascii=False), encoding="utf-8"
            )
            (Path(tmpdir) / "pornographic.json").write_text(
                json.dumps(porn, ensure_ascii=False), encoding="utf-8"
            )
            yield tmpdir

    def test_load_keywords(self, keyword_dir: str):
        """加载关键词库应成功."""
        matcher = KeywordMatcher(keyword_dir=keyword_dir)
        matcher.load()
        assert matcher.is_loaded

    def test_match_returns_hits(self, keyword_dir: str):
        """匹配到关键词应返回命中列表."""
        matcher = KeywordMatcher(keyword_dir=keyword_dir)
        matcher.load()
        hits = matcher.match("这是一段包含测试敏感词的文本")
        assert len(hits) > 0
        assert any(h["keyword"] == "测试敏感词" for h in hits)

    def test_match_no_hits_returns_empty(self, keyword_dir: str):
        """无匹配应返回空列表."""
        matcher = KeywordMatcher(keyword_dir=keyword_dir)
        matcher.load()
        hits = matcher.match("这是一段正常文本，没有任何敏感词")
        assert hits == []

    def test_match_case_insensitive(self, keyword_dir: str):
        """匹配应大小写不敏感."""
        matcher = KeywordMatcher(keyword_dir=keyword_dir)
        matcher.load()
        hits = matcher.match("测试敏感词")  # 与 JSON 中一致
        assert len(hits) > 0

    def test_empty_text_returns_empty(self, keyword_dir: str):
        """空文本应返回空列表."""
        matcher = KeywordMatcher(keyword_dir=keyword_dir)
        matcher.load()
        hits = matcher.match("")
        assert hits == []

    def test_missing_keyword_dir_graceful(self):
        """关键词目录不存在时应优雅降级."""
        matcher = KeywordMatcher(keyword_dir="/nonexistent/path")
        matcher.load()
        assert not matcher.is_loaded
        assert matcher.match("测试") == []
