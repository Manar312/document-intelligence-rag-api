from datetime import datetime, timezone
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from src.core.config import get_settings
from src.providers.embedding_provider import EmbeddingProvider
from src.providers.qdrant_provider import QdrantProvider


class IndexingService:
    def __init__(self, database: AsyncDatabase) -> None:
        settings = get_settings()
        self.database = database
        self.embedding_provider = EmbeddingProvider(
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
        self.qdrant_provider = QdrantProvider(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            dimensions=settings.embedding_dimensions,
        )

    async def index_existing_chunks(self) -> dict[str, Any]:
        chunks = await self.database["document_chunks"].find(
            {},
            {"_id": 0},
        ).sort(
            [("document_id", 1), ("chunk_index", 1)]
        ).to_list(length=None)

        if not chunks:
            return {"chunks_indexed": 0, "documents_updated": 0}

        for chunk in chunks:
            if not chunk.get("text", "").strip():
                raise ValueError(
                    f"Empty chunk found: {chunk.get('document_id')} / "
                    f"{chunk.get('chunk_index')}"
                )

        self.qdrant_provider.ensure_collection()

        texts = [str(chunk["text"]) for chunk in chunks]
        vectors = self.embedding_provider.embed_texts(texts)

        self.qdrant_provider.upsert_chunks(chunks, vectors)

        # Verify all expected deterministic point IDs exist before status updates.
        from uuid import NAMESPACE_URL, uuid5

        point_ids = [
            str(uuid5(
                NAMESPACE_URL,
                f"02-rag:{chunk['document_id']}:{int(chunk['chunk_index'])}",
            ))
            for chunk in chunks
        ]
        retrieved = self.qdrant_provider.client.retrieve(
            collection_name=self.qdrant_provider.collection_name,
            ids=point_ids,
            with_payload=False,
            with_vectors=False,
        )

        if len(retrieved) != len(chunks):
            raise RuntimeError(
                f"Index verification failed: expected {len(chunks)} points, "
                f"found {len(retrieved)}."
            )

        document_ids = sorted({str(chunk["document_id"]) for chunk in chunks})
        now = datetime.now(timezone.utc)

        update_result = await self.database["documents"].update_many(
            {"id": {"$in": document_ids}},
            {
                "$set": {
                    "status": "indexed",
                    "updated_at": now,
                    "error_message": None,
                }
            },
        )

        return {
            "chunks_indexed": len(retrieved),
            "documents_found_in_chunks": len(document_ids),
            "document_records_updated": update_result.modified_count,
            "collection": self.qdrant_provider.collection_name,
            "vector_dimensions": self.embedding_provider.dimensions,
        }

    def close(self) -> None:
        self.qdrant_provider.close()
