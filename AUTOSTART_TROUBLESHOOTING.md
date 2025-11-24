# 🔧 AUTOSTART SCHEDULER TROUBLESHOOTING

## 📅 Дата: 24 ноября 2024

---

## ❌ ПРОБЛЕМА:

**Автозапуск сканера не работает на Railway**
- Scheduler не запускается автоматически
- Или запускается и через час останавливается
- Нужно проверить логи Railway чтобы понять причину

---

## 🔍 ДИАГНОСТИКА - ЧТО ПРОВЕРИТЬ В RAILWAY LOGS:

### 1. Проверить запуск Gunicorn

**Искать в логах:**
```
[START.SH] 🚀 Starting web process with Gunicorn
```

**Если НЕТ этой строки:**
- ❌ `start.sh` не запускается
- **Фикс:** Проверить `Procfile` - должно быть `web: bash start.sh`
- **Команда:** `cat Procfile` → должно показать `web: bash start.sh`

### 2. Проверить инициализацию worker

**Искать в логах:**
```
[GUNICORN] Worker XXXXX initialized
```

**Если НЕТ этой строки:**
- ❌ `post_worker_init()` hook не вызывается
- **Фикс:** Проверить `gunicorn_config.py` - должна быть функция `post_worker_init()`

### 3. Проверить запуск WSGI

**Искать в логах:**
```
[WSGI] Starting background scheduler (attempt #1)...
[WSGI] Imported MercariNotificationApp
[WSGI] Creating MercariNotificationApp instance...
[WSGI] MercariNotificationApp created successfully
[WSGI] Calling run_scheduler()...
```

**Если НЕТ этих строк:**
- ❌ Scheduler thread не запускается в `wsgi.py`
- **Фикс:** Проблема в `wsgi.py` - threads не создаются

**Если есть ошибка после "Calling run_scheduler()...":**
- ❌ `run_scheduler()` падает с ошибкой
- **Фикс:** Смотреть traceback ошибки, исправлять в `mercari_notifications.py`

### 4. Проверить scheduler loop

**Искать в логах:**
```
[SCHEDULER] ⏰ Entering main loop...
[SCHEDULER] ⏰ Loop alive! Iteration 1 (0.0 min)
[SCHEDULER] ⏰ Loop alive! Iteration 2 (0.5 min)
```

**Если НЕТ "Entering main loop":**
- ❌ `run_scheduler()` не доходит до основного цикла
- **Фикс:** Смотреть что происходит до loop в `mercari_notifications.py:run_scheduler()`

**Если "Loop alive" прекращается:**
- ❌ Loop выходит или падает
- **Фикс:** Смотреть последние логи перед остановкой - там будет ошибка

### 5. Проверить DB connection

**Искать в логах:**
```
[DB] Connected to PostgreSQL
[DB ERROR] Connection error
```

**Если есть "[DB ERROR] Connection error":**
- ❌ Потеряно соединение с PostgreSQL
- **Фикс:** Должен работать auto-reconnect (есть в коде)

### 6. Проверить health monitor

**Искать в логах:**
```
[HEALTH] Health check monitor started
[HEALTH] ❌ Scheduler thread is DEAD! Restarting...
[HEALTH] ✅ Scheduler thread restarted
```

**Если есть "Scheduler thread is DEAD":**
- ⚠️ Thread умер, но должен перезапуститься
- **Если НЕ перезапускается:** Проблема в health monitor logic

---

## 🐛 ИЗВЕСТНЫЕ ПРОБЛЕМЫ И ФИКСЫ:

### Проблема 1: Gunicorn timeout (вероятнее всего!)

**Симптомы:**
- Scheduler запускается
- Работает ~2 минуты
- Потом внезапно останавливается
- В логах: `[CRITICAL] WORKER TIMEOUT`

**Причина:**
Gunicorn убивает worker если он не отвечает на requests в течение `timeout` секунд.
Scheduler thread блокирует worker → timeout → worker killed → scheduler умирает.

**РЕШЕНИЕ:**

Изменить архитектуру - scheduler НЕ должен блокировать worker:

#### Вариант A: Использовать async/non-blocking sleep

В `mercari_notifications.py` изменить:
```python
# СТАРЫЙ КОД (блокирует worker):
time.sleep(config.SEARCH_INTERVAL)

# НОВЫЙ КОД (не блокирует):
import signal
def timeout_handler(signum, frame):
    raise TimeoutError()

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(config.SEARCH_INTERVAL)
try:
    time.sleep(config.SEARCH_INTERVAL)
except TimeoutError:
    pass
```

НО это всё равно блокирует! ❌

#### Вариант B: Разбить sleep на маленькие куски + heartbeat

```python
# Вместо time.sleep(300) делаем:
total_wait = config.SEARCH_INTERVAL  # 300 seconds
chunk_size = 10  # Sleep 10 seconds at a time

for i in range(0, total_wait, chunk_size):
    time.sleep(chunk_size)
    # Отправить heartbeat в logger каждые 10 секунд
    logger.debug(f"[SCHEDULER] Waiting... ({i}/{total_wait}s)")
```

Это позволит worker отвечать на health checks! ✅

#### Вариант C: Увеличить Gunicorn timeout (НЕ РЕКОМЕНДУЕТСЯ)

В `gunicorn_config.py`:
```python
timeout = 600  # 10 minutes (уже установлено)
```

Но Railway может иметь свой timeout независимо от Gunicorn! ❌

#### Вариант D: Использовать отдельный worker process (ЛУЧШИЙ!)

Создать отдельный Railway service для scheduler:

1. Создать `Procfile`:
```
web: bash start.sh
worker: python3 mercari_notifications.py worker
```

2. В `start.sh` проверять `SERVICE_NAME`:
```bash
if [ "$SERVICE_NAME" = "worker" ]; then
    exec python3 mercari_notifications.py worker
else
    exec gunicorn --config gunicorn_config.py wsgi:application
fi
```

3. В Railway создать 2 сервиса:
   - `web` - Flask UI (без scheduler)
   - `worker` - Только scheduler

Это ПРАВИЛЬНАЯ архитектура! ✅✅✅

### Проблема 2: Thread не запускается в Gunicorn worker

**Симптомы:**
- Логи показывают "WSGI application loaded"
- НО нет "Starting background scheduler"
- Thread создаётся в master process, а не в worker

**РЕШЕНИЕ:**
Используется `post_worker_init()` hook - уже реализовано в коде ✅

### Проблема 3: Railway перезапускает процесс

**Симптомы:**
- Scheduler работает
- Через N минут внезапно перезапуск
- Логи начинаются заново

**Причина:**
Railway может перезапускать сервис при:
- Memory limit exceeded
- Crash detection
- Health check failure

**РЕШЕНИЕ:**
Проверить использование памяти и health checks в Railway dashboard.

---

## ✅ QUICK FIXES - ЧТО СДЕЛАТЬ ПРЯМО СЕЙЧАС:

### Fix 1: Разбить sleep на chunks (БЫСТРЫЙ ФИКС!)

Этот фикс позволит worker оставаться responsive во время ожидания:

**Файл:** `mercari_notifications.py`

**Найти:**
```python
time.sleep(config.SEARCH_INTERVAL)
```

**Заменить на:**
```python
# Split sleep into chunks to keep worker responsive
total_wait = config.SEARCH_INTERVAL
chunk_size = 30  # Sleep 30 seconds at a time
chunks = total_wait // chunk_size

for i in range(chunks):
    time.sleep(chunk_size)
    elapsed_min = ((i + 1) * chunk_size) / 60
    logger.debug(f"[SCHEDULER] ⏰ Waiting... ({elapsed_min:.1f}/{total_wait/60:.1f} min)")

# Sleep remaining seconds
remaining = total_wait % chunk_size
if remaining > 0:
    time.sleep(remaining)
```

Это должно решить проблему с worker timeout! ✅

### Fix 2: Увеличить worker timeout (ЗАПАСНОЙ ВАРИАНТ)

**Файл:** `gunicorn_config.py`

**Изменить:**
```python
timeout = 600  # Было: 120, стало: 600 (10 минут)
```

Уже установлено в текущем коде ✅

### Fix 3: Добавить keepalive requests (ПРОДВИНУТЫЙ ФИКС)

Scheduler периодически делает HTTP request к самому себе, чтобы worker не считался "idle":

```python
import requests

def keepalive():
    try:
        requests.get(f"http://localhost:{PORT}/health", timeout=5)
    except:
        pass

# В scheduler loop:
for i in range(chunks):
    time.sleep(chunk_size)
    keepalive()  # Keep worker alive
```

---

## 🎯 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:

### Шаг 1: Проверить текущие логи Railway
1. Открыть Railway Dashboard
2. Открыть логи сервиса
3. Искать ключевые слова из раздела "ДИАГНОСТИКА"
4. Определить на каком этапе останавливается

### Шаг 2: Применить Quick Fix 1
1. Изменить `mercari_notifications.py` - разбить sleep на chunks
2. Commit + push
3. Проверить логи - должны быть частые heartbeats во время ожидания

### Шаг 3: Если не помогло - Separate Worker Process
1. Настроить отдельный Railway service для worker
2. Изменить `Procfile` и `start.sh`
3. Deploy оба сервиса

---

## 📊 КАК ПРОВЕРИТЬ ЧТО РАБОТАЕТ:

После deploy проверять логи каждые 5 минут в течение часа:

**Ожидаемые логи (правильная работа):**
```
[START.SH] 🚀 Starting web process
[GUNICORN] Worker 12345 initialized
[WSGI] Starting background scheduler (attempt #1)
[WSGI] MercariNotificationApp created successfully
[SCHEDULER] ⏰ Entering main loop...
[SCHEDULER] ⏰ Loop alive! Iteration 1 (0.0 min)
[SCHEDULER] 🔄 Starting search cycle...
[SEARCH] Found 15 items...
[SCHEDULER] ✅ Search cycle completed
[SCHEDULER] ⏰ Waiting... (0.5/5.0 min)
[SCHEDULER] ⏰ Waiting... (1.0/5.0 min)
[SCHEDULER] ⏰ Waiting... (1.5/5.0 min)
...
[SCHEDULER] ⏰ Loop alive! Iteration 2 (5.0 min)
```

Это должно продолжаться бесконечно! ✅

**Проблемные логи:**
```
[SCHEDULER] ⏰ Loop alive! Iteration 1
[CRITICAL] WORKER TIMEOUT (pid:12345)  ← ПРОБЛЕМА!
[START.SH] 🚀 Starting web process  ← Перезапуск
```

Если видите WORKER TIMEOUT → нужен Quick Fix 1! ⚠️

---

## 📝 SUMMARY:

**Наиболее вероятная проблема:**
Gunicorn worker timeout из-за блокирующего `time.sleep(300)`

**Решение:**
Разбить sleep на маленькие chunks (30 сек) + heartbeat logging

**Файл для изменения:**
`mercari_notifications.py` - функция `run_scheduler()`

**Ожидаемый результат:**
Scheduler будет работать 24/7 без timeout

---

**Дата:** 24 ноября 2024
**Статус:** 🟡 Требуется проверка Railway logs и применение Quick Fix
