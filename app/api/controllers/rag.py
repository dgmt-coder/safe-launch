"""RAG 知识库 Controller."""

from __future__ import annotations

import uuid

from litestar import Controller, delete, post

from app.schemas.rag import (
    RagDocumentCreate,
    RagDocumentResponse,
    RagSearchRequest,
    RagSearchResponse,
)


class RagController(Controller):
    path = "/api/v1/rag"
    tags = ["RAG"]

    @post("/search")
    async def search(self, data: RagSearchRequest) -> RagSearchResponse:
        """RAG 法规检索.

        注意: 此端点需要 RagRetriever 依赖注入。
        当前为占位实现，完整功能见 RagRetriever 模块。
        """
        return RagSearchResponse(query=data.query)

    @post("/documents")
    async def add_document(self, data: RagDocumentCreate) -> RagDocumentResponse:
        """添加知识库文档.

        当前为占位实现。
        """
        doc_id = uuid.uuid4()
        return RagDocumentResponse(
            id=doc_id,
            title=data.title,
            source=data.source,
            created_at="",
        )

    @delete("/documents/{document_id:str}")
    async def delete_document(self, document_id: str) -> None:
        """删除知识库文档.

        当前为占位实现。
        """
        pass
