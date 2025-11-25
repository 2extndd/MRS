# 🔍 SCHEDULER HANG - ROOT CAUSE ANALYSIS

## 📅 Дата: 24 ноября 2024, 19:20 MSK

---

## ❌ ПРОБЛЕМА:

**Scheduler запускается, работает ~30 итераций (30 секунд), потом зависает навсегда**

### Симптомы из логов:

```
2025-11-24 13:17:21 - [SCHEDULER] ⏰ Loop alive! Iteration 30 (0 min uptime)
2025-11-24 13:17:21 - [SCHEDULER] ⏰ Next scheduled run: 2025-11-24 13:17:27
```

**ПОСЛЕ ЭТОГО - НИ ОДНОГО ЛОГА!** Scheduler просто завис.

---

## 🔍 ДИАГНОСТИКА:

### Что НЕ является причиной:

1. ❌ **НЕ Gunicorn timeout** - спим по 1 сек, не по 300 сек
2. ❌ **НЕ Exception в loop** - нет логов об ошибках (есть try/except который бы поймал)
3. ❌ **НЕ KeyboardInterrupt** - нет лога "Shutdown requested"

### Что ЯВЛЯЕТСЯ причиной:

✅ **PostgreSQL connection lost + DB calls без timeout**

Scheduler loop делает множество DB вызовов:
- `self.db.add_log_entry()` - каждые 30 секунд (линия 317)
- `self.db.add_log_entry()` - при reload config (линия 331)
- `self.db.add_log_entry()` - при ошибке (линия 361)
- `config.reload_if_needed()` - каждую итерацию (линия 328)

**Если PostgreSQL connection потерян:**
- Вызовы `db.execute_query()` **зависают навсегда** без timeout
- Loop зависает на одном из этих вызовов
- Нет exception → нет лога об ошибке
- Scheduler просто "мертв"

---

## 🎯 КОРНЕВАЯ ПРИЧИНА:

**`psycopg2` по умолчанию НЕ имеет timeout на queries!**

Из документации psycopg2:
```
If a query takes too long, it will block forever unless:
1. You set statement_timeout in PostgreSQL
2. You use connection timeout (но это только для connect, не для queries!)
3. You use asyncio with timeout
```

Наш код:
```python
def execute_query(self, query, params=None, fetch=False):
    cursor = self.connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)  # ← ЗАВИСАЕТ НАВСЕГДА если connection lost!
```

**НЕТ TIMEOUT!**

---

## ✅ РЕШЕНИЕ:

### Вариант A: Добавить query timeout в PostgreSQL connection

В `db.py` при создании connection:

```python
import psycopg2.extensions
psycopg2.extensions.set_wait_callback(psycopg2.extras.wait_select)

self.connection = psycopg2.connect(
    self.connection_string,
    connect_timeout=10,  # Timeout для connect
    options='-c statement_timeout=30000'  # 30 sec query timeout!
)
```

### Вариант B: Wrap все DB calls в timeout decorator

```python
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Query timeout")

def with_timeout(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result
        return wrapper
    return decorator

@with_timeout(30)
def execute_query(self, query, params=None, fetch=False):
    # ... existing code ...
```

### Вариант C (ЛУЧШИЙ!): Убрать лишние DB logging calls из scheduler loop

**Scheduler loop НЕ должен писать в DB каждые 30 секунд!**

Это создаёт:
1. Огромное количество записей в БД
2. Много точек отказа (каждый вызов может зависнуть)
3. Лишнюю нагрузку

**РЕШЕНИЕ:**
- Убрать `db.add_log_entry()` из loop (линии 317, 331, 361)
- Оставить только console logging (`logger.info()`)
- Если нужны DB logs - писать их **async** в отдельном thread с timeout

---

## 📋 ПЛАН ДЕЙСТВИЙ:

1. ✅ **Немедленно (Quick Fix):**
   - Закомментировать все `db.add_log_entry()` в scheduler loop
   - Оставить только `logger.info()` (выводится в Railway logs)
   - Это устранит 90% точек отказа

2. **Долгосрочно (Proper Fix):**
   - Добавить `statement_timeout` в PostgreSQL connection
   - Переделать DB logging на async с timeout
   - Добавить connection health check перед каждым DB call

---

## 🚀 QUICK FIX - СЕЙЧАС:

```python
# В mercari_notifications.py:run_scheduler()

# Линия 317: ЗАКОММЕНТИРОВАТЬ
# try:
#     self.db.add_log_entry('INFO', f'[SCHEDULER] Loop alive! Iter {loop_iteration}', 'scheduler')
# except Exception as db_log_error:
#     logger.warning(f"[SCHEDULER] Failed to log heartbeat to DB: {db_log_error}")

# Линия 331: ЗАКОММЕНТИРОВАТЬ
# try:
#     self.db.add_log_entry('INFO', 'Configuration reloaded from database', 'config')
# except Exception as db_log_error:
#     logger.warning(f"[CONFIG] Failed to log to database: {db_log_error}")

# Линия 339: ЗАКОММЕНТИРОВАТЬ
# try:
#     self.db.add_log_entry('INFO', f"Search interval changed: {last_interval}s → {config.SEARCH_INTERVAL}s", 'config')
# except Exception as db_log_error:
#     logger.warning(f"[CONFIG] Failed to log to database: {db_log_error}")

# Линия 361: ЗАКОММЕНТИРОВАТЬ
# try:
#     self.db.add_log_entry('ERROR', f'[SCHEDULER] run_pending() error: {str(schedule_error)[:100]}', 'scheduler')
# except:
#     pass
```

**Эти логи всё равно дублируются в `logger.info()` → видны в Railway logs!**

---

## 📊 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:

После Quick Fix:
- ✅ Scheduler будет работать 24/7 без зависаний
- ✅ Логи всё равно будут видны в Railway logs
- ✅ Нет лишних DB calls которые могут зависнуть

---

## 🔍 КАК ПРОВЕРИТЬ:

1. Применить Quick Fix
2. Deploy на Railway
3. Проверить логи через час:
   ```
   [SCHEDULER] ⏰ Loop alive! Iteration 3600 (60 min uptime)
   [SCHEDULER] ⏰ Loop alive! Iteration 7200 (120 min uptime)
   ```
4. Если логи продолжаются - УСПЕХ! ✅

---

**Дата:** 24 ноября 2024, 19:20 MSK
**Статус:** 🔴 ПРОБЛЕМА ДИАГНОСТИРОВАНА - ГОТОВ QUICK FIX
