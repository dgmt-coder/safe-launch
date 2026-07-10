"""图片校验器 — 格式、尺寸、大小检查."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 支持的格式及魔术字节签名
ALLOWED_FORMATS = {"jpeg", "png", "webp", "gif"}
MAX_FILE_SIZE = 20 * 1024 * 1024

# 文件魔术字节 → 格式映射
_MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"RIFF": "webp",
    b"GIF8": "gif",
}


def _detect_format(data: bytes) -> str | None:
    """通过魔术字节检测图片格式."""
    for magic, fmt in _MAGIC_BYTES.items():
        if data[: len(magic)] == magic:
            return fmt
    return None


class ImageValidator:
    """图片格式与大小校验."""

    def validate(self, image_data: bytes, filename: str = "") -> dict:
        """校验图片.

        Args:
            image_data: 图片二进制数据.
            filename: 文件名（用于推断格式）.

        Returns:
            {valid: bool, format: str | None, size: int, errors: list[str]}
        """
        errors: list[str] = []
        size = len(image_data)

        # 1. 大小检查
        if size == 0:
            errors.append("图片数据为空")
        if size > MAX_FILE_SIZE:
            errors.append(f"图片过大: {size / 1024 / 1024:.1f}MB (上限 20MB)")

        # 2. 格式检查
        img_format = _detect_format(image_data)

        if img_format is None and filename:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext in ("jpg", "jpeg"):
                img_format = "jpeg"
            elif ext in ALLOWED_FORMATS:
                img_format = ext

        if img_format and img_format not in ALLOWED_FORMATS:
            errors.append(f"不支持的图片格式: {img_format}")
        elif img_format is None:
            errors.append("无法识别图片格式")

        return {
            "valid": len(errors) == 0,
            "format": img_format,
            "size": size,
            "errors": errors,
        }
