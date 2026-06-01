from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis import close_redis, init_redis
from app.routers import (
    admin_items_router,
    auth_router,
    health_router,
    inventory_router,
    items_router,
    purchases_router,
    refunds_router,
    wallet_router,
)
from app.schemas.common import ApiErrorDetail, build_error_payload
from app.services.errors import ServiceError


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_redis()
    try:
        yield
    finally:
        await close_redis()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(ServiceError)
async def handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
    payload = build_error_payload(code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "request_id", "timestamp"}.issubset(exc.detail):
        payload = exc.detail
    else:
        payload = build_error_payload(code="HTTP_ERROR", message=str(exc.detail)).model_dump()

    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ApiErrorDetail(
            field=".".join(str(part) for part in error["loc"] if part != "body") or None,
            reason=error["msg"],
            value=error.get("input"),
        )
        for error in exc.errors()
    ]

    payload = build_error_payload(
        code="VALIDATION_ERROR",
        message="Validation failed",
        details=details,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": str(uuid4()),
    }


app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(wallet_router, prefix=settings.api_v1_prefix)
app.include_router(items_router, prefix=settings.api_v1_prefix)
app.include_router(purchases_router, prefix=settings.api_v1_prefix)
app.include_router(inventory_router, prefix=settings.api_v1_prefix)
app.include_router(refunds_router, prefix=settings.api_v1_prefix)
app.include_router(admin_items_router, prefix=settings.api_v1_prefix)
