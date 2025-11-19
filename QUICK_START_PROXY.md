# 🚀 Quick Start: Добавление прокси в MercariSearcher

## ⚡ Быстрый старт (5 минут)

### 1️⃣ Скачать список прокси (115 шт)

```bash
curl "https://proxy.webshare.io/api/v2/proxy/list/download/ajdyrzbcopyfalyezgxfgiszewzcrotpbdtpnkjn/-/any/username/direct/-/?plan_id=12074988" > proxies.txt
```

### 2️⃣ Добавить в Railway

**Railway Dashboard:**
1. Открыть: https://railway.app/dashboard
2. Проект MRS → Worker service → Variables
3. Добавить переменные:

```
PROXY_ENABLED=true
PROXY_LIST=<вставить содержимое proxies.txt через запятую>
```

**Или через Railway CLI:**
```bash
railway variables set PROXY_ENABLED=true
railway variables set PROXY_LIST="$(cat proxies.txt | tr '\n' ',')"
```

### 3️⃣ Деплой

```bash
railway up --service worker
railway up --service web
```

### 4️⃣ Проверка

```bash
railway logs --service worker | head -50
```

**Ожидаемые логи:**
```
✓ ProxyManager initialized with 115 proxies
✓ Validating 115 proxies...
✓ Proxy validation complete: 110-115 working
✓ 📡 Using proxy for image download
✓ ✅ Image encoded
```

### 5️⃣ Мониторинг

```bash
curl https://web-production-fe38.up.railway.app/api/proxy/stats
```

---

## 📊 Статус проекта

**Текущий коммит:** `81ab320`  
**Прокси протестированы:** ✅ 10/10 работают (100%)  
**Готовность:** ✅ Production Ready  

---

## 📚 Документация

- `PROXY_IMPLEMENTATION_GUIDE.md` - полное руководство (543 строки)
- `SESSION_REPORT_PROXY_SYSTEM.md` - отчет о работе (581 строка)
- `PROXY_TEST_RESULTS.md` - результаты тестирования (213 строк)

---

**Вопросы?** Читайте PROXY_IMPLEMENTATION_GUIDE.md
