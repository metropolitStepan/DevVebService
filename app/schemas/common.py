from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ApiErrorDetail(BaseModel):
    field: str | None = None
    reason: str
    value: Any | None = None


class ApiError(BaseModel):
    code: str
    message: str
    details: list[ApiErrorDetail] = Field(default_factory=list)
    request_id: str
    timestamp: str


class MessageResponse(BaseModel):
    detail: str


def build_error_payload(code: str, message: str, details: list[ApiErrorDetail] | None = None) -> ApiError:
    return ApiError(
        code=code,
        message=message,
        details=details or [],
        request_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
    )
