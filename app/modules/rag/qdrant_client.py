"""Qdrant 向量数据库客户端封装."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class QdrantManager:
    """Qdrant 管理 — 集合操作、向量搜索、点管理."""

    def __init__(self) -> None:
        self._client: QdrantClient | None = None
        self._collection_name = settings.QDRANT_COLLECTION_NAME

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if settings.QDRANT_API_KEY:
                self._client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                )
            else:
                self._client = QdrantClient(url=settings.QDRANT_URL)
        return self._client

    async def ensure_collection(self, vector_size: int = 1536) -> None:
        """确保集合存在，不存在则创建."""
        try:
            self.client.get_collection(self._collection_name)
            logger.info(f"Qdrant 集合已存在: {self._collection_name}")
        except Exception:
            self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info(f"Qdrant 集合已创建: {self._collection_name} (dim={vector_size})")

    async def search(
        self, vector: list[float], limit: int = 5
    ) -> list[dict]:
        """向量相似度搜索.

        Returns:
            [{id, content, source, similarity, metadata}]
        """
        results = self.client.search(
            collection_name=self._collection_name,
            query_vector=vector,
            limit=limit,
        )
        return [
            {
                "id": hit.id,
                "content": hit.payload.get("content", ""),
                "source": hit.payload.get("source", ""),
                "similarity": hit.score,
                "metadata": hit.payload.get("metadata", {}),
            }
            for hit in results
        ]

    async def upsert(
        self, points: list[dict], vector_generator
    ) -> None:
        """批量插入/更新点.

        Args:
            points: [{id, content, source, metadata}]
            vector_generator: 生成向量的可调用对象.
        """
        texts = [p["content"] for p in points]
        vectors = await vector_generator(texts)

        qdrant_points = [
            models.PointStruct(
                id=p["id"],
                vector=v,
                payload={
                    "content": p["content"],
                    "source": p.get("source", ""),
                    "metadata": p.get("metadata", {}),
                },
            )
            for p, v in zip(points, vectors)
        ]

        self.client.upsert(
            collection_name=self._collection_name,
            points=qdrant_points,
        )
        logger.info(f"Qdrant 写入 {len(points)} 条")

    async def delete(self, point_ids: list[str]) -> None:
        """删除指定点."""
        self.client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
