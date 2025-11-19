# 💡 Идеи по переводу с японского на английский

## Проблема
Mercari возвращает названия товаров, описания и другие поля на японском языке. 
Нужен перевод на английский для удобства пользователя.

## Требования
- ✅ Бесплатный API
- ✅ Переключатель в Web UI (включить/выключить перевод)
- ✅ Не замедлять работу бота

---

## Вариант 1: Google Translate API (Бесплатный лимит)

### Преимущества:
- Высокое качество перевода
- Официальный API
- Поддержка batch перевода (много текстов за раз)

### Недостатки:
- Бесплатно только 500,000 символов/месяц
- Требует Google Cloud аккаунт
- Нужен API key

### Реализация:
```python
from google.cloud import translate_v2 as translate

def translate_text(text: str, target: str = 'en') -> str:
    """Translate text using Google Translate"""
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language=target)
    return result['translatedText']
```

### Оценка:
Если в среднем товар = 50 символов (название), и находим 100 товаров/день:
- 100 items × 50 chars = 5,000 chars/day
- 5,000 × 30 days = 150,000 chars/month
- **Уложится в бесплатный лимит! ✅**

---

## Вариант 2: DeepL API Free

### Преимущества:
- Лучшее качество перевода (лучше Google для многих языков)
- 500,000 символов/месяц бесплатно
- Простой REST API

### Недостатки:
- Требует регистрацию
- API key обязателен
- Немного медленнее Google

### Реализация:
```python
import requests

def translate_with_deepl(text: str, target_lang: str = 'EN') -> str:
    """Translate using DeepL API"""
    api_key = config.DEEPL_API_KEY
    url = "https://api-free.deepl.com/v2/translate"
    
    params = {
        'auth_key': api_key,
        'text': text,
        'target_lang': target_lang,
        'source_lang': 'JA'
    }
    
    response = requests.post(url, data=params)
    result = response.json()
    return result['translations'][0]['text']
```

### Оценка:
**Рекомендуется! Лучший баланс качества и бесплатности.**

---

## Вариант 3: MyMemory Translation API

### Преимущества:
- Полностью бесплатный (без лимитов с email)
- Не требует API key
- Простой REST API

### Недостатки:
- Качество перевода ниже Google/DeepL
- Может быть медленным
- Лимит: 10,000 запросов/день (достаточно)

### Реализация:
```python
import requests

def translate_with_mymemory(text: str, lang_pair: str = 'ja|en', email: str = None) -> str:
    """Translate using MyMemory API (free)"""
    url = "https://api.mymemory.translated.net/get"
    
    params = {
        'q': text,
        'langpair': lang_pair
    }
    
    if email:
        params['de'] = email  # Increases rate limit
    
    response = requests.get(url, params=params)
    result = response.json()
    
    if result['responseStatus'] == 200:
        return result['responseData']['translatedText']
    else:
        return text  # Return original if translation fails
```

### Оценка:
**Хороший вариант для начала! Не требует регистрации.**

---

## Вариант 4: Argos Translate (Локальный, оффлайн)

### Преимущества:
- Полностью бесплатный
- Работает оффлайн
- Нет лимитов
- Open source

### Недостатки:
- Требует установку (большой размер ~500MB)
- Качество перевода среднее
- Медленный на CPU (нужен GPU для скорости)

### Реализация:
```python
import argostranslate.package
import argostranslate.translate

def translate_with_argos(text: str, source: str = 'ja', target: str = 'en') -> str:
    """Translate using Argos Translate (offline)"""
    # Download package first time only
    # argostranslate.package.update_package_index()
    # available_packages = argostranslate.package.get_available_packages()
    # package_to_install = next(filter(lambda x: x.from_code == source and x.to_code == target, available_packages))
    # argostranslate.package.install_from_path(package_to_install.download())
    
    # Translate
    return argostranslate.translate.translate(text, source, target)
```

### Оценка:
**Не рекомендуется для Railway (требует много места и ресурсов).**

---

## Вариант 5: LibreTranslate API (Self-hosted или бесплатный сервис)

### Преимущества:
- Open source
- Бесплатные публичные инстансы
- Хорошее качество

### Недостатки:
- Публичные инстансы могут быть медленными
- Rate limits на бесплатных серверах

### Реализация:
```python
import requests

def translate_with_libretranslate(text: str, source: str = 'ja', target: str = 'en') -> str:
    """Translate using LibreTranslate"""
    url = "https://libretranslate.de/translate"  # Public instance
    
    payload = {
        'q': text,
        'source': source,
        'target': target,
        'format': 'text'
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    return result['translatedText']
```

### Оценка:
**Средний вариант. Зависит от доступности публичного сервера.**

---

## 🎯 РЕКОМЕНДАЦИЯ

### Лучший вариант: **DeepL API Free**

**Почему:**
1. Лучшее качество перевода
2. 500k символов/месяц хватит с запасом
3. Быстрый и надежный
4. Простая регистрация

### Запасной вариант: **MyMemory API**

**Почему:**
1. Не требует регистрации (можно начать сразу)
2. Достаточно для начала
3. Если качество не устроит → переход на DeepL

---

## 🔧 РЕАЛИЗАЦИЯ

### 1. Добавить настройку в конфигурацию

```python
# configuration_values.py
TRANSLATION_ENABLED = False  # По умолчанию выключено
TRANSLATION_SERVICE = 'mymemory'  # или 'deepl', 'google'
DEEPL_API_KEY = None  # Для DeepL
TRANSLATION_CACHE_ENABLED = True  # Кэшировать переводы
```

### 2. Создать модуль перевода

```python
# translator.py
import logging
from typing import Optional
from configuration_values import config

logger = logging.getLogger(__name__)

class Translator:
    """Translation service wrapper"""
    
    def __init__(self):
        self.enabled = config.TRANSLATION_ENABLED
        self.service = config.TRANSLATION_SERVICE
        self.cache = {}  # Simple in-memory cache
    
    def translate(self, text: str, source: str = 'ja', target: str = 'en') -> str:
        """Translate text with caching"""
        if not self.enabled:
            return text
        
        # Check cache
        cache_key = f"{text}_{source}_{target}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Translate
        try:
            if self.service == 'mymemory':
                result = self._translate_mymemory(text, source, target)
            elif self.service == 'deepl':
                result = self._translate_deepl(text, target)
            elif self.service == 'google':
                result = self._translate_google(text, target)
            else:
                return text
            
            # Cache result
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text  # Return original on error
    
    def _translate_mymemory(self, text: str, source: str, target: str) -> str:
        """MyMemory API implementation"""
        import requests
        # ... implementation ...
    
    def _translate_deepl(self, text: str, target: str) -> str:
        """DeepL API implementation"""
        import requests
        # ... implementation ...
    
    def _translate_google(self, text: str, target: str) -> str:
        """Google Translate implementation"""
        from google.cloud import translate_v2
        # ... implementation ...

# Global instance
translator = Translator()
```

### 3. Использовать в коде

```python
# simple_telegram_worker.py
from translator import translator

def _format_item_message(self, item: Dict[str, Any]) -> str:
    # Title
    title = item.get('title', 'No title')
    
    # Translate if enabled
    if config.TRANSLATION_ENABLED:
        title = translator.translate(title)
    
    # ... rest of formatting
```

### 4. Добавить переключатель в Web UI

```html
<!-- web_ui_plugin/templates/config.html -->
<div class="form-group">
    <label>Translation</label>
    <div class="form-check">
        <input type="checkbox" id="translation_enabled" name="translation_enabled">
        <label for="translation_enabled">Enable automatic translation (JA → EN)</label>
    </div>
    
    <select name="translation_service" class="form-control mt-2">
        <option value="mymemory">MyMemory (Free, no key required)</option>
        <option value="deepl">DeepL (Best quality, requires API key)</option>
        <option value="google">Google Translate (Requires API key)</option>
    </select>
    
    <input type="text" name="deepl_api_key" placeholder="DeepL API Key (if using DeepL)" class="form-control mt-2">
</div>
```

---

## 📊 ОЦЕНКА ПРОИЗВОДИТЕЛЬНОСТИ

### MyMemory API:
- Скорость: ~200-500ms на запрос
- Для 100 items: ~20-50 секунд
- **Приемлемо, но можно кэшировать**

### DeepL API:
- Скорость: ~100-300ms на запрос
- Для 100 items: ~10-30 секунд
- **Быстрее и качественнее**

### С кэшированием:
- Повторные переводы: 0ms (из кэша)
- Многие товары повторяются → кэш эффективен
- **Рекомендуется!**

---

## ✅ ПЛАН ДЕЙСТВИЙ (КОГДА РЕАЛИЗОВЫВАТЬ)

1. **Сейчас:** Не делать (фокус на основных проблемах)
2. **После стабилизации:** Добавить MyMemory (простой старт)
3. **Если нужно качество:** Перейти на DeepL
4. **Опционально:** Добавить кэширование переводов в БД

---

**Создано:** 2025-11-19  
**Статус:** Идеи для будущей реализации  
**Приоритет:** Низкий (после решения основных проблем)
