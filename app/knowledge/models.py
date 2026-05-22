from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    doc_id: str
    filename: str
    size_bytes: int = 0
    chunk_count: int = 0
    created_at: str = ""


class KnowledgeCitation(BaseModel):
    index: int
    doc_id: str
    filename: str
    chunk_index: int
    excerpt: str
    score: float | None = None


class KnowledgeSearchResult(BaseModel):
    query: str
    citations: list[KnowledgeCitation] = Field(default_factory=list)
    summary: str = ""


class IndexDocumentResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int


class KnowledgeDocumentListResponse(BaseModel):
    documents: list[KnowledgeDocument] = Field(default_factory=list)


class IndexFromAttachmentRequest(BaseModel):
    session_id: str
    attachment_id: str
