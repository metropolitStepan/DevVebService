# AUDIT REPORT

Дата аудита: 2026-05-31
Проект: Система внутриигровых покупок (MVP backend)

## Таблица соответствия критериям

| # | Критерий | Status | Evidence (path:line) | Gap | Fix |
|---|---|---|---|---|---|
| 1 | Реализация соответствует функциональным требованиям бэкенда | PARTIAL | `app/routers/auth.py:21`, `app/routers/wallet.py:14`, `app/routers/items.py:12`, `app/routers/purchases.py:15`, `app/routers/inventory.py:14`, `app/routers/refunds.py:14`, `app/routers/admin_items.py:21`, `app/db/repositories/purchases.py:16`, `app/db/repositories/refunds.py:14` | Функционал endpoint реализован, но основная бизнес-логика работает на in-memory store, а не на PostgreSQL/SQLAlchemy | Перевести репозитории на `AsyncSession` + PostgreSQL таблицы и транзакции |
| 2 | Python + FastAPI, PEP 8, осмысленные комментарии | PARTIAL | `app/main.py:6`, `requirements.txt:1`, `app/db/repositories/purchases.py:30`, `app/db/repositories/refunds.py:18` | Стек соблюден, но нет автоматизированной проверки PEP 8 (ruff/flake8), комментариев в критичных транзакционных местах минимум | Добавить lint-пайплайн и точечные комментарии к сложной логике |
| 3 | Декомпозиция на функции/классы/модули | PASS | `app/routers/purchases.py:12`, `app/services/purchase_service.py:16`, `app/db/repositories/purchases.py:12`, `app/core/deps.py:16` | Существенных расхождений не обнаружено | Поддерживать текущую модульность |
| 4 | Логичная структура проекта | PASS | `app/core/config.py:5`, `app/models/user.py:20`, `app/schemas/purchases.py:8`, `app/services/refund_service.py:7`, `app/routers/refunds.py:11` | Существенных расхождений не обнаружено | Поддерживать текущую структуру |
| 5 | Функциональные тесты API ~90% (валидация, бизнес-логика, БД) | FAIL | `tests/api/test_auth_endpoints.py:9`, `tests/api/test_purchases_endpoints.py:12`, `tests/db/test_rollback_and_integrity.py:14`, `tests/db/test_test_database_fixture.py:24`, `tests/conftest.py:57`, `app/db/repositories/store.py:116` | Есть широкий API-набор и rollback-тесты, но реальная БД-проверка практически отсутствует (`SELECT 1`), тесты опираются на in-memory слой; подтвержденный coverage ~90% не зафиксирован | Интеграционные тесты поверх PostgreSQL + покрытие с порогом (`--cov-fail-under=90`) в CI |
| 6 | Модель данных логична и в 3НФ (или выше с обоснованием) | PASS | `alembic/versions/0001_initial_schema.py:42`, `alembic/versions/0001_initial_schema.py:63`, `alembic/versions/0001_initial_schema.py:101`, `alembic/versions/0001_initial_schema.py:143`, `alembic/versions/0001_initial_schema.py:181`, `app/models/purchase.py:29`, `app/models/refund.py:43` | Нормализованная схема и ограничения есть; обоснование 3НФ отдельным текстом явно не оформлено | Добавить короткое обоснование 3НФ в docs |
| 7 | Корректная обработка невалидных входных данных | PASS | `app/main.py:54`, `app/schemas/auth.py:6`, `app/schemas/wallet.py:15`, `app/schemas/purchases.py:8`, `tests/api/test_auth_endpoints.py:39`, `tests/api/test_wallet_endpoints.py:85`, `tests/api/test_items_endpoints.py:29` | Существенных расхождений не обнаружено | Поддерживать единый формат ошибок |
| 8 | Аутентификация, авторизация, защита от SQL-инъекций | PARTIAL | `app/core/security.py:35`, `app/core/security.py:103`, `app/core/deps.py:16`, `app/core/deps.py:42`, `app/routers/admin_items.py:18`, `app/db/repositories/purchases.py:145` | JWT/roles реализованы, но SQL-инъекции в реальном data-access слое не демонстрируются, т.к. runtime-репозитории in-memory | Перевести data-access на SQLAlchemy ORM/parameterized queries и покрыть тестами |
| 9 | Разворачивание через Docker Compose | PASS | `docker-compose.yml:3`, `docker-compose.yml:19`, `docker-compose.yml:37`, `Dockerfile:1`, `README.md:28` | Существенных расхождений не обнаружено | Добавить smoke-check после старта (health + migrate) |
| 10 | README: описание, запуск, миграции, тесты, примеры запросов | PASS | `README.md:1`, `README.md:18`, `README.md:28`, `README.md:47`, `README.md:61`, `README.md:81` | Существенных расхождений не обнаружено | Поддерживать актуальность команд |
| 11 | Нет явных следов ИИ-генерации в коде/доках | UNKNOWN | Не подтверждено по файлам однозначным критерием | Формального, проверяемого критерия «AI trace» в репозитории нет | Провести ручной ревью редактором/преподавателем |

## Предварительный балл (0–10)

- backend реализация: **2.4 / 4.0**
- тесты: **1.0 / 2.0**
- модель данных / 3НФ: **0.9 / 1.0**
- обработка невалидных данных: **0.9 / 1.0**

Субтотал: **5.2 / 8.0**

Предварительный балл (нормализованно к 10): **6.5 / 10**

Потенциал `+1..2` за творческий подход:
- Хорошая глубина бизнес-правил (идемпотентность, rollback, refund-window, Redis reserve/event), но для этого потенциала нужен переход на реальную БД и интеграционные тесты поверх PostgreSQL.

## Блокеры несдачи

1. Ключевая бизнес-логика не использует PostgreSQL/SQLAlchemy runtime (`app/db/repositories/store.py:116`, `app/db/repositories/purchases.py:16`, `app/db/repositories/refunds.py:14`).
2. Критерий тестов на БД/покрытие ~90% не подтвержден: основной тестовый контур работает с in-memory, а `db`-тесты фактически ограничены `SELECT 1` (`tests/db/test_test_database_fixture.py:24`).
3. SQL-injection защита в реальном слое доступа к БД не демонстрируется, потому что нет production-like DB repository слоя.

## Краткий вывод

**Статус: не готово к сдаче** (до закрытия P0-блокеров).

---

## Patch Plan (1–2 дня)

### День 1 (P0)

1. Перевести `auth/wallet/items/purchases/refunds/inventory/admin_items` репозитории на `AsyncSession` и SQLAlchemy ORM.
Ожидаемый результат: все CRUD/транзакции выполняются в PostgreSQL, не в `InMemoryStore`.
Проверка: `docker compose exec app pytest -q tests/api`.

2. Реализовать транзакции и блокировки в покупке/возврате на уровне БД (`SELECT ... FOR UPDATE`, уникальные ограничения идемпотентности, атомарные обновления баланса/остатков).
Ожидаемый результат: нет double-spend/double-refund при конкурентных запросах.
Проверка: добавить конкурентные тесты и запустить `docker compose exec app pytest -q tests/db`.

3. Привязать приложение к одному DB-модулю (убрать дублирование `app/core/db.py` и `app/db/session.py`).
Ожидаемый результат: единая точка подключения/DI для БД.
Проверка: `rg "create_async_engine\(|get_db_session" -n app`.

### День 2 (P0/P1)

4. Усилить тестовый контур БД: проверять реальные записи/транзакции/rollback в PostgreSQL после API-запросов.
Ожидаемый результат: tests подтверждают бизнес-логику на реальной БД.
Проверка: `docker compose exec app pytest -q -m db`.

5. Включить coverage-gate в CI/локальном пайплайне (`--cov-fail-under=90`) и зафиксировать факт достижения порога.
Ожидаемый результат: покрытие основного функционала >= 90% подтверждено.
Проверка: `docker compose exec app pytest --cov=app --cov-fail-under=90`.

6. Добавить lint-check (ruff/flake8) и точечные комментарии в критичных участках транзакций.
Ожидаемый результат: формально подтвержден PEP 8, повышена читаемость сложной логики.
Проверка: `ruff check app tests` (или `flake8 app tests`).
