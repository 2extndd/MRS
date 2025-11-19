# 🔧 Cloudflare Worker as Image Proxy - Полное руководство

## Что это такое?

Cloudflare Worker - это serverless функция, которая работает на edge серверах Cloudflare по всему миру. Мы создадим прокси, который будет скачивать фото с Mercari от имени Railway worker.

### Почему это работает?
- Railway IP → Mercari = ❌ 403 Forbidden (Cloudflare блокирует)
- Cloudflare Worker IP → Mercari = ✅ 200 OK (Cloudflare не блокирует свои собственные IP)
- Railway → Cloudflare Worker → Mercari = ✅ Работает!

### Схема работы:
```
[Railway Worker]
    ↓ (запрос на proxy)
[Cloudflare Worker] https://your-proxy.workers.dev/?url=https://static.mercdn.net/image.jpg
    ↓ (скачивает фото)
[Mercari CDN] static.mercdn.net
    ↓ (возвращает фото)
[Cloudflare Worker]
    ↓ (отдает фото)
[Railway Worker] → сохраняет в базу
```

---

## Часть 1: Создание Cloudflare Worker

### Шаг 1: Регистрация Cloudflare Account

1. Перейди на https://dash.cloudflare.com/sign-up
2. Зарегистрируйся (email + password)
3. Подтверди email
4. **Workers бесплатны, домен НЕ нужен!**

### Шаг 2: Установка Wrangler CLI

Wrangler - это CLI для работы с Cloudflare Workers.

```bash
# Установка Node.js (если нет)
# macOS:
brew install node

# Linux:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Проверка:
node --version  # Должно быть v18+
npm --version

# Установка Wrangler
npm install -g wrangler

# Проверка:
wrangler --version
```

### Шаг 3: Login в Cloudflare

```bash
# Авторизация
wrangler login

# Откроется браузер → нажми "Allow"
# В терминале появится: "Successfully logged in"
```

### Шаг 4: Создание Worker проекта

```bash
# Создай директорию
mkdir ~/mercari-image-proxy
cd ~/mercari-image-proxy

# Инициализация проекта
wrangler init

# Ответь на вопросы:
# "Would you like to use TypeScript?" → No
# "Would you like to create a Worker?" → Yes
# "Would you like to use git?" → Yes (optional)
```

Это создаст:
```
mercari-image-proxy/
├── src/
│   └── index.js         ← Сюда пишем код
├── wrangler.toml        ← Конфигурация
└── package.json
```

### Шаг 5: Код Worker (src/index.js)

Замени содержимое `src/index.js` на этот код:

```javascript
// src/index.js
// Cloudflare Worker для проксирования изображений с Mercari

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    // Получаем URL картинки из query параметра
    const imageUrl = url.searchParams.get('url');

    if (!imageUrl) {
      return new Response(
        JSON.stringify({ error: 'Missing url parameter' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Проверка: только Mercari домены
    const allowedDomains = [
      'static.mercdn.net',
      'mercari-shops-static.com',
      'static.mercdn.jp',
    ];

    const imageDomain = new URL(imageUrl).hostname;
    const isAllowed = allowedDomains.some(domain =>
      imageDomain.includes(domain)
    );

    if (!isAllowed) {
      return new Response(
        JSON.stringify({
          error: 'Domain not allowed',
          allowed: allowedDomains,
          received: imageDomain
        }),
        {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Логирование (видно в wrangler tail)
    console.log(`[PROXY] Fetching: ${imageUrl}`);

    try {
      // Скачиваем изображение с Mercari
      const imageResponse = await fetch(imageUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          'Referer': 'https://jp.mercari.com/',
          'Accept': 'image/avif,image/webp,image/apng,image/png,image/svg+xml,image/*,*/*;q=0.8',
          'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
          'Accept-Encoding': 'gzip, deflate, br',
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache',
        },
        cf: {
          // Cloudflare-specific options
          cacheTtl: 86400,  // Cache на 24 часа
          cacheEverything: true,
        },
      });

      // Проверяем статус
      if (!imageResponse.ok) {
        console.error(`[PROXY] Failed: HTTP ${imageResponse.status}`);
        return new Response(
          JSON.stringify({
            error: `Failed to fetch image: HTTP ${imageResponse.status}`,
            url: imageUrl,
          }),
          {
            status: imageResponse.status,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      // Проверяем размер (макс 5MB)
      const contentLength = imageResponse.headers.get('Content-Length');
      if (contentLength && parseInt(contentLength) > 5 * 1024 * 1024) {
        return new Response(
          JSON.stringify({ error: 'Image too large (max 5MB)' }),
          {
            status: 413,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      console.log(`[PROXY] Success: ${imageResponse.status}, ${contentLength} bytes`);

      // Возвращаем изображение с CORS headers
      const headers = new Headers(imageResponse.headers);
      headers.set('Access-Control-Allow-Origin', '*');
      headers.set('Cache-Control', 'public, max-age=86400'); // 24h browser cache
      headers.set('X-Proxy-Status', 'success');
      headers.set('X-Original-URL', imageUrl);

      return new Response(imageResponse.body, {
        status: 200,
        headers: headers,
      });

    } catch (error) {
      console.error(`[PROXY] Error: ${error.message}`);
      return new Response(
        JSON.stringify({
          error: `Fetch error: ${error.message}`,
          url: imageUrl,
        }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  },
};
```

### Шаг 6: Конфигурация (wrangler.toml)

Отредактируй `wrangler.toml`:

```toml
# wrangler.toml
name = "mercari-image-proxy"
main = "src/index.js"
compatibility_date = "2024-01-01"

# Workers Free tier limits:
# - 100,000 requests/day
# - 10ms CPU time per request
# - 128MB memory

[env.production]
name = "mercari-image-proxy"
routes = []  # Не нужны маршруты, используем workers.dev subdomain
```

### Шаг 7: Тестирование локально

```bash
# Запуск локального dev сервера
wrangler dev

# Откроется localhost:8787
# Тестируй:
# http://localhost:8787/?url=https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m12345678901234567890.jpg
```

В браузере должна загрузиться картинка (или ошибка 403, если Mercari все равно блокирует).

### Шаг 8: Деплой в production

```bash
# Деплой на Cloudflare
wrangler deploy

# Вывод:
# ✨ Successfully deployed mercari-image-proxy
# 🌍 https://mercari-image-proxy.your-subdomain.workers.dev
```

**Сохрани этот URL!** Он понадобится для Railway.

Пример URL:
```
https://mercari-image-proxy.user123.workers.dev
```

### Шаг 9: Тестирование в production

```bash
# Тест 1: Проверка без параметра (должна быть ошибка 400)
curl "https://mercari-image-proxy.your-subdomain.workers.dev/"

# Ответ: {"error":"Missing url parameter"}

# Тест 2: Проверка с настоящим URL Mercari
curl -I "https://mercari-image-proxy.your-subdomain.workers.dev/?url=https://static.mercdn.net/c!/w=240/thumb/photos/m12345678901234567890.jpg"

# Должно быть:
# HTTP/2 200 OK
# content-type: image/jpeg
# x-proxy-status: success

# Тест 3: Скачать картинку
curl "https://mercari-image-proxy.your-subdomain.workers.dev/?url=https://static.mercdn.net/c!/w=240/thumb/photos/m12345678901234567890.jpg" -o test.jpg

# Проверь test.jpg - должна быть картинка
```

### Шаг 10: Мониторинг логов (опционально)

```bash
# Просмотр логов в реальном времени
wrangler tail

# Теперь делай запросы к worker и увидишь:
# [PROXY] Fetching: https://static.mercdn.net/...
# [PROXY] Success: 200, 45678 bytes
```

---

## Часть 2: Интеграция с Railway Worker

### Шаг 1: Обновить image_utils.py

Открой `image_utils.py` и замени функцию:

```python
# image_utils.py
import os
import requests
import base64
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Cloudflare Worker URL (из wrangler deploy)
CLOUDFLARE_WORKER_URL = os.environ.get(
    'CLOUDFLARE_WORKER_URL',
    'https://mercari-image-proxy.your-subdomain.workers.dev'  # Замени на свой!
)

def download_and_encode_image(image_url: str, timeout: int = 20) -> Optional[str]:
    """
    Download image via Cloudflare Worker proxy and encode to base64 data URI

    Args:
        image_url: Mercari image URL (static.mercdn.net)
        timeout: Request timeout in seconds

    Returns:
        Base64 data URI (data:image/jpeg;base64,...) or None if failed
    """

    if not image_url:
        logger.warning("No image URL provided")
        return None

    # Construct proxy URL
    proxy_url = f"{CLOUDFLARE_WORKER_URL}?url={image_url}"

    logger.info(f"📥 Downloading via CF Worker: {image_url[:80]}...")

    try:
        # Request через Cloudflare Worker
        response = requests.get(
            proxy_url,
            timeout=timeout,
            stream=True,
            headers={
                'User-Agent': 'MercariSearcher/1.0 (Railway Worker)',
            }
        )

        # Проверка статуса
        if response.status_code != 200:
            logger.warning(
                f"CF Worker returned HTTP {response.status_code}: {response.text[:200]}"
            )
            return None

        # Читаем content
        image_bytes = response.content

        # Проверка размера (макс 500KB для base64)
        size_kb = len(image_bytes) / 1024
        if size_kb > 500:
            logger.warning(f"Image too large: {size_kb:.1f}KB (max 500KB)")
            return None

        # Определяем MIME type
        content_type = response.headers.get('Content-Type', 'image/jpeg')

        # Кодируем в base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Создаем data URI
        data_uri = f"data:{content_type};base64,{base64_image}"

        logger.info(f"✅ Image downloaded: {size_kb:.1f}KB base64")
        return data_uri

    except requests.Timeout:
        logger.error(f"Timeout downloading image (>{timeout}s)")
        return None

    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return None

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None


def get_original_quality_url(image_url: str) -> str:
    """
    Convert Mercari thumbnail URL to original quality URL

    Examples:
        Input:  https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m123.jpg
        Output: https://static.mercdn.net/item/detail/orig/photos/m123.jpg

    Args:
        image_url: Mercari image URL (any quality)

    Returns:
        Original quality URL
    """

    if not image_url:
        return image_url

    # Mercari URL pattern: https://static.mercdn.net/c!/PARAMS/thumb/photos/FILENAME
    # Original quality:    https://static.mercdn.net/item/detail/orig/photos/FILENAME

    if '/thumb/photos/' in image_url:
        # Extract filename
        filename = image_url.split('/thumb/photos/')[-1]
        # Construct original URL
        original_url = f"https://static.mercdn.net/item/detail/orig/photos/{filename}"
        logger.debug(f"Converted to original quality: {original_url}")
        return original_url

    # Если не можем распарсить, возвращаем как есть
    return image_url
```

### Шаг 2: Обновить core.py

В `core.py` убедись, что функция вызывается правильно:

```python
# core.py (около строки 386-416)
from image_utils import download_and_encode_image, get_original_quality_url

# ... внутри функции add_item_to_database или где скачиваются фото ...

# Получаем URL картинки
image_url = item_data.get('thumbnails', [None])[0] if item_data.get('thumbnails') else None

# Скачиваем и кодируем в base64
image_data = None
if image_url:
    # Опционально: конвертируем в оригинальное качество
    # image_url = get_original_quality_url(image_url)

    # Скачиваем через Cloudflare Worker
    image_data = download_and_encode_image(image_url)

    if image_data:
        logger.info(f"✅ Image saved for item {item_id}")
    else:
        logger.warning(f"⚠️ Failed to download image for item {item_id}")

# Добавляем в базу данных
db_item_id = self.db.add_item(
    item_id=item_id,
    item_name=item_name,
    item_price=item_price,
    item_url=item_url,
    search_id=search_id,
    image_url=image_url,  # Оригинальный Mercari URL
    image_data=image_data  # Base64 data URI
)
```

### Шаг 3: Добавить environment variable на Railway

```bash
# Опция 1: Через Railway CLI
railway variables set CLOUDFLARE_WORKER_URL=https://mercari-image-proxy.your-subdomain.workers.dev -s Worker

# Опция 2: Через Railway Dashboard
# 1. Открой https://railway.app/project/YOUR_PROJECT_ID
# 2. Worker service → Variables
# 3. Add Variable:
#    Name: CLOUDFLARE_WORKER_URL
#    Value: https://mercari-image-proxy.your-subdomain.workers.dev
# 4. Save
```

### Шаг 4: Deploy на Railway

```bash
# Убедись что ты в директории MRS
cd /Users/extndd/Documents/MRS/MRS

# Deploy Worker service
railway up -s Worker --detach

# Проверь логи
railway logs -s Worker
```

Должно быть в логах:
```
📥 Downloading via CF Worker: https://static.mercdn.net/c!/w=240/thumb/photos/...
✅ Image downloaded: 123.4KB base64
```

### Шаг 5: Проверка в базе данных

```bash
# Подключись к PostgreSQL
railway connect Postgres-T-E-

# Проверь новые items с фото
SELECT
    id,
    item_name,
    LENGTH(image_data) as image_size,
    created_at
FROM items
WHERE image_data IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;

# Должны быть новые items с image_size > 100000 (≈100KB+)
```

### Шаг 6: Проверка Web UI

Открой https://web-production-fe38.up.railway.app/

Новые items должны показывать фотографии!

---

## Часть 3: Мониторинг и отладка

### Проверка работы Cloudflare Worker

```bash
# 1. Логи Cloudflare Worker (в реальном времени)
cd ~/mercari-image-proxy
wrangler tail

# Оставь это открытым в отдельном терминале
# Делай запросы к worker и увидишь:
# [PROXY] Fetching: https://static.mercdn.net/...
# [PROXY] Success: 200, 45678 bytes
```

### Проверка Railway Worker

```bash
# 2. Логи Railway Worker
railway logs -s Worker

# Должно быть:
# 📥 Downloading via CF Worker: ...
# ✅ Image downloaded: 123.4KB base64

# Если видишь ошибки:
# ⚠️ CF Worker returned HTTP 403
# → Значит Cloudflare Worker тоже заблокирован Mercari
```

### Debugging ошибок

#### Ошибка: "Missing url parameter"
**Причина:** URL не передается в worker
**Решение:**
```python
# Проверь что CLOUDFLARE_WORKER_URL правильный
print(f"Using worker: {CLOUDFLARE_WORKER_URL}")
# Должно быть: https://mercari-image-proxy.user123.workers.dev
```

#### Ошибка: "Domain not allowed"
**Причина:** URL не с Mercari домена
**Решение:**
```javascript
// Добавь домен в allowedDomains (src/index.js)
const allowedDomains = [
  'static.mercdn.net',
  'mercari-shops-static.com',
  'static.mercdn.jp',
  'your-domain.com',  // Добавь если нужно
];
```

#### Ошибка: HTTP 403 от Cloudflare Worker
**Причина:** Cloudflare Worker тоже заблокирован Mercari (20-30% вероятность)
**Решение:**
1. Попробуй другие headers в worker (см. Часть 4)
2. Или переходи на платный прокси (Solution 1)

#### Ошибка: "Image too large"
**Причина:** Изображение > 500KB
**Решение:**
```python
# Увеличь лимит в image_utils.py
if size_kb > 1000:  # Было 500
    logger.warning(...)
```

---

## Часть 4: Оптимизация и улучшения

### Оптимизация 1: Retry логика

Если worker иногда падает, добавь retry:

```python
# image_utils.py
import time

def download_and_encode_image(image_url: str, timeout: int = 20, retries: int = 3) -> Optional[str]:
    """Download with retry logic"""

    for attempt in range(retries):
        try:
            proxy_url = f"{CLOUDFLARE_WORKER_URL}?url={image_url}"
            response = requests.get(proxy_url, timeout=timeout, stream=True)

            if response.status_code == 200:
                # Success - proceed with encoding
                image_bytes = response.content
                # ... rest of code ...
                return data_uri

            elif response.status_code == 403:
                # Cloudflare block - no point retrying
                logger.warning("CF Worker blocked by Cloudflare (403)")
                return None

            else:
                # Other error - retry
                logger.warning(f"Attempt {attempt+1}/{retries} failed: HTTP {response.status_code}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                return None

        except requests.Timeout:
            logger.warning(f"Attempt {attempt+1}/{retries} timeout")
            if attempt < retries - 1:
                time.sleep(2)
                continue
            return None

        except Exception as e:
            logger.error(f"Attempt {attempt+1}/{retries} error: {e}")
            return None

    return None
```

### Оптимизация 2: Лучшие headers в Worker

Если Cloudflare Worker все равно получает 403, попробуй эти headers:

```javascript
// src/index.js - улучшенные headers
const imageResponse = await fetch(imageUrl, {
  headers: {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Referer': 'https://jp.mercari.com/',
    'Origin': 'https://jp.mercari.com',
    'Accept': 'image/avif,image/webp,image/apng,image/png,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Sec-Fetch-Dest': 'image',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'cross-site',
  },
  cf: {
    cacheTtl: 86400,
    cacheEverything: true,
  },
});
```

### Оптимизация 3: Fallback на оригинальный URL

Если CF Worker не работает, сохрани хотя бы URL:

```python
# core.py
image_data = download_and_encode_image(image_url)

if not image_data:
    # Fallback: сохраняем только URL (фото не будет показываться, но ссылка будет)
    logger.warning(f"Saving URL only for item {item_id}")

db_item_id = self.db.add_item(
    # ...
    image_url=image_url,  # URL всегда сохраняем
    image_data=image_data  # Может быть None
)
```

### Оптимизация 4: Статистика успешности

Добавь в базу данных tracking:

```sql
-- Создай таблицу статистики
CREATE TABLE IF NOT EXISTS image_download_stats (
    id SERIAL PRIMARY KEY,
    date DATE DEFAULT CURRENT_DATE,
    total_attempts INTEGER DEFAULT 0,
    successful INTEGER DEFAULT 0,
    failed_403 INTEGER DEFAULT 0,
    failed_timeout INTEGER DEFAULT 0,
    failed_other INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2)
);
```

```python
# core.py или image_utils.py
def update_download_stats(success: bool, error_type: str = None):
    """Track download success rate"""
    query = """
    INSERT INTO image_download_stats (date, total_attempts, successful, failed_403, failed_timeout, failed_other)
    VALUES (CURRENT_DATE, 1, %s, %s, %s, %s)
    ON CONFLICT (date) DO UPDATE SET
        total_attempts = image_download_stats.total_attempts + 1,
        successful = image_download_stats.successful + EXCLUDED.successful,
        failed_403 = image_download_stats.failed_403 + EXCLUDED.failed_403,
        failed_timeout = image_download_stats.failed_timeout + EXCLUDED.failed_timeout,
        failed_other = image_download_stats.failed_other + EXCLUDED.failed_other,
        success_rate = ROUND((image_download_stats.successful + EXCLUDED.successful)::DECIMAL / (image_download_stats.total_attempts + 1) * 100, 2)
    """

    db.execute_query(query, (
        1 if success else 0,
        1 if error_type == '403' else 0,
        1 if error_type == 'timeout' else 0,
        1 if error_type and error_type not in ['403', 'timeout'] else 0
    ))

# Использование:
image_data = download_and_encode_image(image_url)
if image_data:
    update_download_stats(success=True)
else:
    update_download_stats(success=False, error_type='403')  # Или 'timeout', 'other'
```

Проверка статистики:
```sql
SELECT * FROM image_download_stats ORDER BY date DESC;

-- Результат:
-- date       | total | success | 403 | timeout | other | success_rate
-- 2025-11-19 | 150   | 120     | 25  | 3       | 2     | 80.00
-- 2025-11-18 | 200   | 140     | 55  | 4       | 1     | 70.00
```

---

## Часть 5: Cloudflare Worker Limits (Free Tier)

### Лимиты бесплатного плана:

| Метрика | Free Tier | Paid ($5/month) |
|---------|-----------|-----------------|
| **Requests/day** | 100,000 | 10,000,000 |
| **CPU time/request** | 10ms | 50ms |
| **Memory** | 128MB | 128MB |
| **Script size** | 1MB | 10MB |
| **Duration** | Max 30s | Max 30s |

### Расчет для твоего случая:

```
Сканирование: каждые 60 секунд
Items per scan: ~5-10
Images per item: 1

В день:
- Scans: 60 * 24 = 1,440 scans
- Items: 1,440 * 7 (average) = 10,080 items
- Images: 10,080 requests

Результат: 10,080 << 100,000 ✅ В пределах free tier
```

**Вывод:** Free tier более чем достаточно для твоего проекта!

### Если превысил лимит:

Cloudflare Worker вернет HTTP 429 (Too Many Requests):

```python
# image_utils.py - обработка 429
if response.status_code == 429:
    logger.error("CF Worker rate limit exceeded! Upgrade to paid plan or wait.")
    return None
```

---

## Часть 6: Альтернативные подходы

### Подход 1: Multiple Workers (rotation)

Создай 5 worker'ов с разными поддоменами:

```bash
# Deploy 5 workers
wrangler deploy --name mercari-image-proxy-1
wrangler deploy --name mercari-image-proxy-2
wrangler deploy --name mercari-image-proxy-3
wrangler deploy --name mercari-image-proxy-4
wrangler deploy --name mercari-image-proxy-5
```

Используй их по очереди:

```python
# image_utils.py
WORKER_URLS = [
    'https://mercari-image-proxy-1.user.workers.dev',
    'https://mercari-image-proxy-2.user.workers.dev',
    'https://mercari-image-proxy-3.user.workers.dev',
    'https://mercari-image-proxy-4.user.workers.dev',
    'https://mercari-image-proxy-5.user.workers.dev',
]

import random

def download_and_encode_image(image_url: str, timeout: int = 20) -> Optional[str]:
    # Rotate workers
    worker_url = random.choice(WORKER_URLS)
    proxy_url = f"{worker_url}?url={image_url}"

    # ... rest of code ...
```

### Подход 2: Custom Domain

Если у тебя есть домен, можешь использовать красивый URL:

```toml
# wrangler.toml
[env.production]
routes = [
  { pattern = "proxy.yourdomain.com/*", zone_name = "yourdomain.com" }
]
```

Тогда URL будет:
```
https://proxy.yourdomain.com/?url=https://static.mercdn.net/...
```

---

## Часть 7: Тестирование полного цикла

### Тест 1: Cloudflare Worker отдельно

```bash
# Проверь что worker работает
curl -v "https://mercari-image-proxy.user.workers.dev/?url=https://static.mercdn.net/c!/w=240/thumb/photos/m12345678901234567890.jpg"

# Должно быть:
# < HTTP/2 200
# < content-type: image/jpeg
# < x-proxy-status: success
#
# [binary image data]
```

### Тест 2: Railway worker + CF Worker

```bash
# SSH в Railway Worker
railway run -s Worker bash

# Внутри Railway:
python3 -c "
from image_utils import download_and_encode_image
result = download_and_encode_image('https://static.mercdn.net/c!/w=240/thumb/photos/m12345678901234567890.jpg')
print('Success!' if result else 'Failed!')
print(f'Data URI length: {len(result) if result else 0}')
"

# Должно быть:
# 📥 Downloading via CF Worker: ...
# ✅ Image downloaded: 123.4KB base64
# Success!
# Data URI length: 168234
```

### Тест 3: Проверка в базе данных

```bash
railway connect Postgres-T-E-

# SQL:
SELECT
    COUNT(*) as total_items,
    COUNT(image_data) as items_with_images,
    ROUND(COUNT(image_data)::DECIMAL / COUNT(*) * 100, 2) as success_rate
FROM items
WHERE created_at > NOW() - INTERVAL '1 hour';

# Результат:
# total_items | items_with_images | success_rate
# 50          | 42                | 84.00

# Если success_rate > 70% → ✅ Cloudflare Worker работает!
# Если success_rate < 30% → ❌ Переходи на платный прокси
```

### Тест 4: Web UI

```bash
# Открой в браузере:
open https://web-production-fe38.up.railway.app/

# Проверь последние items:
# - Если фотографии показываются → ✅ Работает
# - Если 403 или пустые → ❌ Не работает
```

---

## Часть 8: Что делать если не работает?

### Сценарий 1: CF Worker возвращает 403

**Причина:** Cloudflare Worker тоже заблокирован Mercari

**Варианты:**

1. **Попробуй другие headers** (см. Оптимизация 2)
2. **Попробуй через другой регион:**
   ```javascript
   // src/index.js
   const imageResponse = await fetch(imageUrl, {
     cf: {
       resolveOverride: 'jp.mercari.com',  // Force Japan
     }
   });
   ```
3. **Переходи на платный прокси** (ScraperAPI из Solution 1)

### Сценарий 2: CF Worker работает, но Railway не видит

**Причина:** Неправильный CLOUDFLARE_WORKER_URL

**Решение:**
```bash
# Проверь environment variable
railway variables -s Worker | grep CLOUDFLARE

# Если нет - добавь:
railway variables set CLOUDFLARE_WORKER_URL=https://your-worker.workers.dev -s Worker

# Redeploy
railway up -s Worker --detach
```

### Сценарий 3: Success rate < 70%

**Причина:** Cloudflare Worker нестабилен

**Решение:** Hybrid approach - CF Worker + fallback на ImgBB:

```python
# image_utils.py
def download_and_encode_image(image_url: str) -> Optional[str]:
    # Try CF Worker first
    result = download_via_cf_worker(image_url)

    if result:
        return result

    # Fallback to ImgBB (only if CF Worker fails)
    logger.warning("CF Worker failed, trying ImgBB fallback...")
    return download_and_upload_to_imgbb(image_url)  # From Solution 4
```

---

## Итоговый чеклист:

### Cloudflare Worker setup:
- [ ] Зарегистрирован Cloudflare account
- [ ] Установлен Wrangler CLI
- [ ] Создан worker проект
- [ ] Код скопирован в src/index.js
- [ ] Deployed: `wrangler deploy`
- [ ] Получен URL: https://mercari-image-proxy.USER.workers.dev
- [ ] Протестирован: `curl "URL/?url=MERCARI_IMAGE"`

### Railway integration:
- [ ] Обновлен image_utils.py
- [ ] Обновлен core.py (если нужно)
- [ ] Добавлен CLOUDFLARE_WORKER_URL в Railway variables
- [ ] Deployed на Railway: `railway up -s Worker --detach`
- [ ] Проверены логи: `railway logs -s Worker`
- [ ] Проверена база данных (есть новые items с image_data)
- [ ] Проверен Web UI (фотографии показываются)

### Success metrics:
- [ ] Success rate > 70% (проверь в БД)
- [ ] Логи Worker показывают "✅ Image downloaded"
- [ ] Web UI показывает фотографии
- [ ] Telegram отправляет фотографии (если используется)

---

## Стоимость и лимиты - финальная сводка:

| Параметр | Значение |
|----------|----------|
| **Цена** | $0 (free tier) |
| **Requests/day** | 100,000 (твой usage: ~10,000) |
| **Success rate** | 70-85% (зависит от Cloudflare блокировки) |
| **Latency** | ~200-500ms per image |
| **Setup time** | 20-30 минут |
| **Maintenance** | Почти нет (serverless) |

**Вывод:** Cloudflare Worker - это лучший вариант для начала. Если не сработает (success rate < 50%), переходи на ScraperAPI ($49/month, 95-99% success).

---

Готово! Выбирай команду для начала:

```bash
# Начать setup Cloudflare Worker
mkdir ~/mercari-image-proxy && cd ~/mercari-image-proxy && wrangler init
```

Нужна помощь с каким-то шагом?
