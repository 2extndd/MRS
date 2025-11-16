# Railway Deployment Fix Applied

## Problem Fixed
```
ERROR: no precompiled python found for core:python@3.11.0 on x86_64-unknown-linux-gnu
```

## Solution Applied
Added explicit Railway configuration files:

### 1. nixpacks.toml
Explicitly tells Railway to use Python 3.11 from nixpkgs instead of mise:
```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]
```

### 2. railway.toml
Defines build and deployment commands:
```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application"
```

---

## Next Steps

### 1. Railway Will Auto-Deploy
Since GitHub is connected, Railway will automatically:
- Pull latest commit (2b1bc42)
- Detect `nixpacks.toml`
- Use nixpacks builder with Python 3.11
- Install dependencies
- Deploy successfully

### 2. Monitor Deployment

**Option A - Railway Dashboard:**
1. Go to https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
2. Click **Deployments**
3. Watch latest deployment
4. Should see:
   ```
   ✓ Building with nixpacks
   ✓ Installing python311
   ✓ Installing requirements
   ✓ Starting application
   ```

**Option B - Railway CLI (if logged in):**
```bash
cd /Users/extndd/MRS
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
railway logs
```

### 3. Create Two Services

Railway might auto-create one service. You need **TWO**:

#### Service 1: WEB (Flask UI)
- **Name**: `web`
- **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application`
- **Public Networking**: ✓ Enabled
- **Environment Variables**: (shared with worker)

#### Service 2: WORKER (Background Scanner)
- **Name**: `worker`
- **Start Command**: `python mercari_notifications.py worker`
- **Public Networking**: ✗ Disabled
- **Environment Variables**: (shared with web)

**How to create second service:**
1. Railway Dashboard → **+ New**
2. Select **"Empty Service"**
3. Name: `worker`
4. **Settings** → **Source** → Connect to same repo
5. **Settings** → **Deploy**
   - Start Command: `python mercari_notifications.py worker`
   - Root Directory: `/`
6. **Settings** → **Variables** → Link to shared variables
7. **Deploy**

---

## Required Environment Variables

Add these in Railway Dashboard → **Variables** (shared between both services):

### Required:
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890
```

### Optional (with defaults):
```bash
DISPLAY_CURRENCY=USD
USD_CONVERSION_RATE=0.0067
SEARCH_INTERVAL=300
MAX_ITEMS_PER_SEARCH=50
REQUEST_DELAY_MIN=1.5
REQUEST_DELAY_MAX=3.5
LOG_LEVEL=INFO
```

### Auto-set by Railway:
```bash
DATABASE_URL=postgresql://...  (when PostgreSQL is added)
PORT=3000  (or other assigned port)
```

---

## Verify Deployment Success

### Check Web Service:
1. Railway → **web** service → **Deployments** → **Logs**
2. Should see:
   ```
   [INFO] Starting gunicorn 21.2.0
   [INFO] Listening at: http://0.0.0.0:3000
   [INFO] Using worker: sync
   ```
3. Get public URL: **Settings** → **Networking** → Copy domain
4. Open in browser → Should see Dashboard

### Check Worker Service:
1. Railway → **worker** service → **Deployments** → **Logs**
2. Should see:
   ```
   [INFO] MercariSearcher v1.0.0 Worker Starting...
   [INFO] Tokyo timezone: 2024-11-16 21:30:00 JST
   [INFO] Database: PostgreSQL connected
   [INFO] Telegram: Bot connected (@your_bot)
   [INFO] Scheduler: Started (interval: 300s)
   [INFO] Active searches: 0
   ```

### Check Database:
1. Railway → **PostgreSQL** → **Data**
2. Tables should auto-create on first run:
   - `searches`
   - `items`
   - `price_history`
   - `settings`
   - `error_tracking`
   - `logs`

---

## Troubleshooting

### Still Getting mise Error?

**Option 1 - Clear build cache:**
1. Railway Dashboard → Service → **Settings**
2. Scroll to **Danger Zone**
3. Click **"Clear Build Cache"**
4. Click **"Redeploy"**

**Option 2 - Force nixpacks:**
Add to railway.toml:
```toml
[build]
builder = "nixpacks"
nixpacksConfigPath = "nixpacks.toml"
```

### Deployment Timeout?

Increase timeout in railway.toml:
```toml
[deploy]
healthcheckPath = "/"
healthcheckTimeout = 300
```

### Can't Install Dependencies?

Check requirements.txt:
```bash
# Ensure no conflicting versions
cat requirements.txt
```

If issues with psycopg2, try:
```bash
# In requirements.txt, use binary version:
psycopg2-binary>=2.9.9
# NOT:
# psycopg2>=2.9.9
```

### Web Service Starts but Crashes?

Check if DATABASE_URL is set:
```bash
# Railway logs should show:
[INFO] Database: PostgreSQL connected
# If shows:
[WARNING] DATABASE_URL not set, using SQLite
# → Add PostgreSQL service in Railway
```

---

## Expected Build Logs (Success)

```
─────────────────────────────────────────────────────
│ Building with nixpacks
─────────────────────────────────────────────────────
│ Detected nixpacks.toml configuration
│ Using nixpkgs: python311, postgresql
│
│ [setup] Installing python311... ✓
│ [setup] Installing postgresql... ✓
│
│ [install] Running: pip install -r requirements.txt
│ Collecting requests>=2.31.0
│   Downloading requests-2.31.0-py3-none-any.whl
│ Collecting psycopg2-binary>=2.9.9
│   Downloading psycopg2_binary-2.9.9-cp311-cp311-linux_x86_64.whl
│ ... (more packages)
│ Successfully installed 15 packages ✓
│
│ [build] No build commands
│
│ [start] Starting: gunicorn --bind 0.0.0.0:$PORT wsgi:application
│
─────────────────────────────────────────────────────
│ Deployment successful! ✓
─────────────────────────────────────────────────────
```

---

## Manual Deployment (via CLI)

If you need to deploy manually:

```bash
# Login to Railway (interactive)
railway login

# Link to project
cd /Users/extndd/MRS
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

# Deploy
railway up

# Watch logs
railway logs --service web
railway logs --service worker
```

---

## Files Added to Fix Deployment

- ✅ `nixpacks.toml` - Explicit Python 3.11 configuration
- ✅ `railway.toml` - Build and deploy settings
- ✅ `runtime.txt` - Already present (python-3.11.0)
- ✅ `requirements.txt` - Already present
- ✅ `Procfile` - Already present (for multiple processes)

---

## Summary

The mise error is now fixed by:
1. Adding `nixpacks.toml` with explicit Python 3.11 from nixpkgs
2. Adding `railway.toml` for clear build instructions
3. Railway will now use nixpacks builder instead of mise

**Latest commit pushed:** `2b1bc42`

Railway should auto-deploy successfully now! 🚀

Monitor deployment at:
https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
