# Система внутриигровых покупок

Backend-сервис для регистрации пользователей, пополнения кошелька, покупки внутриигровых товаров, просмотра инвентаря и оформления возвратов.

Стек: `Python`, `FastAPI`, `Pydantic`, `SQLAlchemy`, `Alembic`, `PostgreSQL`, `Redis`, `Docker`, `Docker Compose`, `Pytest`, `Uvicorn`.

## 1) Готовые артефакты

- `Dockerfile`
- `docker-compose.yml` (`app + postgres + redis`)
- `.env.example`
- `alembic/` (миграции)
- `tests/` (API + rollback + test DB fixtures)
- `docs/api_contract_mvp.md`

## 2) Быстрый запуск

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

API: `http://localhost:8000`

Swagger: `http://localhost:8000/docs`

## 3) Команды сдачи (build/up/migrate/test/down)

```bash
# build
docker compose build

# up
docker compose up -d

# migrate
docker compose exec app alembic upgrade head

# test
docker compose exec app pytest -q

# down
docker compose down -v
```

## 4) Миграции

Применить:

```bash
docker compose exec app alembic upgrade head
```

Откатить на 1 ревизию:

```bash
docker compose exec app alembic downgrade -1
```

## 5) Тесты

Запуск:

```bash
docker compose exec app pytest -q
```

Покрытие:

```bash
docker compose exec app pytest --cov=app --cov-report=term-missing --cov-report=xml
```


```bash
docker compose exec app pytest --cov=app --cov-fail-under=90
```

## 6) Примеры запросов

Регистрация:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "player@example.com",
    "username": "player_1",
    "password": "StrongPass123"
  }'
```

Логин:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "player@example.com",
    "password": "StrongPass123"
  }'
```

Пополнение кошелька:

```bash
curl -X POST http://localhost:8000/api/v1/wallet/topup \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "1000.00",
    "reason": "test topup"
  }'
```

Покупка:

```bash
curl -X POST http://localhost:8000/api/v1/purchases \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Idempotency-Key: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": 1,
    "quantity": 1
  }'
```

Возврат:

```bash
curl -X POST http://localhost:8000/api/v1/refunds \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "purchase_id": 1,
    "reason": "mistaken purchase"
  }'
```
