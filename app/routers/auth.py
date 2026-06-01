from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user
from app.schemas.auth import (
    AuthResponse,
    CurrentUser,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
)
from app.services.auth_service import AuthService, get_auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    return await service.register(
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    return await service.login(email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    payload: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenPairResponse:
    return await service.refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    return await service.get_user(current_user.id)
