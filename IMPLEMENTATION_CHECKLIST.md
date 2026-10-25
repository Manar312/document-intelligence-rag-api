# Validation checklist (run only after merging)

- [ ] `python -m pip install -r requirements.txt`
- [ ] `docker compose ps` shows MongoDB and Qdrant healthy/running
- [ ] `python -m compileall src`
- [ ] `uvicorn src.main:app --host 127.0.0.1 --port 8000`
- [ ] `GET /api/v1/health/live`
- [ ] `GET /api/v1/health/ready`
- [ ] Upload a small TXT file through Swagger
- [ ] Verify returned status is `indexed`
- [ ] GET its `/pages` and `/chunks`
- [ ] POST `/api/v1/query` with `generate=false`
- [ ] Upload a small PDF and inspect extraction quality, especially Arabic
- [ ] Delete the disposable test document and verify its file/content/chunks are gone
- [ ] Only after local tests, configure LLM credentials and test generation
