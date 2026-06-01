from fastapi import Depends

from app.core.config import settings
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.db.repositories.auth import AuthRepository, get_auth_repository
from app.db.repositories.wallet import WalletRepository, get_wallet_repository
from app.schemas.auth import AuthResponse, TokenPairResponse, UserResponse
from app.services.errors import BadRequestError, ForbiddenError, UnauthorizedError


class AuthService:
    def __init__(self, auth_repo: AuthRepository, wallet_repo: WalletRepository) -> None:
        self.auth_repo = auth_repo
        self.wallet_repo = wallet_repo

    async def register(self, *, email: str, username: str, password: str) -> AuthResponse:
        normalized_email = _normalize_email(email)
        normalized_username = _normalize_username(username)

        try:
            validate_password_policy(password)
        except ValueError as error:
            raise BadRequestError("WEAK_PASSWORD", str(error)) from error

        user = self.auth_repo.create_user(
            email=normalized_email,
            username=normalized_username,
            password_hash=hash_password(password),
            role="player",
        )
        self.wallet_repo.get_or_create_wallet(user.id)
        return self._build_auth_response(user.id)

    async def login(self, *, email: str, password: str) -> AuthResponse:
        normalized_email = _normalize_email(email)
        user = self.auth_repo.get_user_by_email(normalized_email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password")

        if user.status != "active":
            raise ForbiddenError("USER_BLOCKED", "User is blocked")

        return self._build_auth_response(user.id)

    async def refresh(self, refresh_token: str) -> TokenPairResponse:
        try:
            payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        except TokenValidationError as error:
            raise UnauthorizedError(error.code, error.message) from error

        user_id = self.auth_repo.consume_refresh_token(refresh_token, expected_user_id=payload.sub)
        user = self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise UnauthorizedError("INVALID_REFRESH_TOKEN", "Refresh token is invalid")

        if user.status != "active":
            raise ForbiddenError("USER_BLOCKED", "User is blocked")

        access_token = create_access_token(user.id, user.role)
        new_refresh_token = create_refresh_token(user.id, user.role)
        self.auth_repo.save_refresh_token(new_refresh_token, user.id)

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_ttl_minutes * 60,
        )

    async def get_user(self, user_id: int) -> UserResponse:
        user = self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise UnauthorizedError("USER_NOT_FOUND", "User not found")

        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
        )

    def _build_auth_response(self, user_id: int) -> AuthResponse:
        user = self.auth_repo.get_user_by_id(user_id)
        if user is None:
            raise UnauthorizedError("USER_NOT_FOUND", "User not found")

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id, user.role)
        self.auth_repo.save_refresh_token(refresh_token, user.id)

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                email=user.email,
                username=user.username,
                role=user.role,
                status=user.status,
                created_at=user.created_at,
            ),
            tokens=TokenPairResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_ttl_minutes * 60,
            ),
        )


def get_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    wallet_repo: WalletRepository = Depends(get_wallet_repository),
) -> AuthService:
    return AuthService(auth_repo=auth_repo, wallet_repo=wallet_repo)


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise BadRequestError("INVALID_EMAIL", "Email format is invalid")
    return value


def _normalize_username(username: str) -> str:
    value = username.strip()
    if len(value) < 3 or len(value) > 50:
        raise BadRequestError("INVALID_USERNAME", "Username length is invalid")
    return value
