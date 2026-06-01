from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import ACCESS_TOKEN_TYPE, TokenValidationError, decode_token
from app.schemas.auth import CurrentUser
from app.services.auth_service import AuthService, get_auth_service
from app.services.errors import ForbiddenError, UnauthorizedError


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> CurrentUser:
    if credentials is None:
        raise UnauthorizedError("AUTH_REQUIRED", "Authorization bearer token is required")
    if credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("INVALID_AUTH_SCHEME", "Authorization scheme must be Bearer")

    try:
        payload = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
        user = await auth_service.get_user(payload.sub)
    except TokenValidationError as error:
        raise UnauthorizedError(error.code, error.message) from error

    if user.status != "active":
        raise ForbiddenError("USER_BLOCKED", "User is blocked")

    return CurrentUser(
        id=user.id,
        role=user.role,
        email=user.email,
        username=user.username,
    )


def role_required(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    normalized_roles = {role.strip().lower() for role in roles if role.strip()}

    def checker(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current_user.role.lower() not in normalized_roles:
            raise ForbiddenError("INSUFFICIENT_ROLE", "Insufficient permissions for this endpoint")
        return current_user

    return checker


require_admin = role_required("admin")
