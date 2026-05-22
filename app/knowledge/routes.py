from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.agent.tools.document_parser import extract_text_from_bytes
from app.api.deps import get_current_user, verify_api_key
from app.core.config import get_settings
from app.auth.user_store import UserRecord
from app.knowledge.models import (
    IndexDocumentResponse,
    IndexFromAttachmentRequest,
    KnowledgeDocumentListResponse,
)
from app.knowledge.store import KnowledgeStore
from app.storage.attachments import AttachmentStore

_DOCUMENT_MIMES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
}


def _get_knowledge_store(request: Request) -> KnowledgeStore:
    store = getattr(request.app.state, "knowledge_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="知识库未初始化")
    if not store.enabled:
        raise HTTPException(status_code=503, detail="知识库功能已关闭")
    return store


def _get_attachment_store(request: Request) -> AttachmentStore:
    store = getattr(request.app.state, "attachment_store", None)
    if store is None:
        raise RuntimeError("Attachment store is not initialized")
    return store


def _is_document_upload(file: UploadFile) -> bool:
    mime = (file.content_type or "").split(";")[0].strip().lower()
    name = (file.filename or "").lower()
    if mime in _DOCUMENT_MIMES:
        return True
    return name.endswith((".pdf", ".txt", ".md"))


logger = logging.getLogger(__name__)


def build_knowledge_router() -> APIRouter:
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])

    @router.get("/documents", response_model=KnowledgeDocumentListResponse)
    async def list_documents(
        request: Request,
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> KnowledgeDocumentListResponse:
        store = _get_knowledge_store(request)
        docs = await store.list_documents(current_user.id)
        return KnowledgeDocumentListResponse(documents=docs)

    @router.post("/documents", response_model=list[IndexDocumentResponse])
    async def upload_documents(
        request: Request,
        files: list[UploadFile] = File(...),
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> list[IndexDocumentResponse]:
        if not files:
            raise HTTPException(status_code=400, detail="请至少上传一个文件")
        settings = get_settings()
        max_bytes = settings.attachment_max_bytes
        store = _get_knowledge_store(request)
        results: list[IndexDocumentResponse] = []
        for file in files:
            if not _is_document_upload(file):
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的文件类型：{file.filename}",
                )
            data = await file.read()
            if len(data) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大（{file.filename}），最大 {max_bytes} 字节",
                )
            mime = (file.content_type or "application/octet-stream").split(";")[0]
            filename = file.filename or "document.txt"
            try:
                extract_text_from_bytes(data, mime, filename)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            try:
                result = await store.index_bytes(
                    current_user.id,
                    filename,
                    data,
                    mime,
                    size_bytes=len(data),
                )
            except Exception as exc:
                logger.exception(
                    "knowledge_index_failed",
                    extra={"filename": filename, "user_id": current_user.id},
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"索引失败（{filename}），请稍后重试",
                ) from exc
            results.append(result)
        return results

    @router.delete("/documents/{doc_id}")
    async def delete_document(
        doc_id: str,
        request: Request,
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> dict[str, bool]:
        store = _get_knowledge_store(request)
        deleted = await store.delete_document(current_user.id, doc_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {"deleted": True}

    @router.post("/documents/from-attachment", response_model=IndexDocumentResponse)
    async def index_from_attachment(
        body: IndexFromAttachmentRequest,
        request: Request,
        current_user: UserRecord = Depends(get_current_user),
        _: None = Depends(verify_api_key),
    ) -> IndexDocumentResponse:
        store = _get_knowledge_store(request)
        attachment_store = _get_attachment_store(request)
        try:
            return await store.index_from_attachment(
                attachment_store,
                current_user.id,
                body.session_id,
                body.attachment_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="附件不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(
                "knowledge_index_from_attachment_failed",
                extra={"user_id": current_user.id, "attachment_id": body.attachment_id},
            )
            raise HTTPException(status_code=500, detail="索引失败，请稍后重试") from exc

    return router
