"""L2: RAG 判例检索桥接 — 将检索结果格式化为 LLM few-shot 可用的结构化判例."""

from __future__ import annotations

import structlog

from app.modules.rag.retriever import RagRetriever
from app.schemas.rag import PrecedentHit

logger = structlog.get_logger(__name__)


class RagBridge:
    """RAG 桥接层 — 封装 RagRetriever，为审核流水线提供 L2 判例检索."""

    def __init__(self, retriever: RagRetriever | None = None) -> None:
        self._retriever = retriever

    async def search(
        self,
        text: str,
        *,
        top_k: int = 5,
        review_dimension: str | None = None,
    ) -> list[PrecedentHit]:
        """检索相似判例.

        Args:
            text: 待审核文本作为检索查询.
            top_k: 返回数量.
            review_dimension: 可选，按审核维度过滤.

        Returns:
            相关判例列表，供 LLM 做 few-shot 参考.
        """
        if self._retriever is None:
            logger.warning("RagRetriever 未初始化，L2 跳过")
            return []

        try:
            return await self._retriever.search(
                text, top_k=top_k, review_dimension=review_dimension
            )
        except Exception as e:
            logger.error(f"RAG 检索异常: {e}")
            return []
