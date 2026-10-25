import asyncio
import json
import sys
import traceback
from importlib.util import find_spec
from uuid import NAMESPACE_URL, uuid5

import httpx

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import get_settings

DOCUMENT_IDS = [
    "800836a7-b766-4a05-9628-feb85c30f387",
    "40528492-4851-4ab2-a041-a8dbc56a74b5",
]

results = []

def record(name, passed, detail=""):
    results.append({
        "test": name,
        "status": "PASS" if passed else "FAIL",
        "detail": str(detail),
    })
    symbol = "PASS" if passed else "FAIL"
    print(f"[{symbol}] {name}: {detail}")

def skip(name, detail):
    results.append({
        "test": name,
        "status": "SKIP",
        "detail": str(detail),
    })
    print(f"[SKIP] {name}: {detail}")

async def main():
    settings = get_settings()
    database = None
    mongo_client = None
    qdrant = None
    redis_client = None

    print("\n=== Document Intelligence RAG: Full Read-only Check ===\n")

    # 1. MongoDB
    try:
        from pymongo import AsyncMongoClient

        mongo_client = AsyncMongoClient(
            host=settings.mongo_host,
            port=settings.mongo_port,
            username=settings.mongo_app_username,
            password=settings.mongo_app_password.get_secret_value(),
            authSource=settings.mongo_auth_source,
            serverSelectionTimeoutMS=5000,
        )
        await mongo_client.admin.command("ping")
        database = mongo_client[settings.mongo_database]
        record("MongoDB connection", True, "ping successful")
    except Exception as exc:
        record("MongoDB connection", False, repr(exc))

    # 2. Redis
    try:
        import redis.asyncio as redis_async

        redis_client = redis_async.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        pong = await redis_client.ping()
        record("Redis connection", bool(pong), f"PING={pong}")
    except Exception as exc:
        record("Redis connection", False, repr(exc))

    # 3. Qdrant and collection configuration
    try:
        from src.providers.qdrant_provider import QdrantProvider

        qdrant = QdrantProvider(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_dimensions,
        )
        info = qdrant.client.get_collection(
            settings.qdrant_collection
        )
        vector_size = info.config.params.vectors.size
        record(
            "Qdrant collection and vector dimensions",
            vector_size == settings.embedding_dimensions,
            f"collection={settings.qdrant_collection}, "
            f"points={info.points_count}, dimensions={vector_size}",
        )
    except Exception as exc:
        record("Qdrant connection/collection", False, repr(exc))

    # 4. Document records, content pages, chunks
    if database is not None:
        for document_id in DOCUMENT_IDS:
            try:
                doc = await database["documents"].find_one(
                    {"id": document_id},
                    {"_id": 0},
                )
                pages = await database["document_contents"].count_documents(
                    {"document_id": document_id}
                )
                chunks = await database["document_chunks"].count_documents(
                    {"document_id": document_id}
                )

                valid = (
                    doc is not None
                    and doc.get("status") == "indexed"
                    and pages > 0
                    and chunks > 0
                )
                record(
                    f"Mongo document integrity: {document_id}",
                    valid,
                    f"exists={doc is not None}, "
                    f"status={doc.get('status') if doc else None}, "
                    f"pages={pages}, chunks={chunks}",
                )
            except Exception as exc:
                record(
                    f"Mongo document integrity: {document_id}",
                    False,
                    repr(exc),
                )
    else:
        skip("Mongo document integrity", "MongoDB unavailable")

    # 5. Deterministic Qdrant point IDs and payloads
    if qdrant is not None:
        for document_id in DOCUMENT_IDS:
            try:
                expected_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"02-rag:{document_id}:0",
                    )
                )
                points = qdrant.client.retrieve(
                    collection_name=settings.qdrant_collection,
                    ids=[expected_id],
                    with_payload=True,
                    with_vectors=True,
                )
                point = points[0] if points else None
                payload = point.payload or {} if point else {}
                vector = point.vector if point else None

                # Qdrant may return a vector dictionary for named vectors.
                if isinstance(vector, dict):
                    vector = next(iter(vector.values()), [])

                valid = (
                    point is not None
                    and payload.get("document_id") == document_id
                    and int(payload.get("chunk_index", -1)) == 0
                    and len(vector or []) == settings.embedding_dimensions
                )
                record(
                    f"Qdrant vector integrity: {document_id}",
                    valid,
                    f"point_exists={point is not None}, "
                    f"payload_document_matches="
                    f"{payload.get('document_id') == document_id}, "
                    f"vector_dimensions={len(vector or [])}",
                )
            except Exception as exc:
                record(
                    f"Qdrant vector integrity: {document_id}",
                    False,
                    repr(exc),
                )
    else:
        skip("Qdrant vector integrity", "Qdrant unavailable")

    # 6. Real semantic retrieval; no writes to MongoDB or Qdrant
    if qdrant is not None:
        try:
            from src.providers.embedding_provider import EmbeddingProvider

            embedding = EmbeddingProvider(
                settings.embedding_model,
                settings.embedding_dimensions,
            )
            question = (
                "What is Retrieval-Augmented Generation and "
                "how does document retrieval work?"
            )
            query_vector = embedding.embed_query(question)
            matches = qdrant.search(query_vector, limit=5)

            valid = (
                len(query_vector) == settings.embedding_dimensions
                and len(matches) > 0
                and all("document_id" in item and "text" in item
                        for item in matches)
            )
            record(
                "Semantic retrieval from Qdrant",
                valid,
                f"results={len(matches)}, "
                f"query_dimensions={len(query_vector)}, "
                f"top_document={matches[0].get('document_id') if matches else None}",
            )
            if matches:
                print("  Top result preview:", str(matches[0].get("text", ""))[:180])
        except Exception as exc:
            record("Semantic retrieval from Qdrant", False, repr(exc))
    else:
        skip("Semantic retrieval from Qdrant", "Qdrant unavailable")

    # 7. HTTP endpoints. The API server must already be running.
    base_url = f"http://{settings.host}:{settings.port}"
    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=60,
        ) as client:
            live = await client.get(
                f"{settings.api_v1_prefix}/health/live"
            )
            live_ok = live.status_code == 200
            record(
                "API liveness endpoint",
                live_ok,
                f"HTTP {live.status_code}",
            )

            ready = await client.get(
                f"{settings.api_v1_prefix}/health/ready"
            )
            ready_ok = ready.status_code == 200
            record(
                "API readiness endpoint",
                ready_ok,
                f"HTTP {ready.status_code}",
            )

            # Request retrieval only; generation is deliberately disabled.
            query_response = await client.post(
                f"{settings.api_v1_prefix}/query",
                json={
                    "question": (
                        "What is Retrieval-Augmented Generation?"
                    ),
                    "top_k": 5,
                    "generate": False,
                },
            )

            if query_response.status_code == 200:
                body = query_response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []
                valid = (
                    body.get("success") is True
                    and data.get("generation_status")
                    in {"not_requested", "no_relevant_context"}
                    and isinstance(sources, list)
                )
                record(
                    "Query API retrieval-only request",
                    valid,
                    f"HTTP {query_response.status_code}, "
                    f"sources={len(sources)}, "
                    f"generation_status={data.get('generation_status')}",
                )
                if sources:
                    print(
                        "  First source preview:",
                        str(sources[0].get("text", ""))[:180],
                    )
            else:
                record(
                    "Query API retrieval-only request",
                    False,
                    f"HTTP {query_response.status_code}: "
                    f"{query_response.text[:300]}",
                )

            # Invalid input should be rejected by request validation.
            invalid = await client.post(
                f"{settings.api_v1_prefix}/query",
                json={"question": "", "generate": False},
            )
            record(
                "Query API rejects empty question",
                invalid.status_code == 422,
                f"HTTP {invalid.status_code}",
            )

    except Exception as exc:
        record(
            "API HTTP checks",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    finally:
        if qdrant is not None:
            try:
                qdrant.close()
            except Exception:
                pass
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception:
                pass
        if mongo_client is not None:
            try:
                await mongo_client.close()
            except Exception:
                pass

    print("\n=== FINAL REPORT ===")
    passed = sum(x["status"] == "PASS" for x in results)
    failed = sum(x["status"] == "FAIL" for x in results)
    skipped = sum(x["status"] == "SKIP" for x in results)
    print(f"PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    report_path = "scripts/full_check_report.json"
    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
