from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from pymongo.errors import PyMongoError

from src.api.v1.dependencies import get_document_service
from src.schemas.document_schema import (
    DocumentChunkData, DocumentListData, DocumentPageData, DocumentUploadData,
)
from src.schemas.response_schema import APIResponse
from src.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=APIResponse[DocumentUploadData], status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
) -> APIResponse[DocumentUploadData]:
    try:
        doc = await service.upload_document(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="Database operation failed.") from exc
    return APIResponse(
        message="Document uploaded and queued for background processing.",
        data=DocumentUploadData(
            id=doc["id"], filename=doc["filename"], content_type=doc["content_type"],
            size_bytes=doc["size_bytes"], status=doc["status"], created_at=doc["created_at"],
            page_count=doc.get("page_count"), chunk_count=doc.get("chunk_count"),
        ),
    )


@router.get("", response_model=APIResponse[DocumentListData])
async def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: DocumentService = Depends(get_document_service),
) -> APIResponse[DocumentListData]:
    items = await service.list_documents(skip, limit)
    return APIResponse(
        message="Documents retrieved.",
        data=DocumentListData(items=items, skip=skip, limit=limit),
    )


@router.get("/{document_id}", response_model=APIResponse[DocumentUploadData])
async def get_document(
    document_id: str, service: DocumentService = Depends(get_document_service),
) -> APIResponse[DocumentUploadData]:
    doc = await service.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return APIResponse(message="Document retrieved.", data=doc)


@router.get("/{document_id}/pages", response_model=APIResponse[list[DocumentPageData]])
async def get_document_pages(
    document_id: str, service: DocumentService = Depends(get_document_service),
) -> APIResponse[list[DocumentPageData]]:
    if await service.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return APIResponse(message="Document pages retrieved.", data=await service.get_pages(document_id))


@router.get("/{document_id}/chunks", response_model=APIResponse[list[DocumentChunkData]])
async def get_document_chunks(
    document_id: str, service: DocumentService = Depends(get_document_service),
) -> APIResponse[list[DocumentChunkData]]:
    if await service.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return APIResponse(message="Document chunks retrieved.", data=await service.get_chunks(document_id))


@router.delete("/{document_id}", response_model=APIResponse[dict])
async def delete_document(
    document_id: str, service: DocumentService = Depends(get_document_service),
) -> APIResponse[dict]:
    try:
        deleted = await service.delete_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not completely delete document.") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return APIResponse(message="Document and its indexed content deleted.", data={"id": document_id, "deleted": True})
