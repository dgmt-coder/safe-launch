"""L2: RAG 法规检索桥接 — 将检索结果格式化为审核可用的结构化证据."""

from __future__ import annotations

import logging

from app.modules.rag.retriever import RagRetriever
from app.schemas.rag import RegulationHit

logger = logging.getLogger(__name__)


class RagBridge:
    """RAG 桥接层 — 封装 RagRetriever，为审核流水线提供 L2 检测结果."""

    def __init__(self, retriever: RagRetriever | None = None) -> None:
        self._retriever = retriever

    async def search(self, text: str, top_k: int = 5) -> list[RegulationHit]:
        """检索相关法规.

        Args:
            text: 待审核文本作为检索查询.
            top_k: 返回数量.

        Returns:
            相关法规命中列表.
        """
        if self._retriever is None:
            logger.warning("RagRetriever 未初始化，L2 跳过")
            return []

        try:
            return await self._retriever.search(text, top_k=top_k)
        except Exception as e:
            logger.error(f"RAG 检索异常: {e}")
            return []
