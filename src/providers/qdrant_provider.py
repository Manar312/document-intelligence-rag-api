from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models


class QdrantProvider:
    """Manage document vectors in Qdrant."""

    def __init__(
        self,
        url: str,
        collection_name: str,
        dimensions: int,
    ) -> None:
        self.client = QdrantClient(url=url, timeout=30)
        self.collection_name = collection_name
        self.dimensions = dimensions

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            info = self.client.get_collection(self.collection_name)
            existing = info.config.params.vectors.size

            if existing != self.dimensions:
                raise ValueError(
                    f"Qdrant vector size is {existing}; "
                    f"expected {self.dimensions}."
                )
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimensions,
                distance=models.Distance.COSINE,
            ),
        )

    @staticmethod
    def point_id(document_id: str, chunk_index: int) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"02-rag:{document_id}:{chunk_index}",
            )
        )

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                "Each chunk must have exactly one embedding."
            )

        points = []
        for chunk, vector in zip(chunks, vectors):
            text = str(chunk["text"])
            payload = {
                "document_id": str(chunk["document_id"]),
                "chunk_index": int(chunk["chunk_index"]),
                "page_number": int(chunk["page_number"]),
                "text": text,
                "character_count": int(
                    chunk.get("character_count", len(text))
                ),
                "start_char": int(chunk.get("start_char", 0)),
                "end_char": int(chunk.get("end_char", 0)),
            }

            points.append(
                models.PointStruct(
                    id=self.point_id(
                        payload["document_id"],
                        payload["chunk_index"],
                    ),
                    vector=vector,
                    payload=payload,
                )
            )

        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

    def delete_stale_chunks(
        self,
        document_id: str,
        valid_chunk_indices: list[int],
    ) -> None:
        """Delete vectors for chunks no longer present in the document."""
        document_condition = models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=document_id),
        )

        if not valid_chunk_indices:
            self.delete_document(document_id)
            return

        stale_filter = models.Filter(
            must=[document_condition],
            must_not=[
                models.FieldCondition(
                    key="chunk_index",
                    match=models.MatchAny(any=valid_chunk_indices),
                )
            ],
        )

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(filter=stale_filter),
            wait=True,
        )

    def search(
        self,
        vector: list[float],
        limit: int = 5,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query_filter = None
        if document_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )

        result = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )

        return [
            {"score": point.score, **(point.payload or {})}
            for point in result.points
        ]

    def delete_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def close(self) -> None:
        self.client.close()
