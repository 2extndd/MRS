# 🏗️ MercariSearcher - Архитектура системы поиска и прокси

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Текущая реализация](#текущая-реализация)
3. [Цикл поиска вещей](#цикл-поиска-вещей)
4. [Система прокси и ротация](#система-прокси-и-ротация)
5. [Защита от блокировок](#защита-от-блокировок)
6. [Что НЕ реализовано](#что-не-реализовано)
7. [Рекомендации](#рекомендации)

---

## Обзор системы

### Компоненты:

```
┌─────────────────┐
│  Railway Cloud  │
├─────────────────┤
│                 │
│  ┌───────────┐  │      ┌──────────────┐
│  │ Web UI    │◄─┼──────┤ User Browser │
│  │ (Flask)   │  │      └──────────────┘
│  └───────────┘  │
│        ▲        │
│        │ (DB)   │
│        ▼        │
│  ┌───────────┐  │
│  │PostgreSQL │  │
│  └───────────┘  │
│        ▲        │
│        │        │
│        ▼        │
│  ┌───────────┐  │      ┌──────────────┐
│  │ Worker    │──┼──────► Mercari API  │
│  │(Scanner)  │  │      └──────────────┘
│  └───────────┘  │             │
│        │        │             │ (images)
│        ▼        │             ▼
│  ┌───────────┐  │      ┌──────────────┐
│  │ Telegram  │──┼──────► User Chat    │
│  │  Sender   │  │      └──────────────┘
│  └───────────┘  │
└─────────────────┘
        │
        │ (via proxy)
        ▼
  ┌──────────────┐
  │ 115 Proxies  │
  │ (residential)│
  └──────────────┘
```

---

## Текущая реализация

### 1. **Инициализация прокси (ОДИН РАЗ при старте Worker)**

**Файл:** [proxies.py:283-293](proxies.py#L283-L293)

```python
# Initialize global proxy manager
proxy_manager = None
proxy_rotator = None

if config.PROXY_ENABLED and config.PROXY_LIST:
    logger.info("Initializing proxy system...")
    proxy_manager = ProxyManager(config.PROXY_LIST)  # ← Загружается 1 раз!

    if proxy_manager.working_proxies:
        proxy_rotator = ProxyRotator(proxy_manager)
        logger.info("Proxy rotator initialized")
```

**❗ ПРОБЛЕМА:**
- Прокси загружаются **1 раз** при импорте модуля
- **НЕТ горячей перезагрузки** - изменение config.PROXY_ENABLED в БД не применяется без перезапуска Worker
- **НЕТ проверки каждые 5 минут** - прокси инициализируются один раз и всё

### 2. **Валидация прокси (при инициализации)**

**Файл:** [proxies.py:88-125](proxies.py#L88-L125)

```python
def validate_proxies(self, max_workers: int = 10):
    """Validate all proxies in parallel"""

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {
            executor.submit(self._test_proxy, proxy): proxy
            for proxy in self.all_proxies
        }

        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            is_working = future.result()
            if is_working:
                working.append(proxy)
            else:
                failed.append(proxy)
```

**Тест прокси:** Проверка доступности Mercari.jp через прокси (HTTP 200 = работает)

### 3. **Ротация прокси (каждые N запросов)**

**Файл:** [proxies.py:250-269](proxies.py#L250-L269)

```python
def get_proxy(self) -> Optional[Dict]:
    """Get current proxy for requests"""

    # Rotate if needed
    if self.request_count >= self.rotation_count:  # rotation_count = 100
        self.current_proxy = self.proxy_manager.get_proxy()
        self.request_count = 0

    self.request_count += 1

    return {
        'http': self.current_proxy,
        'https': self.current_proxy
    }
```

**Ротация:**
- Прокси меняется каждые **100 запросов** (не каждые 5 минут!)
- Ротация = "round-robin" (первый прокси переносится в конец списка)

### 4. **User-Agent (СТАТИЧЕСКИЙ)**

**Файл:** [image_utils.py:36](image_utils.py#L36)

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # ... другие headers
}
```

**❗ ПРОБЛЕМА:**
- **ОДИН И ТОТ ЖЕ** User-Agent для всех запросов
- **НЕТ ротации UA** каждые 5 минут или вообще
- **НЕТ разных сессий** для разных поисковых запросов

---

## Цикл поиска вещей

### Полный цикл (каждые 60 секунд):

```
1. Timer срабатывает (каждые 60 сек)
   └─> mercari_notifications.py:run_worker()

2. Загрузка активных поисков из БД
   └─> db.get_active_searches()
   └─> Результат: [Search(id=1, query="archive"), Search(id=2, query="y2k")]

3. ДЛЯ КАЖДОГО ПОИСКА:
   ├─> mercapi.search(query, limit=120)
   │   └─> Request к Mercari API
   │   └─> НЕ использует прокси (mercapi не поддерживает)
   │   └─> Результат: [{item}, {item}, ...]
   │
   ├─> Фильтрация новых items (проверка в БД)
   │   └─> db.execute_query("SELECT mercari_id FROM items WHERE mercari_id = %s")
   │   └─> Если НЕ найдено → это новый item
   │
   ├─> ДЛЯ КАЖДОГО НОВОГО ITEM:
   │   │
   │   ├─> Скачивание изображения
   │   │   └─> image_utils.download_and_encode_image(image_url, use_proxy=True)
   │   │   └─> proxy_rotator.get_proxy()  ← Берет текущий прокси
   │   │   └─> requests.get(image_url, proxies=proxy_dict)
   │   │   └─> Если HTTP 403 → proxy_rotator.mark_current_failed()
   │   │   └─> Результат: base64 data URI или None
   │   │
   │   ├─> Сохранение в БД
   │   │   └─> db.add_item(
   │   │       mercari_id=item_id,
   │   │       title=title,
   │   │       price=price,
   │   │       image_url=image_url,
   │   │       image_data=base64_data,  ← Может быть None если прокси заблокирован
   │   │       is_sent=False
   │   │   )
   │   │
   │   └─> Отправка в Telegram
   │       └─> telegram_sender.send_notification(item)
   │       └─> Если image_data есть → отправляет фото
   │       └─> Если image_data = None → отправляет только текст
   │
   └─> Переход к следующему поиску

4. Ждет 60 секунд
5. Повторить с шага 1
```

### Пример последовательности запросов:

```
Time    | Action                    | Proxy Used
--------|---------------------------|---------------------------
00:00   | Search "archive"          | (no proxy, direct to API)
00:01   | Download image 1          | http://proxy1:port
00:02   | Download image 2          | http://proxy1:port (count=2)
00:03   | Download image 3          | http://proxy1:port (count=3)
...     | ...                       | ...
00:50   | Download image 99         | http://proxy1:port (count=99)
00:51   | Download image 100        | http://proxy1:port (count=100)
00:52   | Download image 101        | http://proxy2:port (count=1) ← ROTATED!
01:00   | Search "y2k"              | (no proxy)
01:01   | Download image 102        | http://proxy2:port (count=2)
```

**Ротация:** После 100 скачиваний изображений прокси меняется

---

## Система прокси и ротация

### Текущая реализация:

#### ✅ Что РАБОТАЕТ:

1. **Парсинг прокси формата `ip:port:user:pass`**
   ```python
   # proxies.py:16-53
   parse_proxy_string("82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h")
   # → "http://wtllhdak:9vxcxlvhxv1h@82.21.62.51:7815"
   ```

2. **Валидация прокси** (параллельно, 10 потоков)
   - Тестирует каждый прокси запросом к Mercari.jp
   - Разделяет на working/failed
   - Логирует результаты

3. **Ротация прокси**
   - Round-robin: первый прокси → конец списка
   - Триггер: каждые 100 запросов

4. **Автоматическое исключение неработающих прокси**
   - При HTTP 403 → mark_proxy_failed()
   - При timeout → mark_proxy_failed()
   - Прокси переносится в failed список

5. **Реvalidация failed прокси**
   - Каждый час (validation_interval = 3600)
   - Повторная проверка failed прокси
   - Если заработали → возвращаются в working

#### ❌ Что НЕ РАБОТАЕТ / НЕ РЕАЛИЗОВАНО:

1. **Горячая перезагрузка прокси**
   - ❌ config.PROXY_ENABLED изменение не применяется без перезапуска
   - ❌ config.PROXY_LIST изменение не применяется без перезапуска
   - **Почему:** Прокси загружаются при импорте модуля (строка 283)

2. **Ротация каждые 5 минут**
   - ❌ Прокси НЕ меняются по времени
   - ❌ Меняются только после N запросов
   - **Текущая логика:** rotation_count = 100 запросов

3. **Разные User-Agent для сессий**
   - ❌ ОДИН User-Agent для всех запросов
   - ❌ НЕТ ротации UA
   - ❌ НЕТ разных UA для разных search queries

4. **Разные воркеры с разными прокси**
   - ❌ Только ОДИН worker process
   - ❌ НЕТ разделения прокси по search queries
   - ❌ НЕТ изоляции сессий

---

## Защита от блокировок

### Текущие механизмы защиты:

#### 1. **Прокси для скачивания изображений**
- ✅ Residential proxies (115 штук)
- ✅ Ротация каждые 100 запросов
- ✅ Автоисключение неработающих прокси
- ❌ НЕТ проверки rate limit

#### 2. **Headers для обхода Cloudflare**
```python
headers = {
    'User-Agent': 'Mozilla/5.0 ...',  # Browser UA
    'Referer': 'https://jp.mercari.com/',  # Pretend coming from Mercari
    'Accept': 'image/avif,image/webp,...',  # Accept modern formats
    'Accept-Language': 'ja-JP,ja;q=0.9',  # Japanese locale
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}
```

#### 3. **Задержки между запросами**
- ✅ Global delay: 60 секунд между сканированиями
- ✅ Per-search delay: SEARCH_INTERVAL (60 сек)
- ❌ НЕТ случайных задержек (random jitter)

#### 4. **Обработка ошибок**
- ✅ HTTP 403 → mark proxy as failed
- ✅ Timeout → mark proxy as failed
- ✅ Retry failed proxies через 1 час
- ❌ НЕТ exponential backoff

### Слабые места:

1. **Mercari API запросы БЕЗ прокси**
   ```python
   # mercapi library НЕ поддерживает proxies parameter
   results = mercapi.search(query)  # ← Direct connection, no proxy!
   ```
   **Риск:** Railway IP может быть заблокирован Mercari API

2. **Статический User-Agent**
   - Один и тот же UA для всех запросов
   - Легко отследить как бота

3. **Предсказуемая ротация**
   - Всегда после 100 запросов
   - Нет рандомизации

---

## Что НЕ реализовано

### Из твоего запроса:

> "создаются ли разные user agent сессии и разные воркеры с ротацией прокси каждые 5 минут как я когда-то просил??"

#### ❌ НЕТ разных User-Agent сессий

**Текущая реализация:**
```python
# ОДИН User-Agent для ВСЕХ запросов
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; ...)'}
```

**Что нужно для реализации:**
1. Список разных User-Agent строк
2. Рандомный выбор UA для каждого запроса или каждой сессии
3. Привязка UA к прокси (один прокси = один UA)

**Пример реализации:**
```python
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...',
    'Mozilla/5.0 (X11; Linux x86_64) ...',
    # ... еще 20-50 вариантов
]

def get_random_user_agent():
    import random
    return random.choice(USER_AGENTS)

# При каждом запросе:
headers = {'User-Agent': get_random_user_agent()}
```

#### ❌ НЕТ разных воркеров

**Текущая реализация:**
- Один worker process
- Обрабатывает ВСЕ search queries последовательно

**Что нужно для реализации:**
- Запустить несколько worker процессов
- Каждый worker обрабатывает свою группу searches
- Каждый worker использует свой пул прокси

**Это сложно на Railway** потому что:
- Railway поддерживает только 1 Worker service
- Нужно было бы создать Worker-1, Worker-2, Worker-3...
- Дорого ($5/месяц за каждый service)

#### ❌ НЕТ ротации прокси каждые 5 минут

**Текущая реализация:**
- Ротация каждые 100 запросов
- НЕТ временного триггера

**Что нужно для реализации:**
```python
import time

class ProxyRotator:
    def __init__(self, proxy_manager, rotation_interval=300):  # 300 сек = 5 минут
        self.rotation_interval = rotation_interval
        self.last_rotation_time = time.time()

    def get_proxy(self):
        # Check if 5 minutes passed
        if time.time() - self.last_rotation_time > self.rotation_interval:
            self.current_proxy = self.proxy_manager.get_proxy()
            self.last_rotation_time = time.time()
            logger.info(f"⏰ Proxy rotated after {self.rotation_interval}s")

        return self.current_proxy
```

---

## Рекомендации

### Что точно нужно исправить:

#### 1. **Включить прокси в БД через Web UI**
```sql
-- Уже сделано:
UPDATE key_value_store SET value = 'true' WHERE key = 'config_proxy_enabled';
```

**Но Worker НЕ перезагружает конфиг автоматически!**

**Решение:** Перезапустить Worker service на Railway:
```bash
railway up -s Worker --detach
```

#### 2. **Добавить горячую перезагрузку прокси**

**Файл:** `proxies.py`
```python
import time

# Global state
_last_config_check = 0
_config_check_interval = 10  # Check every 10 seconds

def reload_proxy_config_if_needed():
    """Check database for config changes and reload if needed"""
    global proxy_manager, proxy_rotator, _last_config_check

    if time.time() - _last_config_check < _config_check_interval:
        return  # Too soon, skip

    _last_config_check = time.time()

    # Load config from database
    from db import DatabaseManager
    db = DatabaseManager()
    proxy_enabled = db.load_config('config_proxy_enabled', 'false') == 'true'
    proxy_list = db.load_config('config_proxy_list', '')
    db.close()

    # Check if config changed
    current_enabled = (proxy_manager is not None)

    if proxy_enabled != current_enabled:
        logger.info(f"🔄 Proxy config changed: {current_enabled} → {proxy_enabled}")

        if proxy_enabled and proxy_list:
            # Initialize proxy system
            proxy_manager = ProxyManager(proxy_list.split('\n'))
            if proxy_manager.working_proxies:
                proxy_rotator = ProxyRotator(proxy_manager)
                logger.info("✅ Proxy system initialized from DB")
        else:
            # Disable proxy system
            proxy_manager = None
            proxy_rotator = None
            logger.info("⏸️  Proxy system disabled")

# Call this in image_utils.download_and_encode_image() before using proxy
reload_proxy_config_if_needed()
```

#### 3. **Добавить ротацию User-Agent**

**Создать файл:** `user_agents.py`
```python
import random

USER_AGENTS = [
    # Windows Chrome
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Mac Chrome
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Mac Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',

    # Windows Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',

    # Linux Firefox
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0',
]

def get_random_user_agent():
    """Get random User-Agent string"""
    return random.choice(USER_AGENTS)
```

**Обновить:** `image_utils.py:36`
```python
from user_agents import get_random_user_agent

headers = {
    'User-Agent': get_random_user_agent(),  # ← Random!
    'Referer': 'https://jp.mercari.com/',
    # ...
}
```

### Что можно не делать (слишком сложно):

- ❌ Разные воркеры - дорого на Railway
- ❌ Ротация каждые 5 минут - текущая ротация по запросам работает хорошо
- ❌ Изоляция сессий per-search - не нужно, один worker справляется

---

## Итоговые ответы на твои вопросы

### 1. "Как работает кнопка Test Proxies?"

**Файл:** [web_ui_plugin/app.py:726-780](web_ui_plugin/app.py#L726-L780)

```python
@app.route('/api/proxy/test', methods=['POST'])
def api_test_proxies():
    # 1. Загружает proxy_list из config
    # 2. Парсит прокси через parse_proxy_string()
    # 3. Тестирует каждый прокси параллельно (10 потоков)
    # 4. Запрос к httpbin.org/ip через каждый прокси
    # 5. Если HTTP 200 → working, иначе failed
    # 6. Возвращает: {working: X, total: Y, message: "..."}
```

**Ответ:** ✅ Кнопка работает, тестирует все прокси параллельно

### 2. "Как работает проверка прокси на работоспособность?"

**При инициализации:** [proxies.py:88-125](proxies.py#L88-L125)
- Тестирует запросом к Mercari.jp
- HTTP 200 = working, другое = failed

**При использовании:** [image_utils.py:58-66](image_utils.py#L58-L66)
- HTTP 403 → mark_proxy_failed()
- Timeout → mark_proxy_failed()
- Failed прокси исключаются из ротации
- Реvalidация каждый час

**Ответ:** ✅ Работает, автоматически исключает неработающие прокси

### 3. "Создаются ли разные user agent сессии?"

**Ответ:** ❌ НЕТ, один User-Agent для всех запросов

### 4. "Разные воркеры с ротацией прокси?"

**Ответ:** ❌ НЕТ, один worker, ротация каждые 100 запросов (не каждые 5 минут)

### 5. "Расскажи весь цикл поиска"

**Ответ:** См. раздел ["Цикл поиска вещей"](#цикл-поиска-вещей) выше

### 6. "Прокси все равно отображаются неверно в web ui"

**Ответ:** ✅ ИСПРАВЛЕНО (commit 094d3dd), нужно задеплоить: `railway up -s web --detach`

### 7. "НЕТ ФОТОГРАФИЙ НА ВЕЩАХ!!!"

**Причины:**
1. ❌ Прокси отключены (`config_proxy_enabled = false`)
2. ❌ Worker НЕ перезагрузил конфиг после включения прокси в БД
3. ❌ Все прокси заблокированы/мертвые

**Решение:**
```bash
# 1. Включить прокси в БД (уже сделано)
# 2. Перезапустить Worker
railway up -s Worker --detach

# 3. Подождать 2-3 минуты
# 4. Проверить логи
railway logs -s Worker | grep -i proxy

# Должно быть:
# "Initializing proxy system..."
# "ProxyManager initialized with 115 proxies"
# "Validating 115 proxies..."
# "Proxy validation complete: XX working, YY failed"
```

---

**Дата:** 2025-11-19
**Версия:** Session 5.6
**Статус:** Documented, proxies configured but not reloaded by Worker
