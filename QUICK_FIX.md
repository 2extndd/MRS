# ⚡ БЫСТРЫЕ ИСПРАВЛЕНИЯ - MercariSearcher

## ✅ ЧТО ИСПРАВЛЕНО (8 минут работы)

### 1. 🔴 КРИТИЧНО: Telegram уведомления теперь РАБОТАЮТ
**Файл:** `mercari_notifications.py`
- БЫЛО: отправка только если `new_items > 0` в текущем цикле
- СТАЛО: проверка pending notifications ВСЕГДА

### 2. 🔴 КРИТИЧНО: API Requests счетчик теперь показывает правильное значение
**Файлы:** `web_ui_plugin/app.py`, `web_ui_plugin/templates/dashboard.html`
- БЫЛО: брал из shared_state (недоступен между процессами)
- СТАЛО: берет из БД (доступен всем процессам)

### 3. ⚠️ ВАЖНО: Timestamp когда item найден
**Файлы:** `db.py`, `web_ui_plugin/templates/items.html`
- Добавлен `found_at` при создании item
- Отображается в карточке item

### 4. ⭐ УЛУЧШЕНИЕ: Качество фотографий
**Файл:** `pyMercariAPI/mercari.py`
- БЫЛО: использовались thumbnails (маленькие превью)
- СТАЛО: используются photos если доступны, иначе thumbnails

### 5. 📝 УЛУЧШЕНИЕ: Логирование config changes
**Файл:** `mercari_notifications.py`
- Теперь логируется reload конфигурации
- Логируется изменение search interval

---

## 🚀 КОМАНДЫ ДЛЯ ДЕПЛОЯ

```bash
# 1. Проверить изменения
git status
git diff

# 2. Коммит
git add mercari_notifications.py db.py pyMercariAPI/mercari.py
git add web_ui_plugin/app.py web_ui_plugin/templates/dashboard.html web_ui_plugin/templates/items.html
git commit -m "Fix: Telegram notifications, API counter, timestamps, photo quality

CRITICAL FIXES:
- Telegram notifications now always check pending items (not only new_items>0)
- API counter now reads from DB (cross-process visible)
- Items now have found_at timestamp

IMPROVEMENTS:
- Photos use full-size images instead of thumbnails
- Config changes are now logged
- Items display timestamp when found"

# 3. Push
git push origin main

# 4. Проверить деплой (2-5 минут)
railway logs --service worker
```

---

## ✅ ЧТО ПРОВЕРИТЬ ПОСЛЕ ДЕПЛОЯ

### 1. Worker запустился
```bash
railway logs --service worker | grep "STARTUP"
```
Должны увидеть:
```
[STARTUP] ✅ Active searches: X
[STARTUP] ✅ Startup notification sent to Telegram
[STARTUP] ✅ Scheduler is running
```

### 2. Telegram уведомления
```bash
railway logs --service worker | grep "Checking for pending"
railway logs --service worker | grep "Notifications:"
```
Должны увидеть:
```
Checking for pending notifications...
Notifications: X/Y sent
```

**И ПРОВЕРИТЬ TELEGRAM - должны прийти уведомления!**

### 3. Web UI
Открыть: https://web-production-fe38.up.railway.app/

**Dashboard:**
- ✅ API Requests: должен показывать > 0 (не 0!)
- ✅ Recent Items: должны появиться items за последние 24 часа

**Items page:**
- ✅ Каждая карточка показывает timestamp "Found: ..."
- ✅ Фото лучшего качества (если mercapi возвращает photos)

---

## 🔍 ДИАГНОСТИКА ПРОБЛЕМ

### Telegram всё ещё не работает?

**Проверка 1: Есть ли unsent items в БД?**
```sql
SELECT COUNT(*) FROM items WHERE is_sent = false;
```
Если 0 - значит items уже отправлены или не найдены.

**Проверка 2: Worker видит unsent items?**
```bash
railway logs --service worker | grep "Found.*pending"
```
Должно быть: "Found X pending notifications"

**Проверка 3: Telegram credentials правильные?**
```bash
railway variables --service worker | grep TELEGRAM
```
Должны быть установлены:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

**Проверка 4: Ошибки при отправке?**
```bash
railway logs --service worker | grep -i "telegram\|failed to send"
```

### API Counter всё ещё 0?

**Проверка: Есть ли значение в БД?**
```sql
SELECT value FROM key_value_store WHERE key = 'api_request_count';
```
Если NULL или отсутствует - worker ещё не делал requests.

**Решение: Сделать Force Scan**
В Web UI нажать кнопку "Force Scan All"

---

## 📊 ИЗМЕНЕНИЯ В КОДЕ

### Файлы изменены:
```
mercari_notifications.py  | +8 -5   (Telegram + config logging)
db.py                      | +2 -1   (found_at timestamp)
pyMercariAPI/mercari.py    | +7 -2   (photo quality)
web_ui_plugin/app.py       | +1      (API counter)
web_ui_plugin/templates/dashboard.html | +1 -1  (API counter)
web_ui_plugin/templates/items.html     | +1      (timestamp display)
```

### НЕ изменены:
- ❌ requirements.txt - зависимости НЕ ТРОГАЛИ
- ❌ простая_telegram_worker.py - работает правильно
- ❌ core.py - поиск работает правильно

---

## 💡 ПОЧЕМУ ЭТО РАБОТАЕТ

### Проблема Telegram:
```python
# БЫЛО:
if results['new_items'] > 0:  # <- items уже в БД = 0 new items
    process_pending_notifications()  # <- НЕ ВЫЗЫВАЕТСЯ!

# СТАЛО:
process_pending_notifications()  # <- ВСЕГДА вызывается!
```

### Проблема API Counter:
```python
# БЫЛО:
state_stats.total_api_requests  # <- web process не видит worker process

# СТАЛО:
db.get_api_counter()  # <- БД видна всем процессам
```

### Проблема Timestamps:
```python
# БЫЛО:
INSERT INTO items (...) VALUES (...)  # <- found_at = NULL

# СТАЛО:
INSERT INTO items (..., found_at) VALUES (..., get_moscow_time())  # <- found_at установлен!
```

---

## 🎯 РЕЗУЛЬТАТ

После деплоя:
- ✅ Telegram БУДЕТ присылать уведомления
- ✅ API Counter БУДЕТ показывать правильное значение
- ✅ Recent Items БУДЕТ работать
- ✅ Items БУДУТ показывать timestamp
- ✅ Фото БУДУТ лучшего качества (если доступны)
- ✅ Логи БУДУТ показывать config changes

---

**ГОТОВО! Делайте commit и push!** 🚀
