"""Embedding 服务 — 支持 OpenAI / Ollama 兼容端点."""

from __future__ import annotations

import structlog

import httpx

from app.core.config.settings import settings

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Embedding 服务封装 — 兼容 OpenAI 和 Ollama API.

    支持的后端:
        - Ollama 本地:  http://localhost:11434/v1
        - OpenAI 官方:  https://api.openai.com/v1
        - 其他兼容服务 (vLLM / TEI / Xinference 等)

    Ollama 注意:
        - /v1/embeddings 的 input 参数在部分版本只接受单条字符串，
          本实现自动拆分为逐条请求以保证兼容性。
        - qwen3-embedding:0.6b 输出 1024 维向量。
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client
        self._is_ollama = "11434" in settings.OPENAI_BASE_URL

    @property
    def is_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def embed(self, text: str) -> list[float]:
        """对单条文本生成向量."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """批量生成向量.

        Args:
            texts: 文本列表.
            batch_size: 每次请求的文本数（Ollama 下忽略，逐条请求).

        Returns:
            向量列表的列表.
        """
        if not self.is_available:
            raise RuntimeError("Embedding API Key 未配置")

        client = self._get_client()
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            if self._is_ollama:
                # Ollama /v1/embeddings 对数组 input 支持不稳定，逐条请求
                for text in batch:
                    vector = await self._request_embedding(client, text)
                    all_vectors.append(vector)
            else:
                # OpenAI 及其他兼容服务，支持数组 input
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
                    logger.error(f"Embedding 请求失败: {e}")
                    raise

        return all_vectors

    async def _request_embedding(
        self, client: httpx.AsyncClient, text: str
    ) -> list[float]:
        """发送单条 embedding 请求并解析响应."""
        try:
            response = await client.post(
                f"{settings.OPENAI_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OPENAI_EMBEDDING_MODEL,
                    "input": text,
                },
            )
            response.raise_for_status()
            body = response.json()

            # 兼容两种响应格式:
            #   OpenAI: {"data": [{"embedding": [...]}]}
            #   Ollama 原生: {"embedding": [...]}
            if "data" in body:
                return body["data"][0]["embedding"]
            return body["embedding"]

        except Exception as e:
            logger.error(f"Embedding 单条请求失败: {e}")
            raise

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端."""
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=httpx.Timeout(60))
