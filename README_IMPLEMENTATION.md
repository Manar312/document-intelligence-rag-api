# Document Intelligence RAG API — implementation bundle

This bundle builds on the uploaded source ZIP and adds the currently missing connected pipeline.

## Features included
- FastAPI + Swagger UI, versioned at `/api/v1`
- Existing MongoDB connection, using the existing local host port `27018`
- Local upload with size limit
- PDF text extraction with OCR fallback; TXT, DOCX, PNG, JPG/JPEG, TIFF parsing
- Page-preserving text storage in MongoDB
- Character chunking with overlap
- FastEmbed embeddings and Qdrant indexing
- Similarity retrieval filtered optionally by document ID
- Optional OpenAI-compatible chat-completions generation
- Document listing, detail, pages, chunks, and deletion endpoints
- Consistent API response envelope

## Important limits
1. Upload processing is synchronous in this implementation. Large files may take time and the request may time out. Celery/Redis job processing is a separate production hardening step, not silently claimed to be implemented here.
2. OCR accuracy depends on installed RapidOCR model support. The parser uses Arabic recognition with the PP-OCRv5 config; confirm the installed RapidOCR version and downloaded models during testing.
3. No LLM key is required for retrieval. If `LLM_API_KEY` and `LLM_MODEL` are empty, `/query` returns retrieved source chunks and `generation_status=llm_not_configured`; it does not fabricate an answer.
4. This project has no authentication/authorization yet. Do not expose it to the public internet without adding those controls.
5. Deletion removes the Mongo document, pages, chunks, local file, and Qdrant points. Test on disposable uploads first.

## Apply safely on Windows
1. Keep the current project folder as a backup. Do not delete the existing Mongo volume.
2. Extract this ZIP to a temporary folder first.
3. Compare/merge its `src`, `requirements.txt`, `.env.example`, and README into `F:\\02-RAG`. The ZIP includes your original assets and Mongo setup too.
4. Keep your current `.env` unchanged. Add only missing values from `.env.example` manually. Do not replace your passwords with the example values.
5. Install dependencies in the active virtual environment:
   `python -m pip install -r requirements.txt`
6. Ensure MongoDB and Qdrant are running:
   `docker compose up -d mongodb qdrant`
7. Start the API:
   `uvicorn src.main:app --host 127.0.0.1 --port 8000`
8. Open `http://127.0.0.1:8000/docs`.

## Endpoints
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/documents` (multipart field `file`)
- `GET /api/v1/documents?skip=0&limit=20`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/pages`
- `GET /api/v1/documents/{document_id}/chunks`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/query`

Example query body:
```json
{
  "question": "Summarize the main points",
  "top_k": 5,
  "generate": false
}
```

For generated answers, set `LLM_API_KEY` and `LLM_MODEL` in `.env` for an OpenAI-compatible endpoint. Keep secrets out of source control.

## Known design decision
The current `DocumentService` runs parsing, chunking, embedding, and indexing in the upload request to make the first end-to-end flow testable. For a more resilient production deployment, move this work into a background queue (Celery/Redis or another job runner), add job status polling, idempotent retries, and transactional cleanup.
