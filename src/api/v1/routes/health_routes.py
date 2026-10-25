
from fastapi import APIRouter, HTTPException, Request
from pymongo.errors import PyMongoError

from src.schemas.response_schema import (
    APIResponse,
    HealthData,
)


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "/live",
    response_model=APIResponse[HealthData],
)
async def liveness_check() -> APIResponse[HealthData]:
    return APIResponse(
        message="Application is alive",
        data=HealthData(status="ok"),
    )



@router.get(
    "/ready",
    response_model=APIResponse[HealthData],
)
async def readiness_check(
    request: Request,
) -> APIResponse[HealthData]:
    try:
        await request.app.state.db.command("ping")

    except PyMongoError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database service is unavailable",
        ) from exc

    return APIResponse(
        message="Application is ready",
        data=HealthData(status="ready"),
    )
