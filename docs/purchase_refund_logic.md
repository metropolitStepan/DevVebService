# Покупка и возврат: бизнес-логика

## Сигнатуры сервисных методов

```python
# app/services/purchase_service.py
async def buy(*, user_id: int, item_id: int, quantity: int, idempotency_key: str) -> PurchaseResponse
async def history(*, user_id: int, limit: int, offset: int) -> PurchaseListResponse
async def get_by_id(*, actor_user_id: int, actor_role: str, purchase_id: int) -> PurchaseResponse

# app/services/refund_service.py
async def request_refund(
    *,
    actor_user_id: int,
    actor_role: str,
    purchase_id: int,
    reason: str,
) -> RefundResponse
```

## Критические участки транзакций

### Покупка (атомарно)

```python
# app/db/repositories/purchases.py::create_purchase
with self.store.transaction():
    # idempotency check: key -> payload hash -> cached result or conflict
    # 1) товар существует и активен
    # 2) stock >= quantity (если stock ограничен)
    # 3) кошелек существует
    # 4) balance >= total
    # 5) списание средств
    # 6) запись purchase
    # 7) запись wallet transaction (purchase_debit)
    # 8) выдача в inventory
    # 9) фиксация idempotency как completed
```

### Возврат (атомарно)

```python
# app/db/repositories/refunds.py::request_refund
with self.store.transaction():
    # 1) покупка существует
    # 2) доступ: владелец или admin
    # 3) статус покупки == completed
    # 4) возврат еще не создан
    # 5) окно возврата не истекло (или admin bypass)
    # 6) условие inventory выполнено
    # 7) зачисление средств
    # 8) запись refund
    # 9) запись wallet transaction (refund_credit)
    # 10) изменение purchase.status -> refunded
```

## Таблица бизнес-правил

| Код правила | Описание | Ошибка |
|---|---|---|
| `ITEM_ACTIVE_REQUIRED` | Покупать можно только активный товар | `ITEM_NOT_ACTIVE` (400) |
| `BALANCE_REQUIRED` | Баланс кошелька должен покрывать `price * quantity` | `INSUFFICIENT_FUNDS` (400) |
| `STOCK_REQUIRED` | При ограниченном stock должно хватать количества | `ITEM_OUT_OF_STOCK` (409) |
| `IDEMPOTENCY_SAME_PAYLOAD` | Повтор с тем же `Idempotency-Key` и тем же payload возвращает прежний purchase | 201 + тот же purchase |
| `IDEMPOTENCY_NO_PAYLOAD_CHANGE` | Тот же `Idempotency-Key` с другим payload запрещен | `IDEMPOTENCY_CONFLICT` (409) |
| `REFUND_ONLY_COMPLETED` | Возврат только для `purchase.status=completed` | `REFUND_NOT_ALLOWED` (400) |
| `REFUND_SINGLE` | На одну покупку только один возврат | `REFUND_ALREADY_EXISTS` (409) |
| `REFUND_WINDOW` | Возврат только в `N` минут (настраивается), admin может обходить по флагу | `REFUND_WINDOW_EXPIRED` (400) |
| `REFUND_INVENTORY_CONDITION` | Если включено, у пользователя должен быть достаточный остаток товара в inventory | `REFUND_INVENTORY_CONDITION_FAILED` (409) |

## Настройки правил

- `REFUND_WINDOW_MINUTES` (по умолчанию `120`)
- `ALLOW_ADMIN_REFUND_AFTER_WINDOW` (по умолчанию `true`)
- `REQUIRE_INVENTORY_FOR_REFUND` (по умолчанию `true`)
