# Alembic план миграций для модели внутриигровых покупок

## 1) Порядок миграций (ревизии/файлы)

Фактически в репозитории:

1. `0001_initial_schema.py`
2. `0002_seed_roles_items.py`

Рекомендуемый порядок при новом старте (если разбивать по шагам):

1. `0001_core_types_and_roles_users.py`
2. `0002_wallets_and_items.py`
3. `0003_purchases_inventory_topups_refunds.py`
4. `0004_audit_and_indexes.py`
5. `0005_db_functions_and_triggers.py`
6. `0006_seed_roles_items.py`

## 2) Что создается в каждой миграции

### `0001_core_types_and_roles_users.py`
- PostgreSQL extension: `pgcrypto`.
- ENUM-типы: `user_status`, `purchase_status`, `topup_status`, `refund_status`.
- Таблицы: `roles`, `users`.
- Ограничения: email/username/password checks.
- Индексы: `uq_users_email_ci`, `idx_users_role_id`.

### `0002_wallets_and_items.py`
- Таблицы: `wallets`, `items`.
- Ограничения: неотрицательный баланс, корректный `currency_code`, цена/остаток.
- Индекс: `idx_items_active_price` (partial index).

### `0003_purchases_inventory_topups_refunds.py`
- Таблицы: `purchases`, `inventory`, `topups`, `refunds`.
- Ключевые FK/unique/check для покупок, пополнений, возвратов.
- Индексы для истории и фильтрации по статусам/пользователю/кошельку.

### `0004_audit_and_indexes.py`
- Таблица `audit_log`.
- Индексы: `idx_audit_entity_created_at_desc`, `idx_audit_actor_created_at_desc`.

### `0005_db_functions_and_triggers.py`
- Функция `fn_set_updated_at` + триггеры для `users`, `wallets`, `items`, `purchases`, `inventory`.
- Функция `fn_validate_refund` + триггер `trg_refunds_validate`.

### `0006_seed_roles_items.py`
- Seed ролей: `admin`, `player`.
- Seed товаров: 2 стартовые позиции.
- Идемпотентность через `ON CONFLICT`.

## 3) Команды для генерации и применения миграций

Создать ревизию вручную:

```bash
alembic revision -m "add purchases table"
```

Создать ревизию автогенерацией (когда модель обновлена):

```bash
alembic revision --autogenerate -m "sync models"
```

Применить все миграции:

```bash
alembic upgrade head
```

Откат на одну ревизию:

```bash
alembic downgrade -1
```

Откат к базе:

```bash
alembic downgrade base
```

Проверить цепочку:

```bash
alembic history
alembic heads
alembic current
```

## 4) Как избежать ошибок на чистой БД и при повторных прогонах

1. Не смешивать seed и schema-изменения в одном файле.
2. В seed использовать `ON CONFLICT DO UPDATE` по стабильным unique-полям (`roles.code`, `items.sku`).
3. В `downgrade` удалять только данные seed по детерминированным ключам.
4. Для зависимых объектов соблюдать порядок `drop`: триггеры -> функции -> индексы -> таблицы -> enum.
5. Не использовать в seed hardcoded id (`role_id=1`), только natural keys (`code`, `sku`).
6. Перед merge проверять миграции на чистой БД:
   - `alembic upgrade head`
   - `alembic downgrade base`
   - `alembic upgrade head`
7. Следить за одним `head` в ветке (`alembic heads`). При нескольких head сделать merge-revision.
8. Для PostgreSQL-specific операций (partial index, enum, extension) писать явный SQL/DSL, не полагаться только на autogenerate.

## 5) Начальный seed (минимум)

- Роли:
  - `admin`
  - `player`
- Товары:
  - `starter_skin_red` (`199.00`)
  - `booster_x2_24h` (`299.00`)

Реализовано в:

- `alembic/versions/0002_seed_roles_items.py`

## 6) Шаблоны migration-файлов

Готовые каркасы:

- `alembic/templates/template_schema_revision.py`
- `alembic/templates/template_seed_revision.py`

Использование:

1. Создать новую ревизию командой `alembic revision -m "..."`.
2. Скопировать тело из нужного шаблона в новый файл из `alembic/versions/`.
3. Заполнить `revision/down_revision` и реализовать `upgrade/downgrade`.
