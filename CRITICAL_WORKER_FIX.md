# 🚨 КРИТИЧЕСКАЯ ПРОБЛЕМА: Worker НЕ запускается

## Проблема:

Worker service на Railway запускает **WEB process** (gunicorn) вместо **WORKER process** (mercari_notifications.py).

**Доказательство из логов:**
```
Starting Railway service: Worker
Starting web process...    # ❌ НЕПРАВИЛЬНО! Должно быть "Starting worker process..."
[INFO] Starting gunicorn 23.0.0
```

## Причина:

`start.sh` проверяет `$RAILWAY_SERVICE_NAME`, но Railway возвращает "Worker" (с заглавной), а скрипт сравнивает с "worker" (lowercase).

Мы исправили start.sh добавив `tr '[:upper:]' '[:lower:]'`, но Railway **НЕ ВИДИТ** новый код даже после `railway up`.

## Решение (НУЖНО СДЕЛАТЬ ВРУЧНУЮ):

### Вариант 1: Изменить Start Command в Railway Dashboard (РЕКОМЕНДУЕТСЯ)

1. Открой: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
2. Найди service "Worker"
3. Открой **Settings** → **Deploy**
4. В поле **"Start Command"** укажи:
   ```bash
   python mercari_notifications.py worker
   ```
5. Сохрани и нажми **"Redeploy"**

### Вариант 2: Установить Environment Variable

1. Открой Worker service → **Variables**
2. Добавь переменную:
   ```
   SERVICE_NAME=worker
   ```
3. Redeploy service

### Вариант 3: Переименовать Service

1. Переименуй service с "Worker" на "worker" (lowercase)
2. Redeploy

## Как проверить что заработало:

### 1. Проверь логи Worker:
```
Starting Railway service: Worker (checking as: worker)
Starting worker process...    # ✅ ПРАВИЛЬНО!
```

Должен быть:
```
python mercari_notifications.py worker
[STARTUP] MercariSearcher Worker starting...
```

НЕ должно быть:
```
gunicorn
wsgi
```

### 2. Проверь БД:
```sql
SELECT COUNT(*) as total, COUNT(image_data) as with_images FROM items;
```

Через 1-2 минуты должны появиться новые items с `with_images > 0`.

### 3. Проверь что фото скачиваются:

В логах Worker должно быть:
```
📥 Downloading image: https://static.mercdn.net/...
✅ Image saved (245.3KB base64)
```

### 4. Проверь Web UI:

https://web-production-fe38.up.railway.app/

Новые items должны показывать фото (не 403).

## Current Status:

- ❌ Worker запускает web process (gunicorn)
- ❌ Фото НЕ скачиваются (всего 2 из 102 items)
- ❌ Worker НЕ сканирует новые items
- ✅ Telegram отправка работает (unsent items уменьшаются)
- ✅ Web service работает
- ✅ БД миграция выполнена

## Files:

- `start.sh` - исправлен (commit 8a05241)
- `core.py` - код скачивания фото есть (lines 386-396)
- `image_utils.py` - функция download_and_encode_image есть
- `web_ui_plugin/app.py` - endpoint /api/image исправлен (commit 26e15ca)

## Next Steps:

1. **ВРУЧНУЮ изменить Start Command в Railway Dashboard**
2. Redeploy Worker service
3. Подождать 1-2 минуты
4. Проверить логи
5. Проверить БД на новые items с фото
6. Проверить Web UI

---

**Last Updated:** 2025-11-19 11:28 UTC
**Commits:** 8a05241 (start.sh fix), 26e15ca (endpoint fix)
**Status:** ⚠️ BLOCKING - Worker не запускается правильно
