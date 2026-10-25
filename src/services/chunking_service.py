from typing import Any


class ChunkingService:
    def __init__(self, chunk_size: int = 1000, overlap: int = 150) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size.")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_pages(
        self, document_id: str, pages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        step = self.chunk_size - self.overlap

        for page in pages:
            text = str(page.get("text", "")).strip()
            if not text:
                continue
            page_number = int(page["page_number"])
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "document_id": document_id,
                        "page_number": page_number,
                        "chunk_index": len(chunks),
                        "text": chunk_text,
                        "character_count": len(chunk_text),
                        "start_char": start,
                        "end_char": end,
                    })
                if end >= len(text):
                    break
                start += step
        return chunks
