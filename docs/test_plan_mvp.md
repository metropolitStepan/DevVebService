# Тест-план MVP (pytest)

## 1) Структура `tests/`

```text
tests/
  conftest.py
  api/
    test_auth_endpoints.py
    test_wallet_endpoints.py
    test_items_endpoints.py
    test_purchases_endpoints.py
    test_inventory_endpoints.py
    test_refunds_endpoints.py
    test_admin_items_endpoints.py
  db/
    test_rollback_and_integrity.py
    test_test_database_fixture.py
```

## 2) Ключевые фикстуры

- `client` — единый `TestClient` с lifecycle FastAPI.
- `reset_store` — автосброс in-memory хранилища перед каждым тестом.
- `register_user` — фабрика регистрации пользователя.
- `auth_headers` — фабрика заголовков авторизации обычного пользователя.
- `admin_headers` — фабрика заголовков админа (роль меняется в тестовом store).
- `topup_balance` — helper для пополнения кошелька.
- `create_purchase` — helper для покупки.
- `test_database_url` — URL отдельной тестовой БД (`TEST_DATABASE_URL` или `*_test`).
- `db_engine` — асинхронный engine тестовой БД с `create_all/drop_all`.
- `db_session` — изолированная сессия для SQL-проверок.

## 3) Отдельная тестовая БД

- Тесты, требующие реальную БД, помечены `@pytest.mark.db`.
- Используется отдельный URL: `TEST_DATABASE_URL`.
- Если переменная не задана, URL выводится из `DATABASE_URL` с суффиксом `_test`.
- Если тестовая БД недоступна, `db`-тесты пропускаются (skip), основной API-набор не падает.

Пример:

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/game_store_test
```

## 4) Матрица покрываемых сценариев

`auth/register`
- Позитив: успешная регистрация.
- Позитив: нормализация email.
- Негатив: `422` невалидный payload.
- Негатив: `409` duplicate email.

`auth/login`
- Позитив: успешный логин.
- Позитив: email case-insensitive.
- Негатив: `401` invalid credentials.
- Негатив: `422` невалидный payload.

`auth/refresh`
- Позитив: выдача новой пары токенов.
- Позитив: новый access работает на `/auth/me`.
- Негатив: `401` invalid token.
- Негатив: `401` reuse refresh token.

`auth/me`
- Позитив: успешное получение профиля.
- Позитив: доступ после login.
- Негатив: `401` без токена.
- Негатив: `401` невалидный/неподдерживаемый `Authorization`.

`wallet/get balance`
- Позитив: нулевой баланс нового пользователя.
- Позитив: корректный баланс после topup.
- Негатив: `401` без токена.
- Негатив: `401` invalid token.

`wallet/topup`
- Позитив: успешное пополнение.
- Позитив: успешное пополнение с `external_ref`.
- Негатив: `422` amount/reason validation.
- Негатив: `409` duplicate `external_ref`.

`items/list`
- Позитив: возврат активных товаров.
- Позитив: `active_only=false` возвращает и неактивные.
- Негатив: `422` invalid `limit`.
- Негатив: `422` invalid `offset`.

`items/get`
- Позитив: товар #1 найден.
- Позитив: товар #2 найден.
- Негатив: `404` товар не найден.
- Негатив: `422` invalid path param.

`purchases/buy`
- Позитив: успешная покупка.
- Позитив: идемпотентный повтор возвращает ту же покупку.
- Негатив: `400` insufficient funds.
- Негатив: `400` item not active.

`purchases/history`
- Позитив: история пользователя корректна.
- Позитив: пагинация limit/offset.
- Негатив: `401` без токена.
- Негатив: `422` invalid query params.

`purchases/get by id`
- Позитив: владелец видит покупку.
- Позитив: admin видит чужую покупку.
- Негатив: `403` чужая покупка для player.
- Негатив: `404` покупка не найдена.

`inventory/list`
- Позитив: пустой inventory для нового пользователя.
- Позитив: inventory после покупки.
- Негатив: `401` без токена.
- Негатив: `401` invalid token.

`refunds/request`
- Позитив: успешный возврат владельцем.
- Позитив: admin делает возврат для другого пользователя.
- Негатив: `400` истекло окно возврата.
- Негатив: `403` возврат чужой покупки player-ом.

`admin items/create`
- Позитив: admin создает товар со stock.
- Позитив: admin создает товар без stock.
- Негатив: `403` player forbidden.
- Негатив: `409` duplicate SKU.

`admin items/update`
- Позитив: admin обновляет name/description.
- Позитив: admin обновляет price/stock.
- Негатив: `403` player forbidden.
- Негатив: `404` item not found.

`admin items/delete`
- Позитив: admin удаляет существующий товар.
- Позитив: admin удаляет созданный в тесте товар.
- Негатив: `403` player forbidden.
- Негатив: `404` item not found.

`admin items/toggle active`
- Позитив: admin деактивирует товар.
- Позитив: admin активирует товар.
- Негатив: `403` player forbidden.
- Негатив: `404` item not found.

## 5) Проверки целостности и rollback

`tests/db/test_rollback_and_integrity.py`:
- Корректность записей после покупки: баланс, inventory, purchase, wallet transaction.
- Корректность записей после возврата: refund record, статус покупки, обратная проводка.
- Rollback покупки при исключении внутри транзакции.
- Rollback возврата при исключении внутри транзакции.

## 6) Команды запуска

Все тесты:

```bash
pytest -q
```

Только API тесты:

```bash
pytest -q tests/api
```

Только rollback/целостность:

```bash
pytest -q tests/db/test_rollback_and_integrity.py
```

Тесты с реальной отдельной БД:

```bash
pytest -q -m db
```

## 7) Покрытие

Установка (если еще не установлено):

```bash
pip install pytest-cov
```

Запуск с покрытием:

```bash
pytest --cov=app --cov-report=term-missing --cov-report=xml
```

Порог покрытия (пример 90%):

```bash
pytest --cov=app --cov-fail-under=90
```
