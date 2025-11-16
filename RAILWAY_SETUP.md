# Railway Deployment Guide for MercariSearcher

## Railway Project ID
`f17da572-14c9-47b5-a9f1-1b6d5b6dea2d`

---

## Step 1: Railway CLI Setup (Optional)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Link to project
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
```

---

## Step 2: PostgreSQL Database Setup

### Via Railway Dashboard:

1. Go to https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
2. Click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically set `DATABASE_URL` environment variable
4. Database will be created and connected

### Verify Connection:
```bash
# Via CLI (optional)
railway run python -c "from db import get_db; db = get_db(); print('DB Connected:', db.is_postgres)"
```

---

## Step 3: Environment Variables Configuration

Go to **Settings** → **Variables** in Railway dashboard and add:

### Required Variables:

```bash
# Telegram Bot (REQUIRED)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890

# Optional: For topic-based group chats
TELEGRAM_THREAD_ID=123
```

### Optional Variables (with defaults):

```bash
# Currency Display
DISPLAY_CURRENCY=USD
USD_CONVERSION_RATE=0.0067

# Search Settings
SEARCH_INTERVAL=300
MAX_ITEMS_PER_SEARCH=50

# Rate Limiting
REQUEST_DELAY_MIN=1.5
REQUEST_DELAY_MAX=3.5

# Proxy Settings (if needed)
PROXY_ENABLED=false
PROXY_LIST=http://proxy1:8080,http://proxy2:8080

# Web UI
SECRET_KEY=your_random_secret_key_here
LOG_LEVEL=INFO
```

### How to Get Telegram Bot Token:

1. Open Telegram and find **@BotFather**
2. Send `/newbot` and follow instructions
3. Copy the token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### How to Get Chat ID:

**Method 1 - Using @userinfobot:**
1. Add **@userinfobot** to your Telegram
2. Send any message to bot
3. Copy the ID (looks like `-1001234567890` for groups or `1234567890` for personal)

**Method 2 - Using getUpdates:**
1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":-1001234567890}` in response

### How to Get Thread ID (for topics):

1. Enable topics in your group
2. Create a topic/thread
3. Send a message to that topic
4. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Find `"message_thread_id":123` in response

---

## Step 4: Service Configuration

Railway should auto-detect the `Procfile` and create **2 services**:

### Service 1: Web (Gunicorn + Flask UI)
```
web: gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
```
- **Port**: Railway provides `$PORT` automatically
- **Health Check**: `GET /` (Flask dashboard)
- **Public Domain**: Railway will assign a domain (e.g., `mrs-production.up.railway.app`)

### Service 2: Worker (Background Scanner)
```
worker: python mercari_notifications.py worker
```
- **No HTTP port** (background process)
- **Runs scheduler** that scans Mercari.jp
- **Sends Telegram notifications**

### Manual Service Creation (if needed):

If Railway doesn't auto-create both services:

1. **For Web Service**:
   - Click **"+ New"** → **"Empty Service"**
   - Name: `web`
   - **Settings** → **Deploy**
   - Start Command: `gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application`
   - Enable **Public Networking**

2. **For Worker Service**:
   - Click **"+ New"** → **"Empty Service"**
   - Name: `worker`
   - **Settings** → **Deploy**
   - Start Command: `python mercari_notifications.py worker`
   - **Disable Public Networking**

---

## Step 5: Deploy from GitHub

### Automatic Deployment:

1. Railway dashboard → **Settings** → **Service**
2. Click **"Connect Repo"**
3. Select `2extndd/MRS` repository
4. **Branch**: `main`
5. Click **"Deploy"**

Railway will:
- Detect `requirements.txt` and install dependencies
- Use `runtime.txt` for Python 3.11
- Read `Procfile` for process commands
- Auto-deploy on every `git push` to main

### Manual Deployment (via CLI):

```bash
cd /Users/extndd/MRS
railway up
```

---

## Step 6: Verify Deployment

### Check Web Service:

1. Go to Railway dashboard → **web** service
2. Click **Settings** → **Networking**
3. Copy the public URL (e.g., `https://mrs-production.up.railway.app`)
4. Open in browser → Should see Flask dashboard

### Check Worker Service:

1. Go to Railway dashboard → **worker** service
2. Click **Deployments** → **Logs**
3. Should see:
   ```
   [INFO] MercariSearcher v1.0.0 Worker Starting...
   [INFO] Tokyo timezone: 2024-11-16 21:00:00 JST
   [INFO] Database: PostgreSQL connected
   [INFO] Telegram: Connected
   [INFO] Scheduler: Started
   [INFO] Active searches: 0
   ```

### Check Database:

```bash
# Via Railway dashboard
# PostgreSQL service → Data → Connect

# Or via CLI
railway connect postgresql

# Test connection in Python
railway run python check_db.py
```

---

## Step 7: Add Your First Search

### Via Web UI:

1. Open `https://your-railway-domain.up.railway.app/queries`
2. Paste Mercari URL:
   ```
   https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
   ```
3. Enter search name: `Julius Under $120`
4. Enter Telegram Chat ID
5. (Optional) Enter Thread ID for topics
6. Click **"Add Search"**

### Via Database (CLI):

```bash
railway run python -c "
from db import get_db
db = get_db()
db.add_search(
    name='Julius Under $120',
    url='https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621',
    telegram_chat_id='-1001234567890',
    telegram_thread_id='123'  # Optional
)
print('Search added!')
"
```

---

## Step 8: Monitor & Manage

### View Logs:

**Web Service Logs:**
- Railway dashboard → **web** → **Deployments** → **Logs**
- Shows Flask app logs, HTTP requests

**Worker Service Logs:**
- Railway dashboard → **worker** → **Deployments** → **Logs**
- Shows scanner activity, Telegram sends, errors

**Database Logs (via Web UI):**
- Open `https://your-domain.up.railway.app/logs`
- Filter by level (INFO, WARNING, ERROR)

### View Dashboard:

- Open `https://your-domain.up.railway.app/`
- See:
  - Uptime
  - Total scans
  - Items found
  - API requests
  - Recent items

### Force Scan:

**Via Web UI:**
- Dashboard → **"Force Scan All"** button

**Via API:**
```bash
curl -X POST https://your-domain.up.railway.app/api/force-scan
```

### Manage Searches:

- **View All**: `https://your-domain.up.railway.app/queries`
- **Edit**: Click search → Update thread ID, activate/deactivate
- **Delete**: Click **X** button
- **Add**: Click **"Add New Search"**

---

## Step 9: Railway Auto-Redeploy (Optional)

For automatic redeploy on critical errors:

### Get Railway API Token:

1. Railway dashboard → **Account Settings** → **Tokens**
2. Click **"Create Token"**
3. Copy token

### Add to Environment Variables:

```bash
RAILWAY_TOKEN=your_railway_api_token
RAILWAY_PROJECT_ID=f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
RAILWAY_SERVICE_ID=your_service_id  # Get from URL or CLI

# Trigger redeploy after N errors in 1 hour
MAX_ERRORS_BEFORE_REDEPLOY=5
```

### How It Works:

- If 5+ critical errors occur in 1 hour (403, 429, 500+)
- `railway_redeploy.py` triggers Railway GraphQL API
- Service automatically redeploys
- Useful for IP bans or rate limits

---

## Step 10: Scaling & Optimization

### Increase Resources (if needed):

1. Railway dashboard → **Service Settings** → **Resources**
2. Upgrade plan for more:
   - RAM (default: 512MB → 8GB+)
   - CPU (default: shared → dedicated)
   - Concurrent requests

### Add Proxies (if Mercari blocks):

```bash
# Add to environment variables
PROXY_ENABLED=true
PROXY_LIST=http://proxy1.example.com:8080,http://proxy2.example.com:8080,socks5://proxy3:1080

# Proxies will auto-rotate every 100 requests
# Failed proxies are auto-removed
```

### Adjust Scan Interval:

**Via Web UI:**
- Open `https://your-domain.up.railway.app/config`
- Change **"Search Interval"** (seconds)
- Save

**Via Environment Variables:**
```bash
SEARCH_INTERVAL=600  # 10 minutes
```

---

## Troubleshooting

### Web Service Not Starting:

**Check Logs:**
```
railway logs --service web
```

**Common Issues:**
- `PORT` not set → Railway should auto-set
- `DATABASE_URL` not found → Add PostgreSQL service
- Import errors → Check `requirements.txt`

**Fix:**
```bash
# Verify Procfile
cat Procfile

# Should output:
# web: gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
```

### Worker Service Not Scanning:

**Check Logs:**
```
railway logs --service worker
```

**Common Issues:**
- No active searches → Add search via Web UI
- Telegram token invalid → Check `TELEGRAM_BOT_TOKEN`
- Database not connected → Check PostgreSQL service

**Test Locally:**
```bash
# Set env vars
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export DATABASE_URL=your_railway_postgres_url

# Run worker
python mercari_notifications.py worker
```

### Telegram Not Sending:

**Verify Bot Token:**
```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

**Verify Chat ID:**
```bash
# Send test message via API
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Test from MercariSearcher"
```

**Check Bot Permissions:**
- Bot must be added to group/channel
- Bot needs **"Send Messages"** permission
- For topics: Bot needs **"Manage Topics"** permission

### Database Connection Failed:

**Check PostgreSQL Service:**
- Railway dashboard → **PostgreSQL** → **Connect**
- Copy `DATABASE_URL`

**Test Connection:**
```bash
railway run python -c "
import psycopg2
import os
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
print('✓ PostgreSQL Connected')
conn.close()
"
```

### Mercari Blocking Requests:

**Symptoms:**
- 403 Forbidden errors
- 429 Too Many Requests

**Solutions:**

1. **Increase Delay:**
   ```bash
   REQUEST_DELAY_MIN=3.0
   REQUEST_DELAY_MAX=6.0
   ```

2. **Enable Proxies:**
   ```bash
   PROXY_ENABLED=true
   PROXY_LIST=your_proxies_here
   ```

3. **Decrease Scan Frequency:**
   ```bash
   SEARCH_INTERVAL=900  # 15 minutes
   ```

---

## Useful Commands

```bash
# View logs
railway logs --service web
railway logs --service worker

# Open web UI
railway open

# Connect to database
railway connect postgresql

# Run command in Railway environment
railway run python check_db.py

# View environment variables
railway variables

# Add environment variable
railway variables set TELEGRAM_BOT_TOKEN=your_token

# Deploy
railway up

# Redeploy current version
railway redeploy

# Check service status
railway status
```

---

## Security Best Practices

1. **Never commit `.env` file** → Already in `.gitignore`
2. **Use Railway environment variables** for secrets
3. **Rotate Telegram bot token** periodically
4. **Use strong `SECRET_KEY`** for Flask sessions
5. **Enable Railway IP whitelisting** (if needed)
6. **Monitor logs** for suspicious activity

---

## Support

- **GitHub Issues**: https://github.com/2extndd/MRS/issues
- **Railway Docs**: https://docs.railway.app
- **Telegram Bot API**: https://core.telegram.org/bots/api

---

## Railway Dashboard Quick Links

- **Project**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **Deployments**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/deployments
- **Settings**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/settings
- **Metrics**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/metrics

---

**Your MercariSearcher is ready for Railway deployment!**
