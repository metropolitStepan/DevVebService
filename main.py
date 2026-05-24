import asyncio
import csv
import hashlib
import itertools
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Union

import redis.asyncio as redis_async
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy import Float, Integer, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


Number = Union[int, float]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "120"))
CACHE_PREFIX = "course-api"
ITEM_CACHE_PREFIX = f"{CACHE_PREFIX}:items"
CALCULATE_CACHE_PREFIX = f"{CACHE_PREFIX}:calculate"


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


@dataclass(slots=True)
class UserRecord:
    user_id: int
    username: str
    password_hash: str


@dataclass(slots=True)
class TaskState:
    task_id: str
    operation: str
    status: str
    detail: str
    processed: int = 0


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


class CalculateRequest(BaseModel):
    numbers: list[Number] = Field(..., min_length=1, description="Список чисел")
    delays: list[float] = Field(..., min_length=1, description="Список задержек в секундах")


class CalculationResult(BaseModel):
    number: Number
    square: Number
    delay: float
    time: float


class CalculateResponse(BaseModel):
    results: list[CalculationResult]
    total_time: float
    parallel_faster_than_sequential: bool


class ItemCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = Field(..., min_length=1, max_length=120)
    price: float = Field(..., gt=0)
    quantity: int = Field(..., ge=0)


class ItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    price: float | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=0)


class ItemResponse(BaseModel):
    id: int
    name: str
    category: str
    price: float
    quantity: int


class ItemsListResponse(BaseModel):
    items: list[ItemResponse]
    limit: int
    offset: int
    returned: int


class ImportCsvRequest(BaseModel):
    file_path: str = Field(..., min_length=1, description="Путь до CSV файла")


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, description="Список id записей")


class BackgroundTaskStatus(BaseModel):
    task_id: str
    operation: str
    status: str
    detail: str
    processed: int


app = FastAPI(title="Calculate API")
auth_router = APIRouter(prefix="/auth", tags=["auth"])
items_router = APIRouter(prefix="/items", tags=["items"])

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

users_by_id: dict[int, UserRecord] = {}
users_by_username: dict[str, UserRecord] = {}
active_sessions: set[int] = set()
next_user_id = itertools.count(start=1)

redis_client: redis_async.Redis | None = None
background_job_states: dict[str, TaskState] = {}


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


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


def map_item(item: Item) -> ItemResponse:
    return ItemResponse(
        id=item.id,
        name=item.name,
        category=item.category,
        price=item.price,
        quantity=item.quantity,
    )


def create_task_state(operation: str, detail: str) -> TaskState:
    task_id = uuid.uuid4().hex
    state = TaskState(
        task_id=task_id,
        operation=operation,
        status="queued",
        detail=detail,
        processed=0,
    )
    background_job_states[task_id] = state
    return state


def update_task_state(
    task_id: str,
    *,
    status_value: str | None = None,
    detail: str | None = None,
    processed: int | None = None,
) -> None:
    state = background_job_states.get(task_id)
    if state is None:
        return

    if status_value is not None:
        state.status = status_value
    if detail is not None:
        state.detail = detail
    if processed is not None:
        state.processed = processed


def get_task_status(task_id: str) -> BackgroundTaskStatus:
    state = background_job_states.get(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Фоновая задача не найдена.")

    return BackgroundTaskStatus(
        task_id=state.task_id,
        operation=state.operation,
        status=state.status,
        detail=state.detail,
        processed=state.processed,
    )


async def get_cache_json(cache_key: str) -> dict[str, Any] | None:
    if redis_client is None:
        return None

    try:
        payload = await redis_client.get(cache_key)
    except RedisError:
        return None

    if payload is None:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed
    return None


async def set_cache_json(cache_key: str, payload: dict[str, Any]) -> None:
    if redis_client is None:
        return

    try:
        serialized = json.dumps(payload, ensure_ascii=False)
        await redis_client.set(cache_key, serialized, ex=CACHE_TTL_SECONDS)
    except (TypeError, RedisError):
        return


async def clear_cache_by_pattern(pattern: str) -> None:
    if redis_client is None:
        return

    try:
        async for key in redis_client.scan_iter(match=pattern):
            await redis_client.delete(key)
    except RedisError:
        return


def build_items_list_cache_key(user_id: int, limit: int, offset: int) -> str:
    return f"{ITEM_CACHE_PREFIX}:list:{user_id}:{limit}:{offset}"


def build_item_cache_key(user_id: int, item_id: int) -> str:
    return f"{ITEM_CACHE_PREFIX}:one:{user_id}:{item_id}"


def build_calculate_cache_key(user_id: int, payload: CalculateRequest) -> str:
    digest_source = json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()
    return f"{CALCULATE_CACHE_PREFIX}:{user_id}:{digest}"


async def clear_items_cache() -> None:
    await clear_cache_by_pattern(f"{ITEM_CACHE_PREFIX}:*")


async def run_csv_import_task(task_id: str, csv_path: str) -> None:
    update_task_state(task_id, status_value="running", detail="Чтение CSV файла...")

    source_path = Path(csv_path).expanduser()
    if not source_path.is_file():
        update_task_state(task_id, status_value="failed", detail="Файл не найден.")
        return

    inserted_rows = 0
    try:
        with source_path.open("r", encoding="utf-8", newline="") as source_file:
            reader = csv.DictReader(source_file)
            fieldnames = reader.fieldnames or []
            normalized = {name.strip().lower() for name in fieldnames}
            required = {"name", "category", "price", "quantity"}
            key_lookup = {name.strip().lower(): name for name in fieldnames}

            if not required.issubset(normalized):
                update_task_state(
                    task_id,
                    status_value="failed",
                    detail="CSV должен содержать колонки: name, category, price, quantity.",
                )
                return

            items_to_create: list[Item] = []
            for row in reader:
                name = (row.get(key_lookup["name"]) or "").strip()
                category = (row.get(key_lookup["category"]) or "").strip()
                price_raw = (row.get(key_lookup["price"]) or "").strip()
                quantity_raw = (row.get(key_lookup["quantity"]) or "").strip()

                if not name or not category:
                    continue

                try:
                    price = float(price_raw)
                    quantity = int(quantity_raw)
                except ValueError:
                    continue

                if price <= 0 or quantity < 0:
                    continue

                items_to_create.append(
                    Item(
                        name=name,
                        category=category,
                        price=price,
                        quantity=quantity,
                    )
                )

            if items_to_create:
                async with AsyncSessionLocal() as session:
                    session.add_all(items_to_create)
                    await session.commit()

            inserted_rows = len(items_to_create)
    except OSError as error:
        update_task_state(task_id, status_value="failed", detail=f"Ошибка чтения файла: {error}")
        return

    await clear_items_cache()
    update_task_state(
        task_id,
        status_value="done",
        detail=f"Импорт завершен. Добавлено записей: {inserted_rows}.",
        processed=inserted_rows,
    )


async def run_bulk_delete_task(task_id: str, item_ids: list[int]) -> None:
    update_task_state(task_id, status_value="running", detail="Удаление записей...")

    unique_ids = sorted(set(item_ids))
    if not unique_ids:
        update_task_state(task_id, status_value="done", detail="Список id пуст.", processed=0)
        return

    try:
        async with AsyncSessionLocal() as session:
            ids_result = await session.execute(select(Item.id).where(Item.id.in_(unique_ids)))
            existing_ids = ids_result.scalars().all()

            if existing_ids:
                await session.execute(delete(Item).where(Item.id.in_(existing_ids)))
                await session.commit()

            removed_count = len(existing_ids)
    except Exception as error:  # noqa: BLE001
        update_task_state(task_id, status_value="failed", detail=f"Ошибка удаления: {error}")
        return

    await clear_items_cache()
    update_task_state(
        task_id,
        status_value="done",
        detail=f"Удаление завершено. Удалено записей: {removed_count}.",
        processed=removed_count,
    )


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


@items_router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreateRequest,
    _: UserRecord = Depends(authorize_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemResponse:
    clean_name = payload.name.strip()
    clean_category = payload.category.strip()
    if not clean_name or not clean_category:
        raise HTTPException(status_code=422, detail="Поля name и category не могут быть пустыми.")

    item = Item(
        name=clean_name,
        category=clean_category,
        price=payload.price,
        quantity=payload.quantity,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    await clear_items_cache()
    return map_item(item)


@items_router.get("/", response_model=ItemsListResponse)
async def list_items(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: UserRecord = Depends(authorize_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemsListResponse:
    cache_key = build_items_list_cache_key(current_user.user_id, limit, offset)
    cached = await get_cache_json(cache_key)
    if cached is not None:
        return ItemsListResponse(**cached)

    result = await session.execute(select(Item).order_by(Item.id).offset(offset).limit(limit))
    rows = result.scalars().all()

    response = ItemsListResponse(
        items=[map_item(item) for item in rows],
        limit=limit,
        offset=offset,
        returned=len(rows),
    )
    await set_cache_json(cache_key, response.model_dump())
    return response


@items_router.post("/import-csv", response_model=BackgroundTaskStatus, status_code=status.HTTP_202_ACCEPTED)
async def import_items_from_csv(
    payload: ImportCsvRequest,
    background_tasks: BackgroundTasks,
    _: UserRecord = Depends(authorize_user),
) -> BackgroundTaskStatus:
    task_state = create_task_state("import_csv", "Задача поставлена в очередь.")
    background_tasks.add_task(run_csv_import_task, task_state.task_id, payload.file_path)
    return get_task_status(task_state.task_id)


@items_router.post("/bulk-delete", response_model=BackgroundTaskStatus, status_code=status.HTTP_202_ACCEPTED)
async def bulk_delete_items(
    payload: BulkDeleteRequest,
    background_tasks: BackgroundTasks,
    _: UserRecord = Depends(authorize_user),
) -> BackgroundTaskStatus:
    task_state = create_task_state("bulk_delete", "Задача поставлена в очередь.")
    background_tasks.add_task(run_bulk_delete_task, task_state.task_id, payload.ids)
    return get_task_status(task_state.task_id)


@items_router.get("/tasks/{task_id}", response_model=BackgroundTaskStatus)
async def get_background_task_status(
    task_id: str,
    _: UserRecord = Depends(authorize_user),
) -> BackgroundTaskStatus:
    return get_task_status(task_id)


@items_router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    current_user: UserRecord = Depends(authorize_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemResponse:
    cache_key = build_item_cache_key(current_user.user_id, item_id)
    cached = await get_cache_json(cache_key)
    if cached is not None:
        return ItemResponse(**cached)

    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")

    response = map_item(item)
    await set_cache_json(cache_key, response.model_dump())
    return response


@items_router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    payload: ItemUpdateRequest,
    _: UserRecord = Depends(authorize_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemResponse:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="Не переданы поля для обновления.")

    if "name" in update_data:
        clean_name = update_data["name"].strip()
        if not clean_name:
            raise HTTPException(status_code=422, detail="Поле name не может быть пустым.")
        item.name = clean_name
    if "category" in update_data:
        clean_category = update_data["category"].strip()
        if not clean_category:
            raise HTTPException(status_code=422, detail="Поле category не может быть пустым.")
        item.category = clean_category
    if "price" in update_data:
        item.price = update_data["price"]
    if "quantity" in update_data:
        item.quantity = update_data["quantity"]

    await session.commit()
    await session.refresh(item)

    await clear_items_cache()
    return map_item(item)


@items_router.delete("/{item_id}", response_model=MessageResponse)
async def delete_item(
    item_id: int,
    _: UserRecord = Depends(authorize_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")

    await session.delete(item)
    await session.commit()

    await clear_items_cache()
    return MessageResponse(detail="Запись удалена.")


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
    current_user: UserRecord = Depends(authorize_user),
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

    cache_key = build_calculate_cache_key(current_user.user_id, data)
    cached = await get_cache_json(cache_key)
    if cached is not None:
        return CalculateResponse(**cached)

    start_time = time.perf_counter()
    task_results = await asyncio.gather(
        *(calculate_square(number, delay) for number, delay in zip(data.numbers, data.delays))
    )
    total_time_raw = time.perf_counter() - start_time
    results = [result for result, _ in task_results]
    sequential_time_raw = sum(elapsed for _, elapsed in task_results)

    response = CalculateResponse(
        results=results,
        total_time=round(total_time_raw, 2),
        parallel_faster_than_sequential=total_time_raw < sequential_time_raw,
    )
    await set_cache_json(cache_key, response.model_dump())
    return response


@app.on_event("startup")
async def on_startup() -> None:
    global redis_client

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    redis_instance = redis_async.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    try:
        await redis_instance.ping()
        redis_client = redis_instance
    except RedisError:
        await redis_instance.aclose()
        redis_client = None


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if redis_client is not None:
        await redis_client.aclose()

    await engine.dispose()


app.include_router(auth_router)
app.include_router(items_router)
