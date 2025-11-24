# 🔍 SHOPS BLACKLIST DEBUG SUMMARY

## 📅 Дата: 24 ноября 2024

---

## ❌ ПРОБЛЕМА:

**Blacklist категорий не работает для Shops items:**
- Shops items в базе данных имеют `category = NULL`
- Фильтр по категориям в `core.py` не срабатывает для Shops
- Пользователь не может блокировать Shops items по категориям

---

## 🔎 ПРОВЕДЁННОЕ ИССЛЕДОВАНИЕ:

### 1. Проверка существующего кода (коммит c161130)

**Найдено:**
- Уже был добавлен фикс для Shops категорий: использовать `category_id`
- Код должен был работать: `item_category = f"ID:{category_id}"`

**Но:**
- Все Shops items в БД имеют `category = NULL`
- Значит фикс не работал

### 2. Тестирование mercapi API

**Результат тестирования:**
```python
# test_shops_category.py показал:
Item: 2JHRZ53QqtsavyLrWN9KP9 (SHOPS)
  hasattr(item, 'category_id'): True ✅
  getattr(item, 'category_id', None): 208 ✅
  hasattr(item, 'item_category'): False
```

**Вывод:**
- ВСЕ items (regular И Shops) имеют `category_id` атрибут
- НИКАКИЕ items НЕ имеют `item_category` в search results
- `category_id` доступен и для regular, и для Shops items

### 3. Тестирование полного flow

**Результат тестирования:**
```python
# test_full_flow.py показал:
INFO [pyMercariAPI.mercari]: [SHOPS CATEGORY] 2JHRZ53QqtsavyLrWN9KP9 using category_id: 208 -> 'ID:208' ✅
INFO [pyMercariAPI.mercari]: [SHOPS DICT] 2JHRZ53QqtsavyLrWN9KP9: item_dict['category'] = 'ID:208' ✅
INFO [mercari_api]: [Item.__init__] SHOPS item 2JHRZ53QqtsavyLrWN9KP9: category from data = 'ID:208' ✅

Item 2: 2JHRZ53QqtsavyLrWN9KP9 (SHOPS)
  Category: 'ID:208' ✅ SUCCESS!
```

**Вывод:**
- Код работает ПРАВИЛЬНО! 🎉
- Категория извлекается, сохраняется в Item, и доступна

---

## 🤔 ГИПОТЕЗЫ О ПРИЧИНЕ NULL:

### Гипотеза 1: Старые данные в БД
Shops items с `category = NULL` были добавлены ДО фикса (коммит c161130).
Новые items должны иметь правильную категорию.

### Гипотеза 2: Код на Railway не обновлён
На Railway ещё работает старая версия без фикса c161130.

### Гипотеза 3: Проблема в сохранении в БД
Категория доходит до `db.add_item()`, но теряется при INSERT.

---

## ✅ ДОБАВЛЕННЫЕ DEBUG ЛОГИ:

### Коммит 1: `3320bee` - Comprehensive debugging
Добавлены логи в 3 местах:

1. **mercari.py:302** - Когда извлекается category_id
   ```python
   logger.info(f"[SHOPS CATEGORY] {item_id} using category_id: {category_id} -> '{item_category}'")
   ```

2. **mercari.py:338** - Когда создаётся item_dict
   ```python
   logger.info(f"[SHOPS DICT] {item_id}: item_dict['category'] = '{item_dict['category']}'")
   ```

3. **items.py:38-41** - Когда Item создаётся
   ```python
   logger.info(f"[Item.__init__] SHOPS item {self.id}: category from data = '{self.category}'")
   ```

### Коммит 2: `2b0341e` - DB layer debugging
Добавлен лог в `db.add_item()`:

4. **db.py:590-591** - Перед INSERT в БД
   ```python
   print(f"[DB ADD_ITEM] SHOPS item {mercari_id}: category = '{category_value}'")
   ```

---

## 🎯 ПЛАН ДЕЙСТВИЙ:

### Шаг 1: Deploy на Railway ✅
```bash
git push origin main
```

### Шаг 2: Мониторинг логов
После deploy искать в логах Railway:
```
[SHOPS CATEGORY] ... using category_id: XXX -> 'ID:XXX'
[SHOPS DICT] ...: item_dict['category'] = 'ID:XXX'
[Item.__init__] SHOPS item ...: category from data = 'ID:XXX'
[DB ADD_ITEM] SHOPS item ...: category = 'ID:XXX'
```

### Шаг 3: Проверка БД
Если логи показывают правильные значения, но в БД NULL:
- Проблема в SQL INSERT query
- Проверить порядок параметров в db.py:586-612

Если логи показывают NULL на каком-то этапе:
- Найти где именно теряется категория
- Исправить этот конкретный участок кода

### Шаг 4: Очистка старых данных (если нужно)
Если проблема была в старых данных:
```sql
-- Удалить старые Shops items без категории
DELETE FROM items WHERE mercari_id NOT LIKE 'm%' AND category IS NULL;
```

---

## 📊 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:

После deploy новые Shops items должны иметь в логах:
```
[SHOPS CATEGORY] 2JHRZ53QqtsavyLrWN9KP9 using category_id: 208 -> 'ID:208'
[SHOPS DICT] 2JHRZ53QqtsavyLrWN9KP9: item_dict['category'] = 'ID:208'
[Item.__init__] SHOPS item 2JHRZ53QqtsavyLrWN9KP9: category from data = 'ID:208'
[DB ADD_ITEM] SHOPS item 2JHRZ53QqtsavyLrWN9KP9: category = 'ID:208'
[FILTER] [SHOPS] Item 2JHRZ53QqtsavyLrWN9KP9: category = 'ID:208'
```

И в БД:
```sql
SELECT mercari_id, category FROM items WHERE mercari_id = '2JHRZ53QqtsavyLrWN9KP9';
-- Результат: category = 'ID:208' ✅
```

---

## 🧪 ТЕСТОВЫЕ ФАЙЛЫ:

Созданы 2 тестовых файла для локального тестирования:

1. **test_shops_category.py** - Проверка mercapi API
   - Показывает какие атрибуты есть у items из поиска
   - Подтверждает наличие `category_id`

2. **test_full_flow.py** - Проверка полного flow
   - Тестирует `Mercari.search()` -> `Item` creation
   - Показывает что категория правильно извлекается

---

## 📝 КОММИТЫ:

```
2b0341e - debug: Add category logging to db.add_item()
3320bee - debug: Add comprehensive Shops category debugging
c161130 - fix: Shops blacklist using category_id (ORIGINAL FIX)
```

---

## 💡 КАК ИСПОЛЬЗОВАТЬ BLACKLIST ДЛЯ SHOPS:

После фикса пользователь сможет блокировать Shops по ID категории:

**Пример:**
```
Config -> Category Blacklist:
ID:208
ID:127
ID:7339
```

Где номера - это `category_id` из mercapi.

**Как найти ID:**
1. Посмотреть логи: `[SHOPS CATEGORY] ... using category_id: XXX`
2. Или проверить БД: `SELECT DISTINCT category FROM items WHERE mercari_id NOT LIKE 'm%'`

---

**Статус:** 🟡 Ожидание deploy и проверки логов на Railway

**Следующий шаг:** Deploy на Railway и мониторинг логов
