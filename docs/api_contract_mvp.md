# API-контракт MVP: Система внутриигровых покупок

## Базовые правила

- Базовый префикс: `/api/v1`.
- Формат запросов/ответов: `application/json`.
- Авторизация: `Authorization: Bearer <access_token>`.
- Роли: `player`, `admin`.
- Времена: `ISO-8601 UTC` (`2026-05-30T12:00:00Z`).

## Единый формат ошибок API

```python
from pydantic import BaseModel
from typing import Any

class ApiErrorDetail(BaseModel):
    field: str | None = None
    reason: str
    value: Any | None = None

class ApiError(BaseModel):
    code: str                # machine code, например: ITEM_NOT_FOUND
    message: str             # человекочитаемое описание
    details: list[ApiErrorDetail] = []
    request_id: str          # UUID запроса для трассировки
    timestamp: str           # ISO-8601 UTC
```

Пример:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {"field": "quantity", "reason": "must be greater than 0", "value": 0}
  ],
  "request_id": "9dba5e22-a0e3-4b9c-95a9-8d502ca1b862",
  "timestamp": "2026-05-30T11:22:33Z"
}
```

## Pydantic-схемы (контракт)

```python
from pydantic import BaseModel, EmailStr, Field, conint, condecimal
from decimal import Decimal
from uuid import UUID

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]{3,50}$")
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    role: str
    status: str
    created_at: str

class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenPairResponse

class WalletBalanceResponse(BaseModel):
    wallet_id: int
    user_id: int
    currency_code: str
    balance: Decimal
    updated_at: str

class WalletTopupRequest(BaseModel):
    amount: condecimal(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=255)
    external_ref: str | None = Field(default=None, max_length=128)

class TopupResponse(BaseModel):
    id: int
    wallet_id: int
    amount: Decimal
    status: str
    reason: str
    external_ref: str | None
    created_at: str
    applied_at: str | None

class ItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    stock: int | None
    created_at: str
    updated_at: str

class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    limit: int
    offset: int

class PurchaseCreateRequest(BaseModel):
    item_id: int
    quantity: conint(gt=0)

class PurchaseResponse(BaseModel):
    id: int
    user_id: int
    wallet_id: int
    item_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    status: str
    idempotency_key: UUID
    created_at: str
    completed_at: str | None

class PurchaseListResponse(BaseModel):
    purchases: list[PurchaseResponse]
    total: int
    limit: int
    offset: int

class InventoryItemResponse(BaseModel):
    item_id: int
    sku: str
    name: str
    quantity: int
    updated_at: str

class InventoryListResponse(BaseModel):
    items: list[InventoryItemResponse]
    total: int

class RefundRequestCreate(BaseModel):
    purchase_id: int
    reason: str = Field(min_length=5, max_length=500)

class RefundResponse(BaseModel):
    id: int
    purchase_id: int
    wallet_id: int
    amount: Decimal
    status: str
    reason: str
    created_at: str
    processed_at: str | None

class AdminItemCreateRequest(BaseModel):
    sku: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    price: condecimal(ge=0, max_digits=18, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)

class AdminItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    price: condecimal(ge=0, max_digits=18, decimal_places=2) | None = None
    stock: int | None = Field(default=None, ge=0)

class AdminItemToggleActiveRequest(BaseModel):
    is_active: bool
```

## Эндпоинты

### 1) Auth

#### `POST /api/v1/auth/register`
- Права: `guest`.
- Вход: `RegisterRequest`.
- Успех: `201 Created`, `AuthResponse`.
- Ошибки:
  - `400`: бизнес-правило регистрации нарушено (например, регистрация временно отключена).
  - `401`: не используется.
  - `403`: IP/аккаунт заблокирован политикой безопасности.
  - `404`: не используется.
  - `409`: `email` или `username` уже заняты.
  - `422`: невалидный формат полей.

#### `POST /api/v1/auth/login`
- Права: `guest`.
- Вход: `LoginRequest`.
- Успех: `200 OK`, `AuthResponse`.
- Ошибки:
  - `400`: некорректный тип логина (например, disabled auth method).
  - `401`: неверные учетные данные.
  - `403`: пользователь `blocked`.
  - `404`: не используется.
  - `409`: конфликт сессии/refresh rotation (редко, при повторном использовании refresh family).
  - `422`: невалидный JSON/поля.

#### `POST /api/v1/auth/refresh`
- Права: `guest` (по `refresh_token`).
- Вход: `RefreshRequest`.
- Успех: `200 OK`, `TokenPairResponse`.
- Ошибки:
  - `400`: malformed refresh token.
  - `401`: refresh token просрочен/отозван/подделан.
  - `403`: пользователь заблокирован.
  - `404`: не используется.
  - `409`: token replay detected (refresh уже использован).
  - `422`: невалидное тело запроса.

#### `GET /api/v1/auth/me`
- Права: `player`, `admin`.
- Вход: нет.
- Успех: `200 OK`, `UserResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: отсутствует/некорректный access token.
  - `403`: пользователь заблокирован.
  - `404`: пользователь из токена не найден.
  - `409`: не используется.
  - `422`: не используется.

### 2) Wallet

#### `GET /api/v1/wallet`
- Права: `player`, `admin` (только свой кошелек).
- Вход: нет.
- Успех: `200 OK`, `WalletBalanceResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: неавторизован.
  - `403`: доступ к чужому кошельку запрещен.
  - `404`: кошелек пользователя не найден.
  - `409`: не используется.
  - `422`: не используется.

#### `POST /api/v1/wallet/topup`
- Права: `player`, `admin` (только свой кошелек).
- Вход: `WalletTopupRequest`.
- Успех: `201 Created`, `TopupResponse`.
- Ошибки:
  - `400`: сумма/операция запрещена бизнес-правилами (например, topup disabled).
  - `401`: неавторизован.
  - `403`: попытка пополнить чужой кошелек.
  - `404`: кошелек не найден.
  - `409`: `external_ref` уже использован.
  - `422`: невалидные поля (`amount <= 0`, пустой `reason`).

### 3) Items

#### `GET /api/v1/items?limit=50&offset=0&active_only=true`
- Права: `guest`, `player`, `admin`.
- Вход: query (`limit`, `offset`, `active_only`).
- Успех: `200 OK`, `ItemListResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: не используется.
  - `403`: не используется.
  - `404`: не используется.
  - `409`: не используется.
  - `422`: невалидные query-параметры.

#### `GET /api/v1/items/{item_id}`
- Права: `guest`, `player`, `admin`.
- Вход: path `item_id`.
- Успех: `200 OK`, `ItemResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: не используется.
  - `403`: не используется.
  - `404`: товар не найден или деактивирован для публичного доступа.
  - `409`: не используется.
  - `422`: невалидный `item_id`.

### 4) Purchases

#### `POST /api/v1/purchases`
- Права: `player`, `admin`.
- Вход: `PurchaseCreateRequest`.
- Доп. заголовок: `Idempotency-Key: <uuid>` (обязателен).
- Успех: `201 Created`, `PurchaseResponse` (status `completed`).
- Ошибки:
  - `400`: товар неактивен/недоступен к продаже.
  - `401`: неавторизован.
  - `403`: пользователь заблокирован.
  - `404`: товар или кошелек не найдены.
  - `409`: конфликт остатков/дубликат операции по `Idempotency-Key` с другим payload.
  - `422`: невалидные поля (`quantity <= 0`, плохой UUID в `Idempotency-Key`).

#### `GET /api/v1/purchases?limit=50&offset=0&status=completed`
- Права: `player`, `admin` (игрок видит только свои).
- Вход: query (`limit`, `offset`, `status`).
- Успех: `200 OK`, `PurchaseListResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: неавторизован.
  - `403`: попытка запросить чужую историю.
  - `404`: не используется.
  - `409`: не используется.
  - `422`: невалидные query-параметры.

#### `GET /api/v1/purchases/{purchase_id}`
- Права: `player`, `admin` (игрок только свою покупку).
- Вход: path `purchase_id`.
- Успех: `200 OK`, `PurchaseResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: неавторизован.
  - `403`: нет доступа к покупке другого пользователя.
  - `404`: покупка не найдена.
  - `409`: не используется.
  - `422`: невалидный `purchase_id`.

### 5) Inventory

#### `GET /api/v1/inventory?limit=50&offset=0`
- Права: `player`, `admin` (только свой инвентарь).
- Вход: query (`limit`, `offset`).
- Успех: `200 OK`, `InventoryListResponse`.
- Ошибки:
  - `400`: не используется.
  - `401`: неавторизован.
  - `403`: доступ к чужому инвентарю запрещен.
  - `404`: не используется.
  - `409`: не используется.
  - `422`: невалидные query-параметры.

### 6) Refunds

#### `POST /api/v1/refunds`
- Права: `player`, `admin`.
- Вход: `RefundRequestCreate`.
- Правила MVP:
  - покупка принадлежит пользователю (для `player`);
  - возврат только для `purchases.status = completed`;
  - один возврат на одну покупку;
  - сумма возврата всегда полная (`purchase.total_amount`).
- Успех: `201 Created`, `RefundResponse` (`status = applied` или `pending` по реализации).
- Ошибки:
  - `400`: покупка не подходит под правила возврата (например, `status != completed`).
  - `401`: неавторизован.
  - `403`: нет прав на возврат по чужой покупке.
  - `404`: покупка не найдена.
  - `409`: возврат уже создан для этой покупки.
  - `422`: невалидный `purchase_id`/`reason`.

### 7) Admin Items

#### `POST /api/v1/admin/items`
- Права: `admin`.
- Вход: `AdminItemCreateRequest`.
- Успех: `201 Created`, `ItemResponse`.
- Ошибки:
  - `400`: бизнес-правило каталога нарушено.
  - `401`: неавторизован.
  - `403`: роль не `admin`.
  - `404`: не используется.
  - `409`: `sku` уже существует.
  - `422`: невалидные поля.

#### `PATCH /api/v1/admin/items/{item_id}`
- Права: `admin`.
- Вход: `AdminItemUpdateRequest`.
- Успех: `200 OK`, `ItemResponse`.
- Ошибки:
  - `400`: попытка установить неконсистентные значения.
  - `401`: неавторизован.
  - `403`: роль не `admin`.
  - `404`: товар не найден.
  - `409`: конфликт уникальности/состояния.
  - `422`: невалидные поля.

#### `DELETE /api/v1/admin/items/{item_id}`
- Права: `admin`.
- Вход: path `item_id`.
- Поведение MVP: soft-delete (`deleted_at`, `is_active=false`).
- Успех: `200 OK`, `ItemResponse` или `204 No Content`.
- Ошибки:
  - `400`: удаление запрещено бизнес-правилом.
  - `401`: неавторизован.
  - `403`: роль не `admin`.
  - `404`: товар не найден.
  - `409`: товар участвует в активной операции.
  - `422`: невалидный `item_id`.

#### `POST /api/v1/admin/items/{item_id}/toggle-active`
- Права: `admin`.
- Вход: `AdminItemToggleActiveRequest`.
- Успех: `200 OK`, `ItemResponse`.
- Ошибки:
  - `400`: переход состояния запрещен (например, нельзя активировать при некорректной цене).
  - `401`: неавторизован.
  - `403`: роль не `admin`.
  - `404`: товар не найден.
  - `409`: конфликт состояния (параллельное изменение).
  - `422`: невалидное тело запроса.
