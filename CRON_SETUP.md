# Настройка автоматического цикла поиска через внешний Cron сервис

## Проблема
Railway не поддерживает встроенные Cron jobs на бесплатном плане. Попытки запустить scheduler в фоновом потоке (threading) оказались ненадежными - поток периодически умирает и не перезапускается.

## Решение
Используем **внешний бесплатный cron сервис** (например, [cron-job.org](https://cron-job.org)) для периодического вызова API endpoint, который запускает цикл поиска.

## Как это работает

1. **Flask приложение** предоставляет API endpoint `/api/trigger-search`
2. **Внешний cron сервис** вызывает этот endpoint каждые N минут (например, каждые 5 минут)
3. **Endpoint запускает** один цикл поиска (search_cycle + telegram_cycle) в фоновом потоке
4. **HTTP ответ возвращается сразу**, а цикл поиска продолжается в фоне

## Шаг 1: Настройка Railway (опционально - для безопасности)

Добавьте secret token в Railway Environment Variables:

```bash
railway variables set CRON_SECRET_TOKEN=<ваш_случайный_токен>
```

Например:
```bash
railway variables set CRON_SECRET_TOKEN=$(openssl rand -hex 32)
```

Это защитит endpoint от несанкционированных вызовов.

## Шаг 2: Регистрация на cron-job.org

1. Перейдите на https://cron-job.org
2. Создайте бесплатный аккаунт
3. Подтвердите email

## Шаг 3: Создание Cron Job

1. В дашборде нажмите **"Create cronjob"**
2. Заполните форму:
   - **Title**: `Mercari Search Cycle`
   - **Address**: `https://your-app.up.railway.app/api/trigger-search`
   - **Schedule**: Выберите интервал (например, `*/5 * * * *` для каждых 5 минут)
   - **Request method**: `POST` (или `GET`, оба поддерживаются)
   - **Authentication** (если настроили CRON_SECRET_TOKEN):
     - Метод 1: **Custom HTTP Headers**
       - Header: `X-Cron-Token`
       - Value: `<ваш_токен_из_railway>`
     - Метод 2: **Query Parameter**
       - URL: `https://your-app.up.railway.app/api/trigger-search?token=<ваш_токен>`

3. **Сохраните** Cron job

## Шаг 4: Тестирование

### Вручную через curl

Без токена:
```bash
curl -X POST https://your-app.up.railway.app/api/trigger-search
```

С токеном (в header):
```bash
curl -X POST https://your-app.up.railway.app/api/trigger-search \
  -H "X-Cron-Token: YOUR_TOKEN"
```

С токеном (в query):
```bash
curl -X POST "https://your-app.up.railway.app/api/trigger-search?token=YOUR_TOKEN"
```

### Ожидаемый ответ

```json
{
  "success": true,
  "message": "Search cycle started",
  "triggered_at": "2025-11-26T12:00:00.123456"
}
```

### Проверка логов

```bash
railway logs --service web | grep "\[API\]"
```

Должны увидеть:
```
[API] Search cycle triggered via API at 2025-11-26 12:00:00
[API] Creating MercariNotificationApp instance...
[API] Running search cycle...
[API] Running Telegram notification cycle...
[API] ✅ Search cycle completed successfully
```

## Альтернативные бесплатные Cron сервисы

Если cron-job.org не подходит, можно использовать:

1. **EasyCron** - https://www.easycron.com (бесплатно до 100 заданий)
2. **cron-job.de** - https://console.cron-job.org (бесплатно)
3. **UptimeRobot** - https://uptimerobot.com (мониторинг с HTTP запросами каждые 5 мин)
4. **Healthchecks.io** - https://healthchecks.io (пинги с HTTP calls)
5. **GitHub Actions** - можно настроить workflow с cron расписанием

## Рекомендуемые интервалы

- **Частый поиск**: каждые 5 минут (`*/5 * * * *`)
- **Средний поиск**: каждые 15 минут (`*/15 * * * *`)
- **Редкий поиск**: каждый час (`0 * * * *`)

## Преимущества этого подхода

✅ **Надежность** - внешний cron сервис специализируется на периодических задачах
✅ **Бесплатно** - не требует платного Railway плана
✅ **Просто** - минимум кода, легко отлаживать
✅ **Масштабируемость** - можно добавить несколько cron jobs для разных задач
✅ **Мониторинг** - cron сервис показывает историю вызовов и ошибки

## Недостатки

❌ **Внешняя зависимость** - полагаемся на сторонний сервис
❌ **Не мгновенно** - минимальный интервал обычно 5 минут (для бесплатных планов)

## Отладка

Если cron job не работает:

1. **Проверьте endpoint вручную через curl**
2. **Посмотрите Railway logs**: `railway logs --service web`
3. **Проверьте историю в cron-job.org** - там показываются HTTP ответы
4. **Убедитесь, что токен правильный** (если используете аутентификацию)
5. **Проверьте, что Railway приложение не спит** (на бесплатном плане может засыпать)

## Миграция со старого подхода

Старый код (threading в wsgi.py) был удален. Если нужно вернуться к нему:

```bash
git log --all --grep="threading" --oneline
git show <commit_hash>
```

Но это **не рекомендуется** - threading подход был ненадежным.
