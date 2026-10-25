from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from src.enums.error_code import ErrorCode


DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    message: str
    data: DataT | None = None
    meta: dict[str, Any] | None = None


class ErrorDetails(BaseModel):
    code: ErrorCode
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = False
    message: str
    error: ErrorDetails
    meta: dict[str, Any] | None = None


class HealthData(BaseModel):
    status: str = Field(description="Current application health status")
