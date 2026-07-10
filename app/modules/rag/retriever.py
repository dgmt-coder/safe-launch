"""RAG 检索器 — 编排 Embedding + Qdrant 检索."""

from __future__ import annotations

import logging

from app.core.config.settings import settings
from app.modules.rag.embedding import OpenAIEmbedding
from app.modules.rag.qdrant_client import QdrantManager
from app.schemas.rag import RegulationHit

logger = logging.getLogger(__name__)


class RagRetriever:
    """RAG 检索器 — 接收查询文本，返回相关法规."""

    def __init__(
        self,
        embedding: OpenAIEmbedding | None = None,
        qdrant: QdrantManager | None = None,
    ) -> None:
        self._embedding = embedding or OpenAIEmbedding()
        self._qdrant = qdrant or QdrantManager()

    async def search(self, query: str, top_k: int = 5) -> list[RegulationHit]:
        """检索相关法规.

        Args:
            query: 查询文本.
            top_k: 返回数量.

        Returns:
            相关法规命中的 RegulationHit 列表.
        """
        if not self._embedding.is_available:
            logger.warning("OpenAI Embedding 未配置，RAG 检索不可用")
            return []

        top_k = min(top_k, settings.L2_RAG_TOP_K)

        try:
            # 1. 查询向量化
            vector = await self._embedding.embed(query)

            # 2. Qdrant 相似度搜索
            raw_hits = await self._qdrant.search(vector, limit=top_k)

            # 3. 转换为 RegulationHit
            return [
                RegulationHit(
                    content=h["content"],
                    source=h.get("source"),
                    similarity=h["similarity"],
                    metadata=h.get("metadata", {}),
                )
                for h in raw_hits
            ]
        except Exception as e:
            logger.error(f"RAG 检索异常: {e}")
            raise
