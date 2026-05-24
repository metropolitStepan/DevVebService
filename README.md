## Установка

```bash
pip install -r requirements.txt
```

## Подготовка Redis

Для выполнения чек-листа по кешированию Redis должен быть запущен.

Пример через Docker:

```bash
docker run --name fastapi-redis -p 6379:6379 -d redis:7-alpine
```

По умолчанию приложение использует `redis://127.0.0.1:6379/0`.
При необходимости можно переопределить переменной `REDIS_URL`.

## Запуск

```bash
uvicorn main:app --reload
```

Документация Swagger: `http://127.0.0.1:8000/docs`

## Авторизация

- `POST /auth/register` - регистрация пользователя.
- `POST /auth/login` - вход пользователя.
- `POST /auth/logout` - выход пользователя.

Для всех защищенных эндпоинтов передавайте заголовок:

`X-User-Id: <user_id>`

## Эндпоинты `items` (БД + фоновые задачи)

- `POST /items/` - создать запись.
- `GET /items/` - получить список записей (кешируется в Redis).
- `GET /items/{item_id}` - получить запись по ID (кешируется в Redis).
- `PUT /items/{item_id}` - обновить запись.
- `DELETE /items/{item_id}` - удалить одну запись.
- `POST /items/import-csv` - фоновая загрузка данных из CSV.
- `POST /items/bulk-delete` - фоновое удаление записей по списку ID.
- `GET /items/tasks/{task_id}` - статус фоновой задачи.

### Формат CSV для импорта

Обязательные колонки: `name,category,price,quantity`

Пример:

```csv
name,category,price,quantity
Milk,Dairy,120.5,7
Bread,Bakery,65,12
```

Тело запроса на `POST /items/import-csv`:

```json
{
  "file_path": "/absolute/or/relative/path/to/items.csv"
}
```

Тело запроса на `POST /items/bulk-delete`:

```json
{
  "ids": [1, 2, 3]
}
```

## Эндпоинт вычислений

`POST /calculate/` доступен только авторизованным пользователям и кешируется в Redis.

Тело запроса:

```json
{
  "numbers": [5, 3, 10],
  "delays": [1, 2, 0.5]
}
```

## Переменные окружения

- `DATABASE_URL` (по умолчанию: `sqlite+aiosqlite:///./app.db`)
- `REDIS_URL` (по умолчанию: `redis://127.0.0.1:6379/0`)
- `CACHE_TTL_SECONDS` (по умолчанию: `120`)
