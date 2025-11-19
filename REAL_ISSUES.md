# 🔴 РЕАЛЬНЫЕ ПРОБЛЕМЫ MercariSearcher

## Найденные проблемы:

### 1. ❌ Telegram уведомления НЕ отправляются
**Причина:** Worker успешно получает items из БД, НО не вызывает `process_pending_notifications()`

**Где смотреть:**
- `mercari_notifications.py` строка 103-106
- Условие `if results['new_items'] > 0:` проверяет только результат поиска
- Но `process_pending_notifications()` вызывается ТОЛЬКО если new_items > 0

**Проблема:**
```python
# Строка 102-106
if results['new_items'] > 0:
    logger.info(f"Processing {results['new_items']} new items for notifications...")
    notification_stats = process_pending_notifications()
```

Если items УЖЕ в БД (is_sent=False), но results['new_items'] = 0 (потому что они не новые в этом цикле), 
то `process_pending_notifications()` НЕ ВЫЗЫВАЕТСЯ!

**Решение:** Вызывать `process_pending_notifications()` ВСЕГДА, не только когда есть новые items в текущем цикле.

---

### 2. ❌ Recent Items (Last 24 Hours) не работает
**Причина:** `found_at` не заполняется при создании item

**Где смотреть:**
- `db.py` строка 131-156 - создание таблицы items
- `found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP` - есть в схеме
- НО при INSERT в строке 434-459 НЕ передается `found_at`!

**Проблема:**
PostgreSQL может не применять DEFAULT для timestamp если используется SERIAL PRIMARY KEY.

**Решение:** Явно передавать `found_at=datetime.now()` при создании item.

---

### 3. ❌ API Requests счетчик показывает 0
**Причина:** Dashboard берет данные из `state_stats` вместо БД

**Где смотреть:**
- `web_ui_plugin/templates/dashboard.html` строка 32
- `{{ state_stats.total_api_requests }}` - берет из shared_state
- Но web process НЕ имеет доступа к shared_state worker process!

**Проблема:**
Shared state работает только внутри одного процесса. Web и Worker - разные процессы.

**Решение:** 
- В dashboard.html использовать счетчик из БД: `{{ total_api_requests }}`
- В `web_ui_plugin/app.py` строка 198 уже есть: `'total_api_requests': total_api_requests`

---

### 4. ❌ Фотографии плохого качества
**Причина:** Используются thumbnails вместо полноразмерных фото

**Где смотреть:**
- `pyMercariAPI/mercari.py` строка 173-176
- `thumbnails = getattr(item, 'thumbnails', [])`
- `item_dict['image_url'] = thumbnails[0]` - это маленькие превью!

**Проблема:**
mercapi возвращает thumbnails (маленькие превью ~240px), а не полные фото.

**Решение:** 
Использовать `photos` вместо `thumbnails`, если они доступны.
Или получать полную информацию через `get_item_details()`.

---

### 5. ❌ Нет timestamp когда item был найден
**Причина:** В items.html не отображается `found_at`

**Где смотреть:**
- `web_ui_plugin/templates/items.html` строки 10-28
- Нет вывода timestamp!

**Решение:** Добавить строку с timestamp в карточку item.

---

### 6. ⚠️ Логи не показывают startup и config changes
**Причина:** Логи пишутся, но могут быть проблемы с форматированием или порядком

**Где смотреть:**
- `mercari_notifications.py` строки 152-171
- Логи ПИШУТСЯ в stdout и БД
- Но может быть проблема с синхронизацией или уровнем логирования

**Решение:** Проверить что логи действительно не пишутся в БД.

---

## 🔧 ИСПРАВЛЕНИЯ

### Исправление #1: Telegram уведомления

**Файл:** `mercari_notifications.py`

```python
# БЫЛО (строка 99-106):
try:
    # Perform searches
    results = self.searcher.search_all_queries()

    # Process notifications for new items
    if results['new_items'] > 0:
        logger.info(f"Processing {results['new_items']} new items for notifications...")
        notification_stats = process_pending_notifications()
        logger.info(f"Notifications: {notification_stats['sent']}/{notification_stats['total']} sent")

# ДОЛЖНО БЫТЬ:
try:
    # Perform searches
    results = self.searcher.search_all_queries()

    # ВСЕГДА проверяем pending notifications (даже если в этом цикле new_items=0)
    logger.info("Checking for pending notifications...")
    notification_stats = process_pending_notifications()
    
    if notification_stats['total'] > 0:
        logger.info(f"Notifications: {notification_stats['sent']}/{notification_stats['total']} sent")
    else:
        logger.info("No pending notifications")
```

---

### Исправление #2: found_at timestamp

**Файл:** `db.py`

```python
# В методе add_item() добавить:

def add_item(self, mercari_id, search_id, **kwargs):
    """Add new item if not exists"""
    # ... existing check code ...
    
    query = """
        INSERT INTO items
        (mercari_id, search_id, title, price, currency, brand, condition,
         size, shipping_cost, stock_quantity, item_url, image_url,
         seller_name, seller_rating, location, description, category, found_at)  # <- добавить found_at
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  # <- добавить %s
    """
    params = (
        mercari_id,
        search_id,
        kwargs.get('title'),
        kwargs.get('price'),
        kwargs.get('currency', 'JPY'),
        kwargs.get('brand'),
        kwargs.get('condition'),
        kwargs.get('size'),
        kwargs.get('shipping_cost'),
        kwargs.get('stock_quantity', 1),
        kwargs.get('item_url'),
        kwargs.get('image_url'),
        kwargs.get('seller_name'),
        kwargs.get('seller_rating'),
        kwargs.get('location'),
        kwargs.get('description'),
        kwargs.get('category'),
        get_moscow_time()  # <- ДОБАВИТЬ ЭТО!
    )
```

---

### Исправление #3: API Requests counter

**Файл:** `web_ui_plugin/templates/dashboard.html`

```html
<!-- БЫЛО (строка 32): -->
<h2 id="api-requests">{{ state_stats.total_api_requests }}</h2>

<!-- ДОЛЖНО БЫТЬ: -->
<h2 id="api-requests">{{ total_api_requests }}</h2>
```

**Файл:** `web_ui_plugin/app.py`

```python
# В функции index() строка 52-55:

return render_template('dashboard.html',
                     stats=stats,
                     state_stats=state_stats,
                     total_api_requests=db.get_api_counter(),  # <- ДОБАВИТЬ ЭТО!
                     config=config)
```

---

### Исправление #4: Качество фотографий

**Файл:** `pyMercariAPI/mercari.py`

```python
# БЫЛО (строка 172-176):
# Get thumbnail
thumbnails = getattr(item, 'thumbnails', [])
if thumbnails:
    item_dict['image_url'] = thumbnails[0]

# ДОЛЖНО БЫТЬ:
# Get best available image (photos > thumbnails)
photos = getattr(item, 'photos', [])
thumbnails = getattr(item, 'thumbnails', [])

if photos:
    # Use full-size photo if available
    item_dict['image_url'] = photos[0]
elif thumbnails:
    # Fallback to thumbnail
    item_dict['image_url'] = thumbnails[0]
```

---

### Исправление #5: Timestamp в items.html

**Файл:** `web_ui_plugin/templates/items.html`

```html
<!-- Добавить после строки 20: -->
<p class="card-text">
    <strong>Price:</strong> ¥{{ item.price }} (${{ (item.price * config.USD_CONVERSION_RATE)|round(2) }})<br>
    {% if item.brand %}<strong>Brand:</strong> {{ item.brand }}<br>{% endif %}
    {% if item.condition %}<strong>Condition:</strong> {{ item.condition }}<br>{% endif %}
    {% if item.size %}<strong>Size:</strong> {{ item.size }}<br>{% endif %}
    {% if item.found_at %}<strong>Found:</strong> <small class="text-muted">{{ item.found_at }}</small><br>{% endif %}  <!-- ДОБАВИТЬ ЭТО -->
</p>
```

---

### Исправление #6: Логирование config changes

**Файл:** `mercari_notifications.py`

```python
# В методе run_scheduler() после строки 178:

while True:
    try:
        # HOT RELOAD CONFIG EVERY ITERATION
        if config.reload_if_needed():
            logger.info("[CONFIG] ✅ Configuration reloaded from database")  # <- ДОБАВИТЬ!
            self.db.add_log_entry('INFO', 'Configuration reloaded from database', 'config')  # <- ДОБАВИТЬ!
            
            # If search interval changed, recreate schedule
            if config.SEARCH_INTERVAL != last_interval:
                logger.info(f"[CONFIG] Search interval changed from {last_interval}s to {config.SEARCH_INTERVAL}s, updating schedule...")
                self.db.add_log_entry('INFO', f"Search interval changed: {last_interval}s → {config.SEARCH_INTERVAL}s", 'config')  # <- ДОБАВИТЬ!
                self._setup_schedule()
                last_interval = config.SEARCH_INTERVAL
```

---

## 📋 ПРИОРИТЕТЫ

### Критические (исправить СЕЙЧАС):
1. ✅ **Telegram notifications** - исправление #1
2. ✅ **API counter** - исправление #3

### Важные (исправить сегодня):
3. ✅ **found_at timestamp** - исправление #2
4. ✅ **Items timestamp display** - исправление #5

### Желательные (исправить когда есть время):
5. ⭐ **Photo quality** - исправление #4
6. ⭐ **Config logging** - исправление #6

---

## 🧪 КАК ПРОВЕРИТЬ

### После исправления #1 (Telegram):
```bash
# Проверить worker logs
railway logs --service worker | grep "Processing.*pending notifications"
railway logs --service worker | grep "Notifications:.*sent"

# Должны увидеть:
# "Processing pending notifications..."
# "Notifications: X/Y sent"
```

### После исправления #2 и #3:
```bash
# Открыть Web UI
# https://web-production-fe38.up.railway.app/

# Dashboard должен показывать:
# - API Requests: > 0 (не 0!)
# - Recent Items: items за последние 24 часа
```

### После исправления #5:
```bash
# Открыть /items
# https://web-production-fe38.up.railway.app/items

# Должны видеть timestamp в каждой карточке
```

---

## ⚠️ ВАЖНО

**НЕ ТРОГАЙТЕ зависимости!** 
Проблема НЕ в библиотеках mercapi или telegram. 
Проблема в логике кода - notifications не вызываются, timestamps не записываются, counters не отображаются.

Все исправления - это простые изменения логики, БЕЗ изменения зависимостей!
