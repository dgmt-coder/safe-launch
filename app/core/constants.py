"""枚举与常量定义."""

from __future__ import annotations

from enum import StrEnum


class ReviewDimension(StrEnum):
    """审核维度."""

    LEGAL = "legal"                    # 法律法规红线
    GAME_PRINCIPLES = "game_principles"  # 游戏基本原则
    COMPLIANCE = "compliance"          # 游戏内合规要求
    ART_ASSETS = "art_assets"          # 美术资源内容审核


class ContentType(StrEnum):
    """内容类型."""

    TEXT = "text"
    IMAGE = "image"


class ReviewStatus(StrEnum):
    """审核状态."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"      # 部分降级完成


class RiskLevel(StrEnum):
    """风险等级."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(StrEnum):
    """违规类型."""

    POLITICAL = "political"        # 政治敏感
    PORNOGRAPHIC = "pornographic"  # 色情
    VIOLENCE = "violence"          # 暴力
    GAMBLING = "gambling"          # 赌博
    DRUGS = "drugs"                # 毒品
    FRAUD = "fraud"                # 诈骗
    OTHER = "other"                # 其他违规


# 审核维度权重（用于加权计算风险分数）
DIMENSION_WEIGHTS: dict[ReviewDimension, float] = {
    ReviewDimension.LEGAL: 1.0,
    ReviewDimension.GAME_PRINCIPLES: 0.9,
    ReviewDimension.COMPLIANCE: 0.8,
    ReviewDimension.ART_ASSETS: 0.7,
}

# 审核层标识
LAYER_KEYWORD = "keyword"
LAYER_RAG = "rag"
LAYER_LLM = "llm"
ALL_LAYERS = [LAYER_KEYWORD, LAYER_RAG, LAYER_LLM]
