"""ReviewCreate Schema 单元测试."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewCreate, ReviewUpdate


class TestReviewCreate:
    """ReviewCreate 字段校验测试."""

    def test_valid_minimal_fields(self):
        """最小有效字段应通过校验."""
        data = ReviewCreate(content="测试", content_type="text", review_dimension="legal")
        assert data.content == "测试"

    def test_empty_content_raises_error(self):
        """空内容应抛出 ValidationError."""
        with pytest.raises(ValidationError):
            ReviewCreate(content="", content_type="text", review_dimension="legal")

    def test_content_exceeds_max_length_raises_error(self):
        """超长内容应抛出 ValidationError."""
        with pytest.raises(ValidationError):
            ReviewCreate(content="x" * 10001, content_type="text", review_dimension="legal")

    @pytest.mark.parametrize("dimension", ["legal", "game_principles", "compliance", "art_assets"])
    def test_all_valid_dimensions_pass(self, dimension: str):
        """所有合法 review_dimension 应通过校验."""
        data = ReviewCreate(content="测试", content_type="text", review_dimension=dimension)
        assert data.review_dimension == dimension

    def test_invalid_dimension_raises_error(self):
        """非法 review_dimension 应抛出 ValidationError."""
        with pytest.raises(ValidationError):
            ReviewCreate(content="测试", content_type="text", review_dimension="INVALID")

    @pytest.mark.parametrize("content_type", ["text", "image"])
    def test_valid_content_types_pass(self, content_type: str):
        """合法 content_type 应通过."""
        data = ReviewCreate(content="测试", content_type=content_type, review_dimension="legal")
        assert data.content_type == content_type

    def test_invalid_content_type_raises_error(self):
        """非法 content_type 应抛出 ValidationError."""
        with pytest.raises(ValidationError):
            ReviewCreate(content="测试", content_type="video", review_dimension="legal")


class TestReviewUpdate:
    """ReviewUpdate Schema 测试."""

    def test_empty_update_allowed(self):
        """空的 Update（所有字段为 None）应允许."""
        data = ReviewUpdate()
        assert data.status is None

    def test_partial_update(self):
        """部分字段更新应通过."""
        data = ReviewUpdate(status="completed")
        assert data.status == "completed"
        assert data.risk_level is None

    def test_extra_fields_forbidden(self):
        """额外字段应被禁止."""
        with pytest.raises(ValidationError):
            ReviewUpdate(status="completed", extra_field="value")  # type: ignore[call-arg]
