"""Qdrant 向量数据库客户端封装 — 判例存储与检索."""

from __future__ import annotations

import uuid

import structlog

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams

from app.core.config.settings import settings
from app.modules.rag.reranker import rerank

logger = structlog.get_logger(__name__)

# ── Payload 索引列表 ─────────────────────────────────────────────
_PAYLOAD_INDEXES: list[tuple[str, str]] = [
    ("is_violation", "bool"),
    ("violation_type", "keyword"),
    ("review_dimension", "keyword"),
    ("severity", "keyword"),
    ("is_active", "bool"),
]


class QdrantManager:
    """Qdrant 管理 — 判例存储、正反例平衡检索、点管理."""

    def __init__(self) -> None:
        self._client: QdrantClient | None = None
        self._collection_name = settings.QDRANT_COLLECTION_NAME
        self._collection_ensured: bool = False

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

    # ── 集合管理 ─────────────────────────────────────────────────

    async def ensure_collection(self, vector_size: int = 1024) -> None:
        """确保集合存在，不存在则创建并建 payload 索引.

        仅首次调用时检查/创建集合，后续调用直接返回（实例级缓存）.
        """
        if self._collection_ensured:
            return

        try:
            self.client.get_collection(self._collection_name)
            logger.info(f"Qdrant 集合已存在: {self._collection_name}")
        except Exception:
            self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            )
            logger.info(
                f"Qdrant 集合已创建: {self._collection_name} (dim={vector_size})"
            )
            # 建 payload 索引
            for field_name, field_type in _PAYLOAD_INDEXES:
                self.client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field_name,
                    field_schema=(
                        models.PayloadSchemaType.BOOL
                        if field_type == "bool"
                        else models.PayloadSchemaType.KEYWORD
                    ),
                    wait=True,
                )
            logger.info(f"Qdrant payload 索引已创建: {len(_PAYLOAD_INDEXES)} 个")

        self._collection_ensured = True

    # ── 判例检索 ─────────────────────────────────────────────────

    async def search(
        self,
        vector: list[float],
        query: str = "",
        *,
        limit: int = 5,
        candidate_multiplier: int = 6,
        review_dimension: str | None = None,
        min_similarity: float = 0.2,
        rerank_alpha: float = 0.5,
    ) -> list[dict]:
        """两阶段检索 — 粗筛大量候选 + keyword/向量混合精排.

        Args:
            vector: 查询向量.
            query: 原始查询文本，用于 rerank 阶段关键词匹配.
            limit: 最终返回数量.
            candidate_multiplier: 粗筛阶段取 limit * candidate_multiplier 个候选.
            review_dimension: 可选，按审核维度过滤.
            min_similarity: 粗筛相似度阈值（较低，保证召回).
            rerank_alpha: 混合得分中向量权重 (0~1).

        Returns:
            按 hybrid_score 降序的 top-limit 条.
        """
        await self.ensure_collection()

        candidate_limit = limit * candidate_multiplier

        base_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="is_active", match=models.MatchValue(value=True)
                ),
            ]
        )
        if review_dimension:
            base_filter.must.append(
                models.FieldCondition(
                    key="review_dimension",
                    match=models.MatchValue(value=review_dimension),
                )
            )

        # 粗筛 — 违规与合规各取一半候选
        violation_half = candidate_limit // 2 + (candidate_limit % 2)
        compliant_half = candidate_limit // 2

        violation_results = self._query_precedents(
            vector=vector, limit=violation_half,
            base_filter=base_filter, is_violation=True,
            score_threshold=min_similarity,
        )
        compliant_results = self._query_precedents(
            vector=vector, limit=compliant_half,
            base_filter=base_filter, is_violation=False,
            score_threshold=min_similarity,
        )

        # 合并去重
        seen: set[str] = set()
        candidates: list[dict] = []
        for hit in sorted(
            list(violation_results.points) + list(compliant_results.points),
            key=lambda h: h.score, reverse=True,
        ):
            if hit.id in seen:
                continue
            seen.add(hit.id)
            candidates.append(self._hit_to_dict(hit))

        # 精排 — 混合向量 + 关键词重叠
        ranked = rerank(query, candidates, alpha=rerank_alpha)

        return ranked[:limit]

    def _query_precedents(
        self,
        *,
        vector: list[float],
        limit: int,
        base_filter: models.Filter,
        is_violation: bool,
        score_threshold: float,
    ):
        """执行单次带过滤的向量检索."""
        query_filter = models.Filter(
            must=base_filter.must
            + [
                models.FieldCondition(
                    key="is_violation",
                    match=models.MatchValue(value=is_violation),
                ),
            ]
        )
        return self.client.query_points(
            collection_name=self._collection_name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
        )

    @staticmethod
    def _hit_to_dict(hit) -> dict:
        """将 Qdrant ScoredPoint 转为业务 dict."""
        payload = hit.payload or {}
        # 兼容旧 payload 中 verdict 嵌套对象 与 扁平字段两种格式
        _get = payload.get
        return {
            "id": hit.id,
            "content": _get("content", ""),
            "is_violation": _get("is_violation"),
            "violation_type": _get("violation_type"),
            "severity": _get("severity"),
            "reasoning": _get("reasoning", ""),
            "review_dimension": _get("review_dimension"),
            "tags": _get("tags", []),
            "reviewer": _get("reviewer"),
            "reviewed_at": _get("reviewed_at"),
            "similarity": hit.score,
            "source": _get("source", ""),
        }

    # ── 判例写入 ─────────────────────────────────────────────────

    async def upsert(
        self,
        precedents: list[dict],
        vector_generator,
    ) -> None:
        """批量写入判例.

        Args:
            precedents: [{content, content_type, is_violation, violation_type,
                          severity, reasoning, review_dimension, tags, reviewer, source}]
            vector_generator: 异步生成向量的可调用对象.
        """
        texts = [p["content"] for p in precedents]
        vectors = await vector_generator(texts)

        now = None  # 延迟导入避免循环引用
        qdrant_points = []
        for p, v in zip(precedents, vectors):
            point_id = p.get("id", uuid.uuid4().hex)
            qdrant_points.append(
                models.PointStruct(
                    id=point_id,
                    vector=v,
                    payload={
                        "content": p["content"],
                        "content_type": p.get("content_type", "text"),
                        "is_violation": p["is_violation"],
                        "violation_type": p.get("violation_type"),
                        "severity": p.get("severity"),
                        "reasoning": p.get("reasoning", ""),
                        "review_dimension": p.get("review_dimension"),
                        "tags": p.get("tags", []),
                        "reviewer": p.get("reviewer"),
                        "reviewed_at": p.get("reviewed_at", ""),
                        "source": p.get("source", ""),
                        "is_active": True,
                        "version": 1,
                        "created_at": p.get("created_at", ""),
                        "updated_at": p.get("updated_at", ""),
                    },
                )
            )

        self.client.upsert(
            collection_name=self._collection_name,
            points=qdrant_points,
        )
        logger.info(f"Qdrant 写入 {len(precedents)} 条判例")

    async def delete(self, point_ids: list[str]) -> None:
        """删除指定判例."""
        self.client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(points=point_ids),
        )
        logger.info(f"Qdrant 删除 {len(point_ids)} 条判例")

    async def deactivate(self, point_ids: list[str]) -> None:
        """停用判例（软删除 — 设为 is_active=False）."""
        self.client.set_payload(
            collection_name=self._collection_name,
            payload={"is_active": False},
            points=point_ids,
        )
        logger.info(f"Qdrant 停用 {len(point_ids)} 条判例")

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            self._collection_ensured = False
