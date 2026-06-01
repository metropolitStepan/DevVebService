from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]{3,50}$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    role: str
    status: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenPairResponse


class CurrentUser(BaseModel):
    id: int
    role: str
    email: str
    username: str
