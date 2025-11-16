# ✅ СЕРВИС СОЗДАН! Завершите настройку (1 минута)

## 🎉 Что уже сделано автоматически:

✅ **GitHub репозиторий подключен**: 2extndd/MRS
✅ **Сервис создан в Railway**
✅ **Service ID**: c5a6f7bc-b1d4-49be-9b40-6ce69efae43a

---

## ⚡ Осталось сделать (1 минута):

### 1. Откройте созданный сервис:
**Прямая ссылка**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/c5a6f7bc-b1d4-49be-9b40-6ce69efae43a

### 2. Переименуйте сервис в "web"
- Settings → Service Name → `web`

### 3. Установите Start Command:
- Settings → Deploy → Start Command:
```bash
gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
```

### 4. Добавьте переменные окружения:
- Settings → Variables → Raw Editor → Вставьте:

```env
TELEGRAM_BOT_TOKEN=8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw
TELEGRAM_CHAT_ID=-4997297083
DISPLAY_CURRENCY=USD
USD_CONVERSION_RATE=0.0067
SEARCH_INTERVAL=300
MAX_ITEMS_PER_SEARCH=50
REQUEST_DELAY_MIN=1.5
REQUEST_DELAY_MAX=3.5
LOG_LEVEL=INFO
```

### 5. Включите публичный домен:
- Settings → Networking → Generate Domain

### 6. Добавьте PostgreSQL:
- Вернитесь в проект: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- Нажмите "+ New" → Database → PostgreSQL

### 7. Создайте WORKER сервис:
- "+ New" → Empty Service → Назовите `worker`
- Settings → Source → Connect Repo → `2extndd/MRS`
- Start Command: `python mercari_notifications.py worker`
- Variables → Вставьте ТЕ ЖЕ переменные (см. шаг 4)

---

## ✅ Проверка после развертывания:

### WEB сервис логи:
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:3000
```

### WORKER сервис логи:
```
[INFO] MercariSearcher v1.0.0 Worker Starting...
[INFO] Database: PostgreSQL connected
[INFO] Telegram: Bot connected
[INFO] Scheduler: Started (interval: 300s)
```

---

## 🚀 Первый тест:

1. Откройте публичный URL web сервиса
2. Перейдите на `/queries`
3. Добавьте поиск:
   - Name: `Julius Denim`
   - URL: `https://jp.mercari.com/search?keyword=julius&category_id=3088`
   - Chat ID: `-4997297083`
   - Active: ✓

4. Через 5 минут проверьте Telegram чат `-4997297083`

---

## 📍 Быстрые ссылки:

- **Созданный сервис**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/c5a6f7bc-b1d4-49be-9b40-6ce69efae43a
- **Проект**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **GitHub**: https://github.com/2extndd/MRS

---

**✅ Сервис уже создан! Осталось только добавить переменные и настроить команду запуска!**
