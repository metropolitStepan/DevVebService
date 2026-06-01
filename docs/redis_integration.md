# Redis интеграция (MVP)

## 1) Pub/Sub событие `purchase.created`

Канал:

```text
igs:mvp:events:purchase.created
```

Формат сообщения (JSON envelope):

```json
{
  "event_id": "9f2467f4-52b5-4fc5-ac5f-9bfd0aa2f3df",
  "event_name": "purchase.created",
  "occurred_at": "2026-05-30T20:01:12.123456+00:00",
  "payload": {
    "purchase_id": 101,
    "user_id": 15,
    "wallet_id": 15,
    "item_id": 2,
    "quantity": 1,
    "unit_price": "299.00",
    "total_amount": "299.00",
    "status": "completed",
    "idempotency_key": "f7a2a3af-1be7-4e65-9086-f581abac9f1e",
    "created_at": "2026-05-30T20:01:12.098765+00:00",
    "completed_at": "2026-05-30T20:01:12.098765+00:00"
  }
}
```

Событие публикуется только для новой покупки, не для идемпотентного повтора.

## 2) TTL-механизм

Используется временный резерв на время обработки покупки:

```text
igs:mvp:purchase:reserve:{user_id}:{idempotency_key}
```

- Команда: `SET key "1" EX {ttl_seconds} NX`
- TTL по умолчанию: `30` секунд (`PURCHASE_RESERVE_TTL_SECONDS`)
- Назначение:
  - защита от параллельной двойной обработки одного idempotency key;
  - автоматическое освобождение ключа при падении процесса.

## 3) Деградация при недоступном Redis

- Если Redis не поднялся на старте, приложение продолжает работу в `degraded` режиме.
- Если Redis упал во время запроса:
  - покупка не падает критически;
  - резерв/публикация становятся best-effort;
  - основная консистентность держится на транзакционной бизнес-логике и идемпотентности в основном хранилище.

## 4) Naming convention ключей

Шаблон:

```text
{prefix}:{bounded_context}:{entity}:{detail...}
```

Примеры MVP:

- `igs:mvp:events:purchase.created` — канал событий.
- `igs:mvp:purchase:reserve:{user_id}:{idempotency_key}` — временный lock/reserve.

Префикс (`REDIS_KEY_PREFIX`) обязателен для изоляции окружений (`dev/stage/prod`).

## 5) Подключение в lifecycle FastAPI

- Startup: `init_redis()` (`app/main.py`, lifespan).
- Shutdown: `close_redis()`.
- Readiness: `GET /health/ready` показывает `status=ok|degraded` и `redis=true|false`.
