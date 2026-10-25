from datetime import datetime
from pydantic import BaseModel, Field


class DocumentUploadData(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime
    page_count: int | None = None
    chunk_count: int | None = None


class DocumentListData(BaseModel):
    items: list[DocumentUploadData]
    skip: int
    limit: int


class DocumentPageData(BaseModel):
    page_number: int
    text: str
    character_count: int
    extraction_method: str = "text"


class DocumentChunkData(BaseModel):
    document_id: str
    chunk_index: int
    page_number: int
    text: str
    character_count: int
    start_char: int
    end_char: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_id: str | None = None
    generate: bool = True


class QuerySource(BaseModel):
    document_id: str
    chunk_index: int
    page_number: int
    score: float
    text: str


class QueryData(BaseModel):
    question: str
    answer: str | None = None
    generation_status: str
    sources: list[QuerySource]
