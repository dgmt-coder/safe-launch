"""ReviewService — 审核业务编排：三线流水线 + 降级 + 批量并发."""

from __future__ import annotations

import asyncio
import structlog
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    LAYER_KEYWORD,
    LAYER_LLM,
    LAYER_RAG,
    ReviewStatus,
    RiskLevel,
)
from app.core.exceptions import DegradedException
from app.schemas.review import LayerResult, ReviewCreate, ReviewResponse, ReviewStats
from app.services.repos.review_repo import ReviewRepository

logger = structlog.get_logger(__name__)


class ReviewService:
    """审核服务 — 编排三层检测流水线."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        keyword_matcher=None,
        rag_retriever=None,
        llm_judge=None,
    ) -> None:
        self._session = session
        self._repo = ReviewRepository(session)
        self._keyword_matcher = keyword_matcher
        self._rag_retriever = rag_retriever
        self._llm_judge = llm_judge

    async def create_review(self, data: ReviewCreate) -> ReviewResponse:
        """执行单条审核 — L1/L2/L3 并发执行，聚合结果."""
        start_time = time.perf_counter()

        # 1. 创建记录 (status=processing)
        record = await self._repo.create(data)

        # 2. 并发执行三层检测
        l1_coro = self._run_keyword(data.content)
        l2_coro = self._run_rag(data.content)
        l3_coro = self._run_llm(data.content)

        l1_result, l2_result, l3_result = await asyncio.gather(
            l1_coro, l2_coro, l3_coro, return_exceptions=True
        )

        # 3. 聚合结果
        layers: list[LayerResult] = []
        skipped: list[str] = []
        l1_ok = not isinstance(l1_result, Exception)
        l2_ok = not isinstance(l2_result, Exception)
        l3_ok = not isinstance(l3_result, Exception)

        if l1_ok:
            layers.append(l1_result)  # type: ignore[arg-type]
        else:
            skipped.append(LAYER_KEYWORD)

        if l2_ok:
            layers.append(l2_result)  # type: ignore[arg-type]
        else:
            skipped.append(LAYER_RAG)

        if l3_ok:
            layers.append(l3_result)  # type: ignore[arg-type]
        else:
            skipped.append(LAYER_LLM)

        # 4. 判断最终结论
        is_violation, violation_type, confidence, risk_level, reasoning = self._aggregate(layers)

        # 5. 全部跳过则失败
        if not layers:
            error_msg = "所有审核层均不可用"
            await self._repo.update(record.id, {
                "status": ReviewStatus.FAILED,
                "error_message": error_msg,
                "degraded": True,
                "skipped_layers": skipped,
                "processing_time_ms": int((time.perf_counter() - start_time) * 1000),
            })
            raise DegradedException(error_msg)

        degraded = len(skipped) > 0
        status = ReviewStatus.DEGRADED if degraded else ReviewStatus.COMPLETED
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. 更新记录
        await self._repo.update(record.id, {
            "status": status,
            "risk_level": risk_level,
            "l1_result": l1_result.details if l1_ok else None,
            "l2_result": l2_result.details if l2_ok else None,
            "l3_result": l3_result.details if l3_ok else None,
            "review_result": {
                "is_violation": is_violation,
                "violation_type": violation_type,
                "confidence": confidence,
                "reasoning": reasoning,
            },
            "degraded": degraded,
            "skipped_layers": skipped or None,
            "processing_time_ms": processing_time_ms,
        })

        # 7. 构建响应
        return ReviewResponse(
            id=record.id,
            content=data.content,
            content_type=data.content_type,
            review_dimension=data.review_dimension,
            status=status,
            risk_level=risk_level,
            is_violation=is_violation,
            violation_type=violation_type,
            confidence=confidence,
            reasoning=reasoning,
            layers=layers,
            degraded=degraded,
            skipped_layers=skipped,
            processing_time_ms=processing_time_ms,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def create_review_batch(
        self, items: list[ReviewCreate], concurrency: int = 5
    ) -> list[ReviewResponse]:
        """批量审核 — 用 Semaphore 控制并发度."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _review_one(data: ReviewCreate) -> ReviewResponse:
            async with semaphore:
                try:
                    return await self.create_review(data)
                except DegradedException as e:
                    logger.warning(f"审核降级失败: {e}")
                    return ReviewResponse(
                        id=uuid.uuid4(),
                        content=data.content,
                        content_type=data.content_type,
                        review_dimension=data.review_dimension,
                        status=ReviewStatus.FAILED,
                        error_message=str(e),
                        degraded=True,
                        skipped_layers=["keyword", "rag", "llm"],
                        created_at=...,
                        updated_at=...,
                    )

        tasks = [_review_one(item) for item in items]
        return list(await asyncio.gather(*tasks))

    async def get_stats(self) -> ReviewStats:
        """获取审核统计数据."""
        total_result = await self._repo.count_by_status()
        dim_result = await self._repo.count_by_dimension()
        risk_result = await self._repo.count_by_risk_level()

        total = sum(r["count"] for r in total_result)
        by_status = {r["status"]: r["count"] for r in total_result}
        by_dimension = {r["dimension"]: r["count"] for r in dim_result}
        by_risk = {r["risk_level"]: r["count"] for r in risk_result}

        completed = by_status.get(ReviewStatus.COMPLETED, 0)
        degraded = by_status.get(ReviewStatus.DEGRADED, 0)
        violation_count = sum(
            r["count"] for r in risk_result
            if r["risk_level"] in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        )

        return ReviewStats(
            total_records=total,
            by_status=by_status,
            by_dimension=by_dimension,
            by_risk_level=by_risk,
            violation_rate=violation_count / completed if completed > 0 else 0.0,
            degraded_rate=degraded / total if total > 0 else 0.0,
            avg_processing_time_ms=0.0,
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    async def _run_keyword(self, content: str) -> LayerResult:
        """L1: 关键词匹配."""
        t0 = time.perf_counter()
        if self._keyword_matcher is None:
            raise RuntimeError("KeywordMatcher 未注入")
        hits = self._keyword_matcher.match(content)
        elapsed = int((time.perf_counter() - t0) * 1000)
        is_violation = len(hits) > 0
        return LayerResult(
            layer=LAYER_KEYWORD,
            is_violation=is_violation,
            details={"hits": hits, "count": len(hits)},
            processing_time_ms=elapsed,
        )

    async def _run_rag(self, content: str) -> LayerResult:
        """L2: RAG 法规检索."""
        t0 = time.perf_counter()
        if self._rag_retriever is None:
            raise RuntimeError("RagRetriever 未注入")
        hits = await self._rag_retriever.search(content)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return LayerResult(
            layer=LAYER_RAG,
            is_violation=None,  # RAG 仅提供证据，不做判定
            details={"regulations": [h.model_dump() for h in hits], "count": len(hits)},
            processing_time_ms=elapsed,
        )

    async def _run_llm(self, content: str) -> LayerResult:
        """L3: LLM 深度判定."""
        t0 = time.perf_counter()
        if self._llm_judge is None:
            raise RuntimeError("LLMJudge 未注入")
        result = await self._llm_judge.analyze(content)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return LayerResult(
            layer=LAYER_LLM,
            is_violation=result.get("is_violation"),
            details=result,
            processing_time_ms=elapsed,
        )

    @staticmethod
    def _aggregate(
        layers: list[LayerResult],
    ) -> tuple[bool | None, str | None, float | None, str | None, str | None]:
        """聚合各层结果为最终判定."""
        # L3 (LLM) 优先级最高
        llm_layer = next((l for l in layers if l.layer == LAYER_LLM), None)
        if llm_layer and llm_layer.is_violation is not None:
            risk_level = (
                RiskLevel.HIGH
                if llm_layer.details.get("confidence", 0) > 0.8
                and llm_layer.is_violation
                else RiskLevel.LOW
            )
            return (
                llm_layer.is_violation,
                llm_layer.details.get("violation_type"),
                llm_layer.details.get("confidence"),
                risk_level,
                llm_layer.details.get("reasoning", ""),
            )

        # 没有 LLM → 看 L1 关键词
        kw_layer = next((l for l in layers if l.layer == LAYER_KEYWORD), None)
        if kw_layer and kw_layer.is_violation:
            return (
                True,
                "other",
                0.9,
                RiskLevel.MEDIUM,
                f"关键词命中 {kw_layer.details.get('count', 0)} 条",
            )

        # 都没有明确判定 → 低风险
        return (
            False,
            None,
            0.5,
            RiskLevel.LOW,
            "未检测到明显违规",
        )
