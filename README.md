## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
uvicorn main:app --reload
```

## Эндпоинт

`POST /calculate/`

Тело запроса:

```json
{
  "numbers": [5, 3, 10], 
  "delays": [1, 2, 0.5]
}
```
