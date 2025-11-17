# Config Hot Reload - Implementation Plan

**Статус:** READY TO IMPLEMENT
**Цель:** Config изменения применяются БЕЗ restart сервиса

---

## 🎯 Проблема

Сейчас:
1. Config сохраняется в БД ✅
2. НО worker читает config только при старте ❌
3. Поэтому требуется restart ❌

---

## ✅ Решение: Hot Reload Config

### Шаг 1: Добавить config cache и reload в configuration_values.py

```python
# В configuration_values.py добавить:

import time

class ConfigValues:
    def __init__(self):
        self._config_cache = {}
        self._last_reload_time = 0
        self._reload_interval = 10  # Check every 10 seconds

        # Load initial config from DB
        self._load_config_from_db()

    def _load_config_from_db(self):
        """Load configuration from database"""
        try:
            from db import get_db
            db = get_db()

            # Load all config_ keys
            all_config = db.get_all_config()  # Need to implement this

            for key, value in all_config.items():
                if key.startswith('config_'):
                    config_key = key.replace('config_', '').upper()
                    self._config_cache[config_key] = value

                    # Set attribute
                    setattr(self, config_key, value)

        except Exception as e:
            logger.warning(f"Could not load config from DB: {e}")

    def reload_if_needed(self):
        """Hot reload config if enough time has passed"""
        current_time = time.time()

        if current_time - self._last_reload_time < self._reload_interval:
            return False  # Too soon

        self._last_reload_time = current_time

        try:
            old_config = self._config_cache.copy()
            self._load_config_from_db()

            if old_config != self._config_cache:
                logger.info("[CONFIG] ✅ Hot reload: config updated!")
                return True

        except Exception as e:
            logger.error(f"[CONFIG] Hot reload failed: {e}")

        return False

# Create global instance
config = ConfigValues()
```

### Шаг 2: Добавить hot reload в main loop

```python
# В mercari_notifications.py в методе run():

while True:
    try:
        # HOT RELOAD CONFIG EVERY ITERATION
        config.reload_if_needed()  # <--- ДОБАВИТЬ ЭТУ СТРОКУ

        schedule.run_pending()
        time.sleep(1)
    except KeyboardInterrupt:
        break
```

### Шаг 3: Убрать "restart required" из UI

```python
# В web_ui_plugin/app.py:

@app.route('/api/config/system', methods=['POST'])
def api_save_system_config():
    try:
        data = request.get_json()

        # Save to database
        saved_count = 0
        for key, value in data.items():
            if db.save_config(f"config_{key}", value):
                saved_count += 1

        return jsonify({
            'success': True,
            'message': f'✅ Saved {saved_count} settings',
            'note': 'Settings will be applied automatically within 10 seconds'  # <-- ИЗМЕНИТЬ
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Шаг 4: Обновить UI сообщение

```html
<!-- В web_ui_plugin/templates/config.html убрать "Restart required" -->

<div class="alert alert-success" id="success-message" style="display: none;">
    ✅ Settings saved successfully!
    <br>
    <small class="text-muted">Changes will be applied automatically within 10 seconds.</small>
</div>
```

---

## 🔥 Как это работает:

1. **Worker loop:** Каждую секунду проверяет `config.reload_if_needed()`
2. **Config check:** Раз в 10 секунд загружает config из БД
3. **If changed:** Обновляет все атрибуты config объекта
4. **Result:** Новые значения применяются БЕЗ restart!

---

## 📊 Сравнение с KufarSearcher:

**KufarSearcher:**
- Config в ENV variables
- Restart нужен для чтения новых ENV

**MercariSearcher (с hot reload):**
- Config в PostgreSQL
- Hot reload каждые 10 секунд
- БЕЗ restart! ✅

---

## ⚙️ Config параметры с hot reload:

✅ **Будут hot reload:**
- `scan_interval` - интервал сканирования
- `max_items` - макс товаров
- `request_delay` - задержка между запросами
- И другие runtime параметры

❌ **НЕ будут hot reload (требуют restart):**
- `DATABASE_URL` - подключение к БД
- `TELEGRAM_BOT_TOKEN` - токен бота
- Системные ENV variables

---

## 🎯 Итоговый result:

```
BEFORE:
User: Изменяет scan_interval с 300 на 60
System: "Settings saved! Restart required"
User: Ждёт 5 минут пока админ перезапустит ❌

AFTER (с hot reload):
User: Изменяет scan_interval с 300 на 60
System: "Settings saved! Applied in 10 seconds ✅"
System: (через 10 сек) "Config reloaded! scan_interval=60"
User: Работает сразу! ✅
```

---

**Автор:** Claude Code
**Дата:** 2025-11-17
**Статус:** Готов к имплементации
