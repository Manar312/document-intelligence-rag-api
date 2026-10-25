
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from src.models.document_model import DocumentModel


class DocumentRepository:
    def __init__(self, database: AsyncDatabase) -> None:
        self.collection = database["documents"]

    async def create(self, document: DocumentModel) -> dict[str, Any]:
        data = document.model_dump(mode="json")
        await self.collection.insert_one(data)
        return data

    async def get_by_id(self, document_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"id": document_id},
            {"_id": 0},
        )

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({}, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def update_status(
        self,
        document_id: str,
        status: str,
        error_message: str | None = None,
        *,
        page_count: int | None = None,
        chunk_count: int | None = None,
    ) -> dict[str, Any] | None:
        update_fields: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
            "error_message": error_message,
        }

        if page_count is not None:
            update_fields["page_count"] = page_count

        if chunk_count is not None:
            update_fields["chunk_count"] = chunk_count

        return await self.collection.find_one_and_update(
            {"id": document_id},
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def delete(self, document_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one_and_delete(
            {"id": document_id},
            projection={"_id": 0},
        )
