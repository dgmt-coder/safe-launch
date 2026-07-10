"""ImageValidator 单元测试."""

from __future__ import annotations

import pytest

from app.modules.image_review.validator import ImageValidator


class TestImageValidator:
    """图片校验器测试."""

    @pytest.fixture
    def validator(self):
        return ImageValidator()

    def test_empty_data_invalid(self, validator):
        """空数据应无效."""
        result = validator.validate(b"")
        assert not result["valid"]
        assert "图片数据为空" in result["errors"]

    def test_oversized_data_invalid(self, validator):
        """超大文件应无效."""
        result = validator.validate(b"x" * (21 * 1024 * 1024))
        assert not result["valid"]
        assert any("过大" in e for e in result["errors"])

    def test_unknown_format_invalid(self, validator):
        """未知格式应无效."""
        result = validator.validate(b"\x00\x01\x02" * 10)
        assert not result["valid"]
        assert any("格式" in e for e in result["errors"])

    def test_jpeg_magic_bytes_valid(self, validator):
        """JPEG 魔术字节应有效."""
        # JPEG 文件头: FF D8 FF E0
        data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01" + b"\x00" * 100
        result = validator.validate(data)
        assert "format" in result
