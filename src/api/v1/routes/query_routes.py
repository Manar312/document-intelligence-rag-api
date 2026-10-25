import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.v1.dependencies import get_rag_service
from src.schemas.document_schema import QueryData, QueryRequest
from src.schemas.response_schema import APIResponse
from src.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["RAG"])


@router.post("", response_model=APIResponse[QueryData])
async def query_documents(
    request: QueryRequest,
    service: RAGService = Depends(get_rag_service),
) -> APIResponse[QueryData]:
    try:
        result = await service.query(
            question=request.question,
            top_k=request.top_k,
            document_id=request.document_id,
            generate=request.generate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("RAG query failed during retrieval or generation")
        raise HTTPException(
            status_code=503,
            detail="Retrieval or generation service failed.",
        ) from None

    return APIResponse(
        message="Query completed.",
        data=result,
    )
