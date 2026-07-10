"""RAG 知识库 Schema — 检索请求/响应、文档管理."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    """RAG 检索请求."""

    query: str = Field(..., min_length=1, max_length=2000, description="检索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回数量")


class RegulationHit(BaseModel):
    """单条法规命中结果."""

    content: str = Field(..., description="法规原文片段")
    source: str | None = Field(None, description="法规来源")
    similarity: float = Field(..., ge=0.0, le=1.0, description="相似度")
    metadata: dict = Field(default_factory=dict, description="附加信息")


class RagSearchResponse(BaseModel):
    """RAG 检索响应."""

    query: str
    hits: list[RegulationHit] = Field(default_factory=list)
    processing_time_ms: int = 0


class RagDocumentCreate(BaseModel):
    """添加知识库文档."""

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
