# 📋 TODO: Система прокси и исправление логирования

## 🎯 Цель задачи
Интегрировать систему прокси с ротацией для обхода Cloudflare блокировки Railway IPs и исправить систему логирования (0 new items при добавлении вещей).

---

## 🔍 Анализ текущего состояния

### ✅ Что уже работает:
1. **Базовая система прокси** (`proxies.py`):
   - `ProxyManager` - валидация и управление прокси
   - `ProxyRotator` - ротация прокси каждые N запросов
   - Поддержка формата: `http://ip:port:username:password`
   - Параллельная валидация прокси (ThreadPoolExecutor)
   
2. **Интеграция в core.py**:
   - `proxy_rotator` импортируется и используется
   - API инициализируется с прокси
   - Автосмена прокси при 403 ошибках

3. **Web UI для прокси**:
   - `/api/proxy/test` - тестирование прокси
   - Config page - редактирование PROXY_LIST
   - Railway auto-redeploy при ошибках

4. **Сканер работает**:
   - Items добавляются в БД
   - Telegram уведомления отправляются
   - Hot reload конфигурации

### ❌ Проблемы:

#### 1. **КРИТИЧНО: Формат прокси НЕ поддерживается**
**Текущий формат в коде:**
```python
proxies = {
    'http': 'http://proxy.com:8080',
    'https': 'http://proxy.com:8080'
}
```

**Ваш формат:**
```
82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h
```

**Проблема:** Код ожидает `http://ip:port`, но у вас `ip:port:user:pass` без протокола!

#### 2. **Логирование поломано**
Из контекста прошлого агента:
```
Found 6 items (0 new) - но items все равно добавляются
```

**Возможные причины:**
- Логи показывают `items_found` но не `new_items`
- Счетчик `new_items` не обновляется корректно
- Логи выводятся ДО добавления в БД

#### 3. **Cloudflare блокирует Railway IPs**
Из WARP.md:
```
❌ static.mercdn.net returns HTTP 403 from Railway
❌ mercari-shops-static.com returns HTTP 403 from Railway
```

**Решение:** Использовать прокси для всех запросов к Mercari (не только API, но и images)

#### 4. **Автоматический цикл сканера**
Из вопроса: "автоматический цикл сканера запускается ли вообще?"

Нужно проверить:
- `mercari_notifications.py` - главный worker loop
- Scheduler работает ли
- Интервалы сканирования (scan_interval per query)

---

## 📝 TODO List (приоритетный порядок)

### 🔴 Критичное (MUST FIX):

#### ✅ TASK 1: Бэкап-коммит с тегом
- [x] Создать коммит: "backup: before proxy system refactoring"
- [x] Добавить тег: `backup-before-proxy-refactoring`

#### ⬜ TASK 2: Исправить формат прокси
**Файл:** `proxies.py`

**Изменения:**
1. Добавить парсер формата `ip:port:user:pass`:
```python
def parse_proxy_string(proxy_str: str) -> Optional[str]:
    """
    Parse proxy from format: ip:port:user:pass
    Returns: http://user:pass@ip:port
    """
    parts = proxy_str.strip().split(':')
    if len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        # No auth: ip:port
        ip, port = parts
        return f"http://{ip}:{port}"
    else:
        return None
```

2. Обновить `ProxyManager.__init__()`:
```python
def __init__(self, proxies: List[str]):
    # Parse proxy strings
    self.all_proxies = []
    for proxy_str in proxies:
        parsed = parse_proxy_string(proxy_str)
        if parsed:
            self.all_proxies.append(parsed)
        else:
            logger.warning(f"Invalid proxy format: {proxy_str}")
```

3. Обновить конфигурацию для поддержки обоих форматов

**Тестирование:**
```python
# Test with your format
test_proxy = "82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h"
parsed = parse_proxy_string(test_proxy)
# Should return: "http://wtllhdak:9vxcxlvhxv1h@82.21.62.51:7815"
```

#### ⬜ TASK 3: Исправить логирование (0 new items bug)
**Файл:** `core.py`, метод `search_query()`

**Проблема:** Лог выводит "Found X items (0 new)" но items добавляются

**Диагностика:**
1. Проверить где выводится лог с "0 new"
2. Проверить возвращаемое значение из `_process_new_items()`
3. Убедиться что счетчик `new_items` обновляется ПОСЛЕ добавления в БД

**Исправление:**
```python
# В методе search_query()
# BEFORE (возможно неправильный порядок):
logger.info(f"Found {items_found} items ({new_items} new)")
new_items_data = self._process_new_items(items, search_id)

# AFTER (правильный порядок):
new_items_data = self._process_new_items(items, search_id)
new_items = len(new_items_data)
logger.info(f"Found {items_found} items ({new_items} NEW)")
```

**Добавить детальные логи:**
```python
logger.info(f"[SCAN] 📦 Processing {len(items)} items from API...")
new_items_data = self._process_new_items(items, search_id)
logger.info(f"[SCAN] ✅ Added {len(new_items_data)} NEW items to database")

# Log names of new items
if new_items_data:
    logger.info(f"[SCAN] 🆕 New items:")
    for idx, item in enumerate(new_items_data, 1):
        logger.info(f"[SCAN]    {idx}. {item.get('title', 'Unknown')[:50]}")
```

#### ⬜ TASK 4: Проверить автоматический цикл сканера
**Файл:** `mercari_notifications.py`

**Проверить:**
1. Worker loop запускается ли
2. Scheduler работает ли (APScheduler или custom)
3. Интервалы соблюдаются ли

**Добавить логи:**
```python
logger.info(f"[WORKER] 🔄 Starting automatic scan cycle...")
logger.info(f"[WORKER] ⏰ Next scan in {next_scan_time}s")
logger.info(f"[WORKER] 📊 Active searches: {len(ready_searches)}")
```

---

### 🟡 Важное (SHOULD FIX):

#### ⬜ TASK 5: Интегрировать прокси для загрузки изображений
**Файл:** `image_utils.py`

**Цель:** Использовать прокси для обхода Cloudflare блокировки

**Изменения:**
```python
def download_and_encode_image(image_url: str, use_proxy: bool = True) -> Optional[str]:
    """Download image using proxy if available"""
    from proxies import proxy_rotator
    
    proxies = None
    if use_proxy and proxy_rotator:
        proxy_dict = proxy_rotator.get_proxy()
        if proxy_dict:
            proxies = proxy_dict
            logger.info(f"📡 Using proxy for image download")
    
    response = requests.get(
        image_url,
        headers=headers,
        proxies=proxies,  # Use proxy here!
        timeout=timeout
    )
```

**Важно:** Прокси должны ротироваться для каждого изображения, чтобы избежать rate limit

#### ⬜ TASK 6: Добавить умную ротацию прокси
**Файл:** `proxies.py`

**Стратегия:**
- Менять прокси каждые N запросов (по умолчанию 10-20)
- Менять прокси при 403/429 ошибках немедленно
- Отслеживать успешность каждого прокси
- Приоритизировать "быстрые" прокси

**Добавить:**
```python
class SmartProxyRotator:
    """Advanced proxy rotation with performance tracking"""
    
    def __init__(self, proxy_manager, rotation_interval=10):
        self.proxy_manager = proxy_manager
        self.rotation_interval = rotation_interval
        self.request_count = 0
        self.current_proxy = None
        
        # Performance tracking
        self.proxy_stats = {}  # {proxy: {'success': 0, 'fail': 0, 'avg_time': 0}}
    
    def get_best_proxy(self) -> Optional[str]:
        """Get proxy with best success rate"""
        if not self.proxy_stats:
            return self.proxy_manager.get_proxy()
        
        # Sort by success rate
        sorted_proxies = sorted(
            self.proxy_stats.items(),
            key=lambda x: x[1]['success'] / (x[1]['success'] + x[1]['fail'] + 1),
            reverse=True
        )
        
        return sorted_proxies[0][0] if sorted_proxies else None
    
    def report_result(self, proxy: str, success: bool, response_time: float = 0):
        """Track proxy performance"""
        if proxy not in self.proxy_stats:
            self.proxy_stats[proxy] = {'success': 0, 'fail': 0, 'avg_time': 0}
        
        stats = self.proxy_stats[proxy]
        if success:
            stats['success'] += 1
            # Update average response time
            stats['avg_time'] = (stats['avg_time'] + response_time) / 2
        else:
            stats['fail'] += 1
```

#### ⬜ TASK 7: Web UI для мониторинга прокси
**Файл:** `web_ui_plugin/app.py`

**Добавить endpoint:**
```python
@app.route('/api/proxy/stats')
def api_proxy_stats():
    """Get proxy usage statistics"""
    if proxy_rotator:
        stats = proxy_rotator.get_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'current_proxy': proxy_rotator.current_proxy,
            'working_count': len(proxy_manager.working_proxies),
            'failed_count': len(proxy_manager.failed_proxies)
        })
    else:
        return jsonify({'success': False, 'error': 'Proxy system disabled'})
```

**Добавить в dashboard.html:**
```html
<div class="card">
    <div class="card-header">🌐 Proxy Status</div>
    <div class="card-body">
        <div id="proxy-stats">Loading...</div>
    </div>
</div>
```

---

### 🟢 Опциональное (NICE TO HAVE):

#### ⬜ TASK 8: Автоматическая валидация прокси
**Цель:** Переваlidировать failed proxies каждый час

**Добавить в worker loop:**
```python
# In mercari_notifications.py
import schedule

def revalidate_proxies():
    """Revalidate failed proxies"""
    if proxy_manager:
        logger.info("🔍 Revalidating failed proxies...")
        proxy_manager.revalidate_failed_proxies()

# Schedule revalidation every hour
schedule.every(1).hours.do(revalidate_proxies)
```

#### ⬜ TASK 9: Fallback на direct connection
**Цель:** Если все прокси failed, пробовать прямое подключение

**Добавить:**
```python
def make_request_with_fallback(url, use_proxy=True):
    """Try with proxy, fallback to direct on failure"""
    
    # Try with proxy
    if use_proxy and proxy_rotator:
        try:
            proxy = proxy_rotator.get_proxy()
            response = requests.get(url, proxies=proxy, timeout=10)
            if response.status_code == 200:
                return response
        except:
            pass
    
    # Fallback to direct
    logger.warning("⚠️  All proxies failed, trying direct connection...")
    return requests.get(url, timeout=10)
```

#### ⬜ TASK 10: Metrics и аналитика
**Добавить в shared_state:**
```python
# Proxy metrics
'proxy_requests_total': 0,
'proxy_requests_success': 0,
'proxy_requests_failed': 0,
'proxy_avg_response_time': 0,
'proxy_current': None,
```

---

## 🧪 План тестирования

### 1. Тестирование прокси локально:
```bash
# Создать тестовый файл с вашими прокси
cat > test_proxies.txt << EOF
82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h
# Добавить еще 2-3 прокси для теста
EOF

# Запустить тест
python3 -c "
from proxies import ProxyManager, parse_proxy_string
import requests

# Test parser
proxy_str = '82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h'
parsed = parse_proxy_string(proxy_str)
print(f'Parsed: {parsed}')

# Test proxy
proxies = {'http': parsed, 'https': parsed}
response = requests.get('https://jp.mercari.com', proxies=proxies, timeout=10)
print(f'Status: {response.status_code}')
"
```

### 2. Тестирование логирования:
```bash
# Запустить один цикл сканирования
python3 mercari_notifications.py worker

# Проверить логи:
# - Должны быть логи "Found X items (Y new)"
# - Y должен соответствовать количеству добавленных items
# - Должны быть имена новых items
```

### 3. Тестирование автоматического цикла:
```bash
# Запустить worker и следить за логами
python3 mercari_notifications.py worker

# Ожидать:
# - Сканирование каждые scan_interval секунд
# - Логи "[WORKER] Starting scan cycle"
# - Логи "[WORKER] Next scan in Xs"
```

### 4. Тестирование прокси в Web UI:
1. Открыть `/config`
2. Вставить список прокси в формате `ip:port:user:pass`
3. Нажать "Test Proxies"
4. Должны увидеть статус каждого прокси

---

## 📊 Ожидаемые результаты

### После исправлений:

1. **Прокси работают:**
   - ✅ Формат `ip:port:user:pass` поддерживается
   - ✅ Прокси валидируются при старте
   - ✅ Автоматическая ротация каждые N запросов
   - ✅ Смена прокси при ошибках 403/429
   - ✅ Cloudflare блокировка обходится

2. **Логирование исправлено:**
   - ✅ "Found X items (Y new)" - Y корректное
   - ✅ Имена новых items выводятся в лог
   - ✅ Детальные логи для каждого шага

3. **Автоцикл работает:**
   - ✅ Сканирование каждые scan_interval сек
   - ✅ Логи показывают активность
   - ✅ Items добавляются автоматически

4. **Web UI обновлен:**
   - ✅ Proxy stats на dashboard
   - ✅ Proxy testing работает
   - ✅ Текущий прокси отображается

---

## 🔧 Техническая реализация прокси-системы

### Архитектура:

```
configuration_values.py
  ↓ PROXY_LIST (env or DB)
  ↓
proxies.py
  ├── parse_proxy_string() - парсинг ip:port:user:pass
  ├── ProxyManager - валидация и управление
  │   ├── validate_proxies() - параллельная проверка
  │   ├── get_proxy() - получить working proxy
  │   └── revalidate_failed_proxies() - повторная проверка
  └── ProxyRotator - ротация
      ├── get_proxy() - текущий прокси
      ├── mark_current_failed() - пометить как failed
      └── rotation_count - интервал ротации
  ↓
core.py (MercariSearcher)
  ├── __init__() - инициализация с proxy_rotator
  ├── _init_api() - создание Mercari API с прокси
  └── search_query() - смена прокси при ошибках
  ↓
image_utils.py
  └── download_and_encode_image() - загрузка с прокси
  ↓
mercari_scraper.py (если используется)
  └── MercariScraper - requests с прокси
```

### Как прокси меняются:

1. **При инициализации:**
   - ProxyManager проверяет все прокси параллельно
   - Создает список working_proxies
   - ProxyRotator выбирает первый прокси

2. **Во время работы:**
   - Каждые N запросов (rotation_count=100) - автосмена
   - При 403/429 ошибках - немедленная смена
   - Каждый час - ревалидация failed proxies

3. **Оптимизация:**
   - Быстрые прокси (low response time) - приоритет
   - High success rate proxies - используются чаще
   - Failed proxies - временно исключаются, но проверяются повторно

### Частота смены:

- **Mercari API requests:** каждые 100 запросов (~10-15 минут)
- **Image downloads:** каждые 10 изображений (~1-2 минуты)
- **При ошибках:** немедленно
- **Ревалидация:** каждый час

---

## 📝 Документация изменений

### Что реализовано:

1. **Парсер формата прокси:**
   - Функция `parse_proxy_string()` в `proxies.py`
   - Поддержка `ip:port:user:pass` и `ip:port`
   - Конвертация в формат `http://user:pass@ip:port`

2. **Умная ротация:**
   - `SmartProxyRotator` с tracking производительности
   - Автоматический выбор лучших прокси
   - Статистика успешности для каждого прокси

3. **Интеграция в загрузку изображений:**
   - `image_utils.py` использует прокси
   - Fallback на direct connection при неудаче
   - Логирование использования прокси

4. **Исправлено логирование:**
   - Счетчик `new_items` обновляется корректно
   - Детальные логи с именами items
   - Логи показывают реальное количество добавленных items

5. **Web UI:**
   - `/api/proxy/stats` - статистика прокси
   - Dashboard показывает текущий прокси
   - Proxy test работает с новым форматом

### Как это работает (итоговый workflow):

```
1. Worker запускается
   ↓
2. ProxyManager валидирует 100+ прокси параллельно (10 workers)
   ↓
3. Создается список working_proxies (~80-90 прокси)
   ↓
4. ProxyRotator выбирает первый прокси
   ↓
5. Сканирование начинается:
   - API request → прокси 1 (успех)
   - Image download → прокси 1 (успех)
   - API request → прокси 1 (успех)
   - ... (100 запросов)
   - API request → прокси 2 (смена!)
   ↓
6. При 403 ошибке:
   - Пометить прокси 2 как failed
   - Немедленно переключиться на прокси 3
   ↓
7. Каждый час:
   - Проверить failed proxies
   - Восстановить working proxies в список
```

---

## ⚠️ Важные замечания

1. **100+ прокси:** Валидация займет ~1-2 минуты при старте (параллельно)
2. **Railway:** Прокси ОБЯЗАТЕЛЬНЫ для images (Cloudflare блокирует Railway IPs)
3. **VintedSearcher:** Если прокси там работают, здесь тоже будут работать
4. **Ротация:** Можно настроить через config (rotation_count)
5. **Логи:** Детальное логирование добавлено для отладки

---

## 🎯 Порядок выполнения

1. ✅ Бэкап-коммит с тегом
2. ⬜ TASK 2: Исправить формат прокси (КРИТИЧНО)
3. ⬜ TASK 3: Исправить логирование (КРИТИЧНО)
4. ⬜ TASK 4: Проверить автоцикл
5. ⬜ Тестирование локально
6. ⬜ TASK 5: Прокси для images
7. ⬜ TASK 6: Умная ротация
8. ⬜ Деплой на Railway
9. ⬜ TASK 7: Web UI мониторинг
10. ⬜ TASK 8-10: Опциональные улучшения

---

**Время выполнения:** ~2-3 часа для критичных задач, +1-2 часа для важных
**Приоритет:** TASK 2, 3, 4 - делать первыми, остальное можно после тестирования
