# Document Intelligence RAG API

FastAPI backend for document ingestion, processing, semantic retrieval, and Retrieval-Augmented Generation.

## Features
- Document upload, listing, retrieval, and deletion.
- MongoDB for document metadata and content.
- Qdrant for vector search.
- FastEmbed multilingual embeddings.
- Redis and Celery for background processing.
- Configurable LLM provider.
- Health and readiness endpoints.

## Run locally
```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
docker compose up -d
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Swagger UI: http://127.0.0.1:8000/docs

## Configuration
Configure local credentials and API keys in .env. Never commit .env or real secrets.
