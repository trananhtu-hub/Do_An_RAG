from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import api_error, get_current_user
from app.core.auth import AuthUser
from app.models.document_schemas import DocumentListResponse, DocumentSummary
from app.services.documents import DocumentNotFound, DocumentService

router = APIRouter(tags=["documents"])


def get_document_service() -> DocumentService:
    return DocumentService()


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Danh sách tài liệu trong kho tri thức",
)
def list_documents(
    user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    rows = service.list_documents()
    return DocumentListResponse(
        items=[DocumentSummary(**row) for row in rows],
        total=len(rows),
    )


@router.get(
    "/documents/{document_id}/file",
    summary="Tải PDF gốc của tài liệu",
    response_class=FileResponse,
)
def document_file(
    document_id: str,
    user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    try:
        identifier = UUID(document_id)
    except ValueError:
        raise api_error(400, "invalid_document_id", "Mã tài liệu không hợp lệ.") from None
    try:
        path, title = service.resolve_file(identifier)
    except DocumentNotFound as exc:
        raise api_error(404, "document_not_found", str(exc)) from None
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{title}.pdf",
        content_disposition_type="inline",
    )
