"""OpenAI Embedding — 文本向量化."""

from __future__ import annotations

import logging

import httpx

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIEmbedding:
    """OpenAI Embedding 服务封装 — 支持 text-embedding-3-small 等模型."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    @property
    def is_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def embed(self, text: str) -> list[float]:
        """对单条文本生成向量.

        Returns:
            向量列表 (1536 维).
        """
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """批量生成向量.

        Args:
            texts: 文本列表.
            batch_size: 每次请求的文本数.

        Returns:
            向量列表的列表.
        """
        if not self.is_available:
            raise RuntimeError("OpenAI API Key 未配置")

        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(30))

        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await client.post(
                    f"{settings.OPENAI_BASE_URL}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.OPENAI_EMBEDDING_MODEL,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                body = response.json()
                all_vectors.extend(
                    item["embedding"] for item in body["data"]
                )
            except Exception as e:
                logger.error(f"OpenAI Embedding 失败: {e}")
                raise

        return all_vectors
