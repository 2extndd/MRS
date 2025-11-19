# 🔧 Railway Worker Service - Пересоздание

## Проблема
Worker service застрял на коммите `3fc6bfed` (от `railway up`).
Простой redeploy НЕ помогает - нет выбора новых коммитов.

## Решение: Удалить и создать заново

### Шаг 1: Сохранить текущие Environment Variables

В Railway Dashboard → worker service → Variables:

**Скопируй все эти переменные (понадобятся для нового service):**
```
DATABASE_URL=postgresql://...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_THREAD_ID=... (если есть)
RAILWAY_SERVICE_NAME=worker
RAILWAY_PROJECT_ID=...
RAILWAY_SERVICE_ID=...
PROXY_ENABLED=...
PROXY_LIST=...
... (и любые другие custom variables)
```

### Шаг 2: Удалить старый Worker Service

1. Railway Dashboard → worker service
2. Settings → Danger Zone
3. "Remove Service from All Environments"
4. Подтвердить удаление

### Шаг 3: Создать новый Worker Service

1. В проекте "tender-healing" нажать **"+ New"**
2. Выбрать **"GitHub Repo"**
3. Найти и выбрать репозиторий (MRS или как называется)
4. Railway автоматически определит Python проект

### Шаг 4: Настроить Worker Service

#### A. Settings → General
- **Service Name:** `worker`
- **Start Command:** `python3 simple_telegram_worker.py`

#### B. Settings → Environment
- **Environment:** `production`

#### C. Settings → Variables
Вставить все скопированные переменные из Шага 1:
- `DATABASE_URL` (ВАЖНО! Скопируй из web service если потерял)
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `RAILWAY_SERVICE_NAME=worker`
- Остальные...

#### D. Settings → Deployments (ВАЖНО!)
- **Enable Auto Deploy:** ✅ ВКЛ
- **Branch:** `main`
- **Deploy on Push:** ✅ ВКЛ

Это решит проблему с застрявшим коммитом в будущем!

### Шаг 5: Deploy

1. Railway автоматически начнёт deploy
2. Или нажми "Deploy" вручную
3. Подожди ~2-3 минуты

### Шаг 6: Проверка

Проверь логи worker:
```bash
railway logs --service worker | grep "Getting full details"
```

Должны увидеть:
```
📦 Getting full details for item: m89111205335
   Size: XS
   Photo: ORIGINAL
✅ NEW item added to DB: Nike Air Max...
```

Если видишь эти строки - **ВСЁ РАБОТАЕТ!** ✅

---

## Альтернатива: Настроить Auto-Deploy для существующего Worker

Если не хочешь удалять worker:

1. Railway Dashboard → worker service
2. Settings → Source → "Change Source"
3. Выбрать GitHub Repository (тот же)
4. Branch: `main`
5. ✅ Enable "Deploy on Push"
6. Save

Затем:
1. Settings → Deployments → "Redeploy"
2. Выбрать latest commit (2a24a72)

Это должно заставить worker использовать новый коммит.

---

## После успешного деплоя

- Items будут добавляться в БД
- Размеры будут извлекаться
- Фото в высоком качестве (orig/large)
- Telegram уведомления с правильными данными

**Worker будет автоматически деплоиться при каждом push!** 🚀
