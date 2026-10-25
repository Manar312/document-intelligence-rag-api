from datetime import datetime, timezone
from typing import Any

from pymongo import UpdateOne
from pymongo.asynchronous.database import AsyncDatabase


class DocumentChunkRepository:
    """Persist and retrieve document chunks."""

    def __init__(self, database: AsyncDatabase) -> None:
        self.collection = database["document_chunks"]

    async def replace_chunks(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        operations = []
        chunk_indices = []

        for chunk in chunks:
            chunk_index = int(chunk["chunk_index"])
            chunk_indices.append(chunk_index)

            operations.append(
                UpdateOne(
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                    },
                    {
                        "$set": {
                            **chunk,
                            "updated_at": now,
                        },
                        "$setOnInsert": {
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )
            )

        # Write new chunks before removing obsolete ones.
        if operations:
            await self.collection.bulk_write(
                operations,
                ordered=True,
            )
            await self.collection.delete_many(
                {
                    "document_id": document_id,
                    "chunk_index": {"$nin": chunk_indices},
                }
            )
        else:
            await self.collection.delete_many(
                {"document_id": document_id}
            )

        return await self.list_for_document(document_id)

    async def list_for_document(
        self,
        document_id: str,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find(
                {"document_id": document_id},
                {"_id": 0},
            )
            .sort("chunk_index", 1)
        )
        return await cursor.to_list(length=None)

    async def delete_for_document(
        self,
        document_id: str,
    ) -> None:
        await self.collection.delete_many(
            {"document_id": document_id}
        )
