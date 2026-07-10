"""外部图片检测服务客户端 — 调用公司私有检测接口."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class ExternalDetector:
    """外部图片检测服务 — 通过 httpx 调用私有 API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    @property
    def is_available(self) -> bool:
        return bool(settings.IMAGE_REVIEW_API_URL)

    async def detect(self, image_data: bytes) -> dict[str, Any]:
        """调用外部服务检测图片.

        Args:
            image_data: 图片二进制数据.

        Returns:
            检测结果字典.
        """
        if not self.is_available:
            return {"status": "manual_review", "reason": "图片检测服务未配置"}

        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(settings.IMAGE_REVIEW_TIMEOUT))

        # 计算文件哈希
        file_hash = hashlib.sha256(image_data).hexdigest()

        try:
            response = await client.post(
                settings.IMAGE_REVIEW_API_URL,  # type: ignore[arg-type]
                headers={
                    "Authorization": f"Bearer {settings.IMAGE_REVIEW_API_KEY or ''}",
                    "Content-Type": "application/octet-stream",
                    "X-File-Hash": file_hash,
                },
                content=image_data,
            )
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            logger.warning("图片检测服务超时，转为人工审核")
            return {
                "status": "manual_review",
                "reason": "检测服务超时",
                "file_hash": file_hash,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"图片检测服务错误: {e.response.status_code}")
            return {
                "status": "manual_review",
                "reason": f"检测服务错误: {e.response.status_code}",
                "file_hash": file_hash,
            }

        except Exception as e:
            logger.error(f"图片检测调用异常: {e}")
            return {
                "status": "manual_review",
                "reason": f"检测服务不可用: {e}",
                "file_hash": file_hash,
            }
