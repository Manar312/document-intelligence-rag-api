from fastapi import APIRouter

from src.api.v1.routes.document_routes import router as document_router
from src.api.v1.routes.health_routes import router as health_router
from src.api.v1.routes.query_routes import router as query_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(document_router)
api_router.include_router(query_router)
