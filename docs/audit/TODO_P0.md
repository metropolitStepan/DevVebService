# TODO P0 (Критичные блокеры)

- [ ] Перевести runtime-репозитории с `InMemoryStore` на PostgreSQL/SQLAlchemy
Почему это критично:
Проект по ТЗ должен работать на PostgreSQL + SQLAlchemy, а сейчас ключевая бизнес-логика покупок/возвратов живет в in-memory и не подтверждает корректность работы с БД.
Что изменить (конкретные файлы):
`app/db/repositories/store.py`, `app/db/repositories/auth.py`, `app/db/repositories/wallet.py`, `app/db/repositories/items.py`, `app/db/repositories/purchases.py`, `app/db/repositories/inventory.py`, `app/db/repositories/refunds.py`, `app/db/repositories/admin_items.py`, `app/services/*.py`, `app/core/deps.py`.
Критерий приемки (Definition of Done):
После перезапуска приложения данные сохраняются в PostgreSQL; API-тесты проходят без использования `STORE`; в репозиториях используются `AsyncSession`/ORM-запросы.

- [ ] Реализовать атомарные транзакции покупки/возврата на уровне БД
Почему это критично:
Без DB-level транзакций и блокировок есть риск гонок и неконсистентного баланса/остатков при параллельных запросах.
Что изменить (конкретные файлы):
`app/db/repositories/purchases.py`, `app/db/repositories/refunds.py`, при необходимости `alembic/versions/0001_initial_schema.py` или новая миграция для дополнительных ограничений/индексов.
Критерий приемки (Definition of Done):
Покупка/возврат выполняются в одной транзакции БД; конкурентные сценарии проходят (нет двойного списания/двойного возврата), тесты это подтверждают.

- [ ] Переписать функциональные DB-тесты на реальные проверки бизнес-логики в PostgreSQL
Почему это критично:
Критерий оценки требует тесты не только happy-path, но и БД-аспекты; сейчас `db`-контур фактически проверяет только `SELECT 1`.
Что изменить (конкретные файлы):
`tests/conftest.py`, `tests/db/test_test_database_fixture.py`, `tests/db/test_rollback_and_integrity.py`, добавить новые интеграционные тесты в `tests/api/`.
Критерий приемки (Definition of Done):
Тесты проверяют реальные записи в таблицах `wallets/purchases/inventory/refunds` после API-запросов и rollback-поведение на PostgreSQL.

- [ ] Зафиксировать и выполнить coverage-gate >= 90% по основному функционалу
Почему это критично:
Требование по покрытию (~90%) должно быть подтверждено измеримым результатом, иначе критерий формально не закрыт.
Что изменить (конкретные файлы):
`requirements.txt`, `pytest.ini`, при наличии CI-конфига — добавить `--cov-fail-under=90`; при необходимости расширить `tests/api/` и `tests/db/`.
Критерий приемки (Definition of Done):
Команда `pytest --cov=app --cov-fail-under=90` проходит стабильно в локальном и контейнерном окружении.
