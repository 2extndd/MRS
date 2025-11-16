# MercariSearcher - Quick Start Guide

## ⚡ Быстрый Старт (3 минуты)

### 1. Откройте Railway Dashboard
**https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d**

### 2. Добавьте PostgreSQL
- Нажмите **"+ New"** → **"Database"** → **"PostgreSQL"**

### 3. Добавьте GitHub Repo (создаст первый сервис)
- Нажмите **"+ New"** → **"GitHub Repo"**
- Выберите: **`2extndd/MRS`**
- Branch: **`main`**

### 4. Настройте WEB сервис
- Переименуйте в **`web`**
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --timeout 30 wsgi:application`
- **Networking** → **Generate Domain** (включить публичный доступ)
- **Variables** → Добавьте переменные ниже ⬇️

### 5. Создайте WORKER сервис
- **"+ New"** → **"Empty Service"** → Назовите **`worker`**
- **Settings** → **Source** → **Connect Repo** → **`2extndd/MRS`**
- **Start Command**: `python mercari_notifications.py worker`
- **Variables** → Добавьте те же переменные ⬇️

---

## 📋 Environment Variables (для ОБОИХ сервисов)

```bash
TELEGRAM_BOT_TOKEN=8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw
TELEGRAM_CHAT_ID=-4997297083
DISPLAY_CURRENCY=USD
USD_CONVERSION_RATE=0.0067
SEARCH_INTERVAL=300
MAX_ITEMS_PER_SEARCH=50
REQUEST_DELAY_MIN=1.5
REQUEST_DELAY_MAX=3.5
LOG_LEVEL=INFO
```

---

## ✅ Проверка

### WEB сервис логи должны показать:
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:3000
```

### WORKER сервис логи должны показать:
```
[INFO] MercariSearcher v1.0.0 Worker Starting...
[INFO] Database: PostgreSQL connected
[INFO] Telegram: Bot connected
[INFO] Scheduler: Started (interval: 300s)
```

### Откройте Web UI
- Скопируйте публичный URL **web** сервиса
- Перейдите на `/queries`
- Добавьте первый поиск

---

## 🎯 Пример Первого Поиска

```
Name: Julius Denim
URL: https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
Telegram Chat ID: -4997297083
Active: ✓
```

---

## 📱 Telegram Уведомления

Бот будет отправлять уведомления каждые **5 минут** в чат ID: **-4997297083**

Формат уведомления:
```
👔 JULIUS - Archive Distressed Denim Jacket

💴 $98.50 (¥14,700)
📏 Size: 2 (M)
🏷️ Condition: Used - Good

[Open Mercari] кнопка
```

---

## 🔗 Ссылки

- **Railway Dashboard**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **GitHub Repo**: https://github.com/2extndd/MRS
- **Подробная инструкция**: см. [RAILWAY_MANUAL_SETUP.md](RAILWAY_MANUAL_SETUP.md)

---

**Готово! Ваш MercariSearcher будет сканировать Mercari.jp автоматически! 🚀**
