"""RAG 判例检索 Schema — 检索请求/响应、判例管理."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    """RAG 检索请求."""

    query: str = Field(..., min_length=1, max_length=2000, description="检索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回数量")
    review_dimension: str | None = Field(
        None, max_length=50, description="审核维度过滤"
    )


class PrecedentHit(BaseModel):
    """单条判例命中结果 — 含策划已确认的判定结论."""

    content: str = Field(..., description="判例原文")
    is_violation: bool = Field(..., description="是否违规")
    violation_type: str | None = Field(None, description="违规类型")
    severity: str | None = Field(None, description="严重程度: high / medium / low")
    reasoning: str | None = Field(None, description="策划判定理由")
    review_dimension: str | None = Field(None, description="审核维度")
    tags: list[str] = Field(default_factory=list, description="标签")
    similarity: float = Field(..., ge=0.0, le=1.0, description="向量相似度")
    source: str | None = Field(None, description="判例来源 / 审查人")


class RagSearchResponse(BaseModel):
    """RAG 检索响应."""

    query: str
    hits: list[PrecedentHit] = Field(default_factory=list)
    processing_time_ms: int = 0


class PrecedentCreate(BaseModel):
    """添加判例."""

    content: str = Field(..., min_length=1, description="判例内容")
    content_type: str = Field(default="text", description="内容类型")
    is_violation: bool = Field(..., description="是否违规")
    violation_type: str | None = Field(None, description="违规类型")
    severity: str | None = Field(None, description="严重程度")
    reasoning: str | None = Field(None, description="判定理由")
    review_dimension: str = Field(..., max_length=50, description="审核维度")
    tags: list[str] = Field(default_factory=list, description="标签")
    reviewer: str | None = Field(None, max_length=100, description="审查人")
    source: str | None = Field(None, max_length=500, description="来源")


class PrecedentResponse(BaseModel):
    """判例响应."""

    id: str
    content: str
    is_violation: bool
    violation_type: str | None = None
    severity: str | None = None
    reasoning: str | None = None
    review_dimension: str
    tags: list[str] = []
    reviewer: str | None = None
    created_at: str


class RagDocumentCreate(BaseModel):
    """添加知识库文档（兼容旧接口）."""

    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    source: str | None = Field(None, max_length=500, description="来源")
    metadata: dict = Field(default_factory=dict, description="附加元数据")


class RagDocumentResponse(BaseModel):
    """知识库文档响应."""

    id: uuid.UUID
    title: str
    source: str | None = None
    created_at: str
