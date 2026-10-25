from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.services.document_service import DocumentService


class DocumentUploadData(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime


class DocumentController:
    def __init__(self, service: DocumentService) -> None:
        self.service = service

    async def upload(self, upload_file: Any) -> dict[str, Any]:
        return await self.service.upload_document(upload_file)
