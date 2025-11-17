# FIX: PostgreSQL Authentication Failed

## ПРОБЛЕМА

```
[DB ERROR] Failed to connect: password authentication failed for user "postgres"
```

DATABASE_URL в переменных окружения указывает на **УДАЛЕННУЮ** базу данных!
Поэтому:
- ❌ Web service падает на PostgreSQL
- ❌ Fallback на in-memory SQLite
- ❌ Queries пропадают после перезагрузки

## РЕШЕНИЕ

### Шаг 1: Добавить НОВУЮ базу данных через Railway Dashboard

1. Открой: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
2. Нажми "+ New" → "Database" → "Add PostgreSQL"
3. Railway автоматически создаст новую базу данных

### Шаг 2: Подключить DATABASE_URL к сервисам

Railway **АВТОМАТИЧЕСКИ** создаст переменную `DATABASE_URL` для новой базы данных!

Нужно только:
1. Перейти в настройки сервиса **web**
2. Variables → Add Reference → выбрать новую базу данных → `DATABASE_URL`
3. Повторить для сервиса **worker**

### Шаг 3: Redeploy оба сервиса

После обновления DATABASE_URL, Railway автоматически передеплоит сервисы.

Или вручную:
```bash
railway service web && railway up
railway service worker && railway up
```

### Шаг 4: Проверить подключение

Логи должны показать:
```
[DB] Connected to PostgreSQL
```

Вместо:
```
[DB ERROR] Failed to connect: password authentication failed
[DB] Using in-memory SQLite as fallback
```

## После фикса

1. Web service подключится к PostgreSQL ✅
2. Worker service подключится к PostgreSQL ✅
3. Queries будут сохраняться в базе данных ✅
4. Queries будут персистить после перезагрузки ✅

## Альтернативный метод (CLI)

Если есть доступ к Railway CLI с интерактивным режимом:

```bash
# Добавить PostgreSQL
railway add --database postgresql

# Обновить переменные
railway service web
railway variables --set DATABASE_URL=$(railway variables --service postgresql | grep DATABASE_URL)

railway service worker
railway variables --set DATABASE_URL=$(railway variables --service postgresql | grep DATABASE_URL)

# Redeploy
railway up
```

Но в твоем случае проще через Dashboard!
