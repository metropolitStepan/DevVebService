import asyncio
import hashlib
import itertools
import time
from dataclasses import dataclass
from typing import Union

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field


Number = Union[int, float]


@dataclass(slots=True)
class UserRecord:
    user_id: int
    username: str
    password_hash: str


class CalculateRequest(BaseModel):
    numbers: list[Number] = Field(..., min_length=1, description="Список чисел")
    delays: list[float] = Field(..., min_length=1, description="Список задержек в секундах")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Логин пользователя")
    password: str = Field(..., min_length=6, max_length=128, description="Пароль пользователя")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Логин пользователя")
    password: str = Field(..., min_length=6, max_length=128, description="Пароль пользователя")


class AuthResponse(BaseModel):
    user_id: int
    username: str


class MessageResponse(BaseModel):
    detail: str


class CalculationResult(BaseModel):
    number: Number
    square: Number
    delay: float
    time: float


class CalculateResponse(BaseModel):
    results: list[CalculationResult]
    total_time: float
    parallel_faster_than_sequential: bool


app = FastAPI(title="Calculate API")
auth_router = APIRouter(prefix="/auth", tags=["auth"])

users_by_id: dict[int, UserRecord] = {}
users_by_username: dict[str, UserRecord] = {}
active_sessions: set[int] = set()
next_user_id = itertools.count(start=1)


def get_password_hash(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def get_username_key(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    clean_username = username.strip()
    if len(clean_username) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Логин должен содержать минимум 3 символа без учета пробелов.",
        )
    return clean_username


def authorize_user(x_user_id: int | None = Header(default=None, alias="X-User-Id")) -> UserRecord:
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация. Передайте заголовок X-User-Id.",
        )

    user = users_by_id.get(x_user_id)
    if user is None or x_user_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия не найдена. Выполните вход повторно.",
        )

    return user


@auth_router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterRequest) -> AuthResponse:
    username = validate_username(payload.username)
    username_key = get_username_key(username)

    if username_key in users_by_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует.",
        )

    user = UserRecord(
        user_id=next(next_user_id),
        username=username,
        password_hash=get_password_hash(payload.password),
    )

    users_by_id[user.user_id] = user
    users_by_username[username_key] = user

    return AuthResponse(user_id=user.user_id, username=user.username)


@auth_router.post("/login", response_model=AuthResponse)
async def login_user(payload: LoginRequest) -> AuthResponse:
    username_key = get_username_key(validate_username(payload.username))
    user = users_by_username.get(username_key)

    if user is None or user.password_hash != get_password_hash(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль.",
        )

    active_sessions.add(user.user_id)
    return AuthResponse(user_id=user.user_id, username=user.username)


@auth_router.post("/logout", response_model=MessageResponse)
async def logout_user(current_user: UserRecord = Depends(authorize_user)) -> MessageResponse:
    active_sessions.discard(current_user.user_id)
    return MessageResponse(detail="Сессия завершена.")


app.include_router(auth_router)


async def calculate_square(number: Number, delay: float) -> tuple[CalculationResult, float]:
    start_time = time.perf_counter()
    await asyncio.sleep(delay)
    elapsed = time.perf_counter() - start_time

    return (
        CalculationResult(
            number=number,
            square=number * number,
            delay=delay,
            time=round(elapsed, 2),
        ),
        elapsed,
    )


@app.post("/calculate/", response_model=CalculateResponse)
async def calculate(
    data: CalculateRequest,
    _: UserRecord = Depends(authorize_user),
) -> CalculateResponse:
    if len(data.numbers) != len(data.delays):
        raise HTTPException(
            status_code=422,
            detail="Количество чисел и задержек должно совпадать.",
        )

    if any(delay < 0 for delay in data.delays):
        raise HTTPException(
            status_code=422,
            detail="Задержки не могут быть отрицательными.",
        )

    start_time = time.perf_counter()
    task_results = await asyncio.gather(
        *(calculate_square(number, delay) for number, delay in zip(data.numbers, data.delays))
    )
    total_time_raw = time.perf_counter() - start_time
    results = [result for result, _ in task_results]
    sequential_time_raw = sum(elapsed for _, elapsed in task_results)

    return CalculateResponse(
        results=results,
        total_time=round(total_time_raw, 2),
        parallel_faster_than_sequential=total_time_raw < sequential_time_raw,
    )
