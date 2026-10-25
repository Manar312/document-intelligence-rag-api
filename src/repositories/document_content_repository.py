from datetime import datetime, timezone
from typing import Any

from pymongo import UpdateOne
from pymongo.asynchronous.database import AsyncDatabase


class DocumentContentRepository:
    """Persist extracted page content for a document."""

    def __init__(self, database: AsyncDatabase) -> None:
        self.collection = database["document_contents"]

    async def save_pages(
        self,
        document_id: str,
        pages: list[dict[str, object]],
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        operations = []
        page_numbers = []

        for page in pages:
            page_number = int(page["page_number"])
            text = str(page.get("text", ""))

            page_numbers.append(page_number)
            operations.append(
                UpdateOne(
                    {
                        "document_id": document_id,
                        "page_number": page_number,
                    },
                    {
                        "$set": {
                            "text": text,
                            "character_count": len(text),
                            "extraction_method": page.get(
                                "extraction_method", "text"
                            ),
                            "updated_at": now,
                        },
                        "$setOnInsert": {
                            "document_id": document_id,
                            "page_number": page_number,
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )
            )

        # Write the new pages before removing obsolete pages.
        if operations:
            await self.collection.bulk_write(
                operations,
                ordered=True,
            )
            await self.collection.delete_many(
                {
                    "document_id": document_id,
                    "page_number": {"$nin": page_numbers},
                }
            )
        else:
            await self.collection.delete_many(
                {"document_id": document_id}
            )

        return await self.get_pages(document_id)

    async def get_pages(
        self,
        document_id: str,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find(
                {"document_id": document_id},
                {"_id": 0},
            )
            .sort("page_number", 1)
        )
        return await cursor.to_list(length=None)

    async def delete_for_document(
        self,
        document_id: str,
    ) -> None:
        await self.collection.delete_many(
            {"document_id": document_id}
        )
