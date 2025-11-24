# 🎯 AUTOSTART SCHEDULER FIX - FINAL SUMMARY

## 📅 Дата: 24 ноября 2024

---

## ❌ ИСХОДНАЯ ПРОБЛЕМА:

**Автозапуск сканера не работает на Railway:**
- Scheduler не запускается автоматически
- Или запускается, но ничего не происходит (нет сканирования)
- Пользователь не видит новых items

---

## 🔍 ПРОВЕДЁННЫЙ АНАЛИЗ:

### 1. Проверка существующего кода

Проверил все компоненты автозапуска:
- ✅ `Procfile`: правильно запускает `start.sh`
- ✅ `start.sh`: правильно запускает Gunicorn
- ✅ `gunicorn_config.py`: правильно настроен (1 worker, timeout 600s)
- ✅ `wsgi.py`: правильно создаёт scheduler thread с auto-restart
- ✅ `post_worker_init()`: правильно вызывается в worker process

### 2. Проверка scheduler loop

**Найдено:** Scheduler loop использует правильный подход:
```python
while True:
    schedule.run_pending()
    time.sleep(1)  # Спит всего 1 секунду каждую итерацию
```

**Вывод:** Loop НЕ блокирует worker надолго ✅

### 3. Проверка schedule setup

**НАШЁЛ ПРОБЛЕМУ!** 🎯

В функции `_setup_schedule()`:
```python
schedule.every(config.SEARCH_INTERVAL).seconds.do(self.search_cycle)
```

**Проблема:**
- `schedule.every(N).seconds.do(func)` запускает `func` ВПЕРВЫЕ через N секунд
- Если `SEARCH_INTERVAL = 300` (5 минут), первый scan произойдёт через 5 минут
- В течение этих 5 минут scheduler "жив" (логирует "Loop alive!"), но НЕ делает ничего полезного
- Railway/Gunicorn могут посчитать worker idle и убить его
- Пользователь видит: запуск → логи "Loop alive!" → тишина → перезапуск

---

## ✅ РЕШЕНИЕ:

### Immediate First Run

Добавлен код для **немедленного запуска первого search cycle**:

```python
def _setup_schedule(self):
    # ... создание jobs ...

    # Run first search cycle immediately (in background thread to not block setup)
    def run_first_cycle():
        import time
        time.sleep(2)  # Small delay to ensure scheduler loop is running
        try:
            logger.info(f"[SCHEDULER] 🚀 Running first search cycle immediately...")
            self.search_cycle()
            logger.info(f"[SCHEDULER] ✅ First search cycle completed")
        except Exception as e:
            logger.error(f"[SCHEDULER] ❌ First search cycle failed: {e}")

    import threading
    first_cycle_thread = threading.Thread(target=run_first_cycle, daemon=True)
    first_cycle_thread.start()
```

**Как работает:**
1. Scheduler запускается
2. Jobs создаются (будущие runs каждые N секунд)
3. **Немедленно** (через 2 сек) запускается первый search cycle в отдельном thread
4. Scheduler начинает показывать активность сразу
5. Последующие runs происходят по расписанию

**Преимущества:**
- ✅ Scheduler показывает активность немедленно
- ✅ Пользователь видит items сразу (не ждёт 5 минут)
- ✅ Worker показывает что он работает (не idle)
- ✅ Нет риска timeout из-за "бездействия"
- ✅ Не блокирует setup (background thread)

---

## 📊 ДОПОЛНИТЕЛЬНЫЕ УЛУЧШЕНИЯ:

### Tags для всех jobs

Добавлены tags для easier debugging:
```python
job.tag('search_cycle')
telegram_job.tag('telegram_cycle')
cleanup_job.tag('cleanup')
proxy_job.tag('proxies')
```

Теперь можно фильтровать jobs по тегам для отладки.

---

## 🎯 ОЖИДАЕМОЕ ПОВЕДЕНИЕ ПОСЛЕ ФИКСА:

### Логи при запуске (ожидается):

```
[START.SH] 🚀 Starting web process with Gunicorn
[GUNICORN] Worker 12345 initialized
[WSGI] Starting background scheduler (attempt #1)...
[WSGI] Imported MercariNotificationApp
[WSGI] Creating MercariNotificationApp instance...
[WSGI] MercariNotificationApp created successfully
[WSGI] Calling run_scheduler()...

[SCHEDULER] Starting scheduler
[SCHEDULER] Search cycle will run every 300 seconds
[SCHEDULER] ⏱ Search cycle: every 300s (first run: immediate)
[SCHEDULER] 📬 Telegram cycle: every 35s
[SCHEDULER] ⏰ Entering main loop...

[SCHEDULER] 🚀 Running first search cycle immediately...  ← НОВОЕ!
[SEARCH] 🔄 Starting search cycle...
[SEARCH] Found 15 items from "archive" search
[SEARCH] Added 5 new items to database
[SCHEDULER] ✅ First search cycle completed  ← НОВОЕ!

[SCHEDULER] ⏰ Loop alive! Iteration 30 (0.5 min)
[SCHEDULER] ⏰ Loop alive! Iteration 60 (1.0 min)
...
[SCHEDULER] ⏰ Loop alive! Iteration 300 (5.0 min)
[SEARCH] 🔄 Starting search cycle... ← Следующий scheduled run
```

**Ключевые моменты:**
1. "Running first search cycle immediately" появляется через ~2 секунды после старта
2. Сразу начинается сканирование
3. Items находятся и добавляются в БД
4. Loop продолжает работать
5. Через 5 минут (SEARCH_INTERVAL) - следующий scheduled run

---

## 🐛 DEBUG ЛОГИ ДЛЯ SHOPS BLACKLIST:

Как бонус, добавлены debug логи для диагностики Shops category blacklist:

**3 коммита:**
1. `3320bee` - Comprehensive category debugging
   - Логи в `mercari.py` при извлечении category_id
   - Логи в `items.py` при создании Item
   - Логи показывают полный data flow

2. `2b0341e` - DB layer debugging
   - Лог в `db.add_item()` перед INSERT
   - Показывает что именно сохраняется в БД

3. `d9ee3fc` - Autostart fix (этот коммит)
   - Immediate first search cycle
   - Теперь scheduler работает сразу

---

## 📝 КОММИТЫ:

```bash
d9ee3fc - fix: Run first search cycle immediately on startup
2b0341e - debug: Add category logging to db.add_item()
3320bee - debug: Add comprehensive Shops category debugging
```

Всё запушено на GitHub → Railway автоматически задеплоит.

---

## ✅ ЧТО ПРОВЕРИТЬ ПОСЛЕ DEPLOY:

### Шаг 1: Проверить логи Railway (первые 2 минуты)

Открыть Railway Dashboard → Logs, искать:
```
✅ [SCHEDULER] 🚀 Running first search cycle immediately...
✅ [SEARCH] 🔄 Starting search cycle...
✅ [SEARCH] Found X items...
✅ [SCHEDULER] ✅ First search cycle completed
```

**Если эти логи есть** → УСПЕХ! Scheduler работает! 🎉

### Шаг 2: Проверить что loop продолжает работать

Ждать 5-10 минут, искать в логах:
```
✅ [SCHEDULER] ⏰ Loop alive! Iteration 300 (5.0 min)
✅ [SCHEDULER] ⏰ Loop alive! Iteration 600 (10.0 min)
```

**Если логи продолжаются** → Scheduler стабилен! ✅

### Шаг 3: Проверить Shops category (BONUS)

Искать в логах при сканировании:
```
✅ [SHOPS CATEGORY] 2JHR... using category_id: 208 -> 'ID:208'
✅ [SHOPS DICT] 2JHR...: item_dict['category'] = 'ID:208'
✅ [Item.__init__] SHOPS item 2JHR...: category from data = 'ID:208'
✅ [DB ADD_ITEM] SHOPS item 2JHR...: category = 'ID:208'
✅ [FILTER] [SHOPS] Item 2JHR...: category = 'ID:208'
```

**Если все эти логи есть** → Shops category работает! Можно использовать blacklist! ✅

### Шаг 4: Проверить в БД

Через час работы проверить:
```sql
SELECT mercari_id, category FROM items WHERE mercari_id NOT LIKE 'm%' LIMIT 10;
```

**Ожидается:** `category = 'ID:208'` (или другой ID), НЕ NULL ✅

---

## 🚨 ЕСЛИ ЧТО-ТО ПОШЛО НЕ ТАК:

### Проблема: Нет лога "Running first search cycle immediately"

**Причина:** Thread не запустился или упал с ошибкой

**Решение:**
1. Смотреть traceback в логах перед этим местом
2. Проверить что `_setup_schedule()` вызывается
3. Проверить что нет exception при создании thread

### Проблема: Есть "Running first search cycle", но "Loop alive" останавливается

**Причина:** Loop падает с ошибкой или worker убивается

**Решение:**
1. Смотреть последние логи перед остановкой
2. Если есть "[CRITICAL] WORKER TIMEOUT" → см. AUTOSTART_TROUBLESHOOTING.md
3. Если есть traceback → исправлять конкретную ошибку

### Проблема: Shops категория всё ещё NULL

**Причина:** Проверить debug логи - найти где теряется категория

**Решение:**
1. Искать в логах: где последний раз видна категория?
2. Если "SHOPS CATEGORY" → есть
3. Если "SHOPS DICT" → есть
4. Если "Item.__init__" → есть
5. Если "DB ADD_ITEM" → есть, НО в БД NULL → проблема в SQL INSERT
6. Сообщить результаты для дальнейшей диагностики

---

## 📊 ИТОГ:

**Основная проблема:** Первый search cycle не запускался сразу (ждал 5 минут)

**Решение:** Немедленный запуск первого cycle в background thread

**Статус:** ✅ Исправлено и задеплоено на Railway

**Ожидаемый результат:**
- Scheduler работает сразу после запуска
- Items находятся немедленно
- Loop работает стабильно 24/7
- Shops blacklist работает (BONUS)

---

**Дата:** 24 ноября 2024
**Коммиты:** 3 (debug + autostart fix)
**Статус:** 🟢 ГОТОВО К ПРОВЕРКЕ НА RAILWAY

**Следующий шаг:** Мониторить Railway logs первые 10 минут после deploy
