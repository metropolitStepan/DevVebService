## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
uvicorn main:app --reload
```

## Эндпоинты авторизации

- `POST /auth/register` - регистрация пользователя.
- `POST /auth/login` - вход пользователя.
- `POST /auth/logout` - выход пользователя (требует заголовок `X-User-Id`).

Тело запроса для `/auth/register` и `/auth/login`:

```json
{
  "username": "student",
  "password": "strong123"
}
```

## Основной эндпоинт

`POST /calculate/` доступен только авторизованным пользователям.

Для доступа передайте заголовок `X-User-Id` со значением `user_id`, полученным после входа.

Тело запроса:

```json
{
  "numbers": [5, 3, 10],
  "delays": [1, 2, 0.5]
}
```
