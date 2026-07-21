"""RAG 检索器 — 编排 Embedding + Qdrant 判例检索."""

from __future__ import annotations

import structlog

from app.core.config.settings import settings
from app.modules.rag.embedding import EmbeddingService
from app.modules.rag.qdrant_client import QdrantManager
from app.schemas.rag import PrecedentHit

logger = structlog.get_logger(__name__)


class RagRetriever:
    """RAG 检索器 — 接收查询文本，返回相似判例供 LLM 做 few-shot 推理."""

    def __init__(
        self,
        embedding: EmbeddingService | None = None,
        qdrant: QdrantManager | None = None,
    ) -> None:
        self._embedding = embedding or EmbeddingService()
        self._qdrant = qdrant or QdrantManager()

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        review_dimension: str | None = None,
        min_similarity: float = 0.35,
    ) -> list[PrecedentHit]:
        """检索相似判例.

        Args:
            query: 查询文本.
            top_k: 返回数量.
            review_dimension: 可选，按审核维度过滤判例.
            min_similarity: 相似度阈值，低于此值不返回.

        Returns:
            PrecedentHit 列表，适合直接注入 LLM few-shot prompt.
        """
        if not self._embedding.is_available:
            logger.warning("Embedding 服务未配置，RAG 检索不可用")
            return []

        top_k = min(top_k, settings.L2_RAG_TOP_K)

        try:
            vector = await self._embedding.embed(query)
            raw_hits = await self._qdrant.search(
                vector,
                query=query,
                limit=top_k,
                review_dimension=review_dimension,
                min_similarity=min_similarity,
            )

            return [
                PrecedentHit(
                    content=h["content"],
                    is_violation=h["is_violation"],
                    violation_type=h.get("violation_type"),
                    severity=h.get("severity"),
                    reasoning=h.get("reasoning"),
                    review_dimension=h.get("review_dimension"),
                    tags=h.get("tags", []),
                    similarity=h["similarity"],
                    source=h.get("reviewer") or h.get("source"),
                )
                for h in raw_hits
            ]
        except Exception as e:
            logger.error(f"RAG 检索异常: {e}")
            raise
