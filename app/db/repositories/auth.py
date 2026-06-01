from datetime import UTC, datetime

from fastapi import Depends

from app.core.security import token_fingerprint
from app.db.repositories.store import InMemoryStore, UserRecord, get_store
from app.services.errors import ConflictError, UnauthorizedError


class AuthRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_user(self, email: str, username: str, password_hash: str, role: str = "player") -> UserRecord:
        email_key = email.strip().lower()
        username_key = username.strip().lower()

        if email_key in self.store.users_by_email:
            raise ConflictError("EMAIL_ALREADY_EXISTS", "Email already registered")
        if username_key in self.store.users_by_username:
            raise ConflictError("USERNAME_ALREADY_EXISTS", "Username already registered")

        self.store._user_seq += 1
        user = UserRecord(
            id=self.store._user_seq,
            email=email.strip().lower(),
            username=username.strip(),
            password_hash=password_hash,
            role=role,
            status="active",
            created_at=datetime.now(UTC),
        )
        self.store.users[user.id] = user
        self.store.users_by_email[email_key] = user.id
        self.store.users_by_username[username_key] = user.id
        return user

    def get_user_by_email(self, email: str) -> UserRecord | None:
        user_id = self.store.users_by_email.get(email.strip().lower())
        if user_id is None:
            return None
        return self.store.users.get(user_id)

    def get_user_by_id(self, user_id: int) -> UserRecord | None:
        return self.store.users.get(user_id)

    def save_refresh_token(self, refresh_token: str, user_id: int) -> None:
        self.store.refresh_tokens[token_fingerprint(refresh_token)] = user_id

    def consume_refresh_token(self, refresh_token: str, expected_user_id: int) -> int:
        user_id = self.store.refresh_tokens.pop(token_fingerprint(refresh_token), None)
        if user_id is None:
            raise UnauthorizedError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or revoked")
        if user_id != expected_user_id:
            raise UnauthorizedError("INVALID_REFRESH_TOKEN", "Refresh token subject mismatch")
        return user_id


def get_auth_repository(store: InMemoryStore = Depends(get_store)) -> AuthRepository:
    return AuthRepository(store)
