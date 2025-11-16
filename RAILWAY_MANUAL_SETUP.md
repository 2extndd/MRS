# Railway Manual Setup Guide

Since Railway CLI requires interactive login, follow these steps via Railway Dashboard.

---

## STEP 1: Open Railway Dashboard

Go to: **https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d**

---

## STEP 2: Connect GitHub Repository

### If not already connected:

1. Click **"+ New"** in Railway Dashboard
2. Select **"GitHub Repo"**
3. Choose **"2extndd/MRS"**
4. Branch: **main**
5. Click **"Deploy"**

### If already connected but not deploying:

1. Go to existing service
2. Click **"Settings"**
3. **"Source"** tab
4. Verify connected to: `2extndd/MRS` on branch `main`
5. Click **"Redeploy"**

---

## STEP 3: Check Current Deployment Status

### Look for these files in Railway build logs:

Railway should detect:
- ✓ `nixpacks.toml` → Uses nixpacks builder with Python 3.11
- ✓ `railway.toml` → Build and deploy configuration
- ✓ `runtime.txt` → Python version
- ✓ `requirements.txt` → Dependencies

### Expected Build Process:

```
Building...
├─ Detected nixpacks.toml
├─ Using nixpkgs: python311, postgresql
├─ Installing dependencies from requirements.txt
├─ Starting with: gunicorn --bind 0.0.0.0:$PORT wsgi:application
└─ ✓ Deployment successful
```

### If you see mise error:

```
ERROR: no precompiled python found for core:python@3.11.0
```

**Solution:** Clear build cache:
1. Service → **Settings**
2. Scroll to **Danger Zone**
3. Click **"Clear Build Cache"**
4. Click **"Redeploy"**

---

## STEP 4: Add PostgreSQL Database

1. In Railway Dashboard, click **"+ New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Wait for provisioning (1-2 minutes)

**Railway will automatically:**
- Create PostgreSQL instance
- Set `DATABASE_URL` environment variable
- Connect to your services

---

## STEP 5: Add Environment Variables

1. Click **"Variables"** tab (in your service or shared variables)
2. Add the following variables:

### Required Variables:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**How to get these:**
- **Bot Token**: Message @BotFather on Telegram → `/newbot`
- **Chat ID**: Message @userinfobot → `/start` → Copy ID

### Optional Variables (recommended):

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
DATABASE_URL=postgresql://...  (set by PostgreSQL service)
PORT=3000  (or assigned port)
```

---

## STEP 6: Create Two Services

Railway needs **TWO separate services** for this project:

### Service 1: WEB (Flask Dashboard)

**Purpose:** Web UI for managing searches and viewing items

**Configuration:**
1. Click **"+ New"** → **"Empty Service"**
2. Name: `web`
3. **Settings** → **Source**:
   - Connect to: `2extndd/MRS`
   - Branch: `main`
4. **Settings** → **Deploy**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application`
5. **Settings** → **Networking**:
   - Enable **"Public Networking"**
   - Generate Domain (or use custom)
6. **Settings** → **Variables**:
   - Link to shared variables or copy all env vars
7. Click **"Deploy"**

**Expected Output in Logs:**
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:3000
[INFO] Booting worker with pid: 1
```

**Test:**
- Open Public Domain → Should see Dashboard

### Service 2: WORKER (Background Scanner)

**Purpose:** Scans Mercari.jp and sends Telegram notifications

**Configuration:**
1. Click **"+ New"** → **"Empty Service"**
2. Name: `worker`
3. **Settings** → **Source**:
   - Connect to: `2extndd/MRS`
   - Branch: `main`
4. **Settings** → **Deploy**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python mercari_notifications.py worker`
5. **Settings** → **Networking**:
   - **Disable** Public Networking (no HTTP port needed)
6. **Settings** → **Variables**:
   - Link to shared variables or copy all env vars
7. Click **"Deploy"**

**Expected Output in Logs:**
```
[INFO] MercariSearcher v1.0.0 Worker Starting...
[INFO] Tokyo timezone: 2024-11-16 21:30:00 JST
[INFO] Database: PostgreSQL connected
[INFO] Telegram: Bot connected (@your_bot_name)
[INFO] Scheduler: Started (interval: 300s)
[INFO] Active searches: 0
```

---

## STEP 7: Verify Both Services Are Running

### Check WEB Service:

1. Railway Dashboard → **web** service
2. **Deployments** tab → Latest deployment should be green ✓
3. Click **"View Logs"**
4. Should see Gunicorn started successfully
5. **Settings** → **Networking** → Copy Public Domain
6. Open in browser → Should see MercariSearcher Dashboard

### Check WORKER Service:

1. Railway Dashboard → **worker** service
2. **Deployments** tab → Latest deployment should be green ✓
3. Click **"View Logs"**
4. Should see:
   - Database connected
   - Telegram bot connected
   - Scheduler started
5. No errors in logs

### Check PostgreSQL:

1. Railway Dashboard → **PostgreSQL** service
2. **Data** tab → Should see database name
3. Click **"Connect"** → Copy connection string
4. Verify `DATABASE_URL` is in Variables tab of both web and worker

---

## STEP 8: Add Your First Search

### Via Web UI (Recommended):

1. Open your Railway Public Domain (web service)
2. Navigate to: `/queries`
3. Click **"Add New Search"**
4. Fill in the form:

**Example:**
```
Name: Julius Denim Under $120
URL: https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
Telegram Chat ID: -1001234567890
Telegram Thread ID: (leave empty or add for topics)
Active: ✓ Checked
```

5. Click **"Add Search"**
6. Should see search in list

### Via Database (Advanced):

1. Railway Dashboard → PostgreSQL → **Data**
2. Click **"Query"**
3. Run:
```sql
INSERT INTO searches (name, url, telegram_chat_id, is_active)
VALUES (
  'Julius Denim Under $120',
  'https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621',
  '-1001234567890',
  true
);
```

---

## STEP 9: Monitor for Items

### Watch Worker Logs:

1. Railway Dashboard → **worker** service → **Logs**
2. Wait for next scan (default: 5 minutes)
3. Should see:
```
[INFO] Scanning search: Julius Denim Under $120
[INFO] Found 12 items from Mercari.jp
[INFO] New items: 3
[INFO] Sending Telegram notification for item: m63020522105
[INFO] Telegram notification sent successfully
```

### Check Telegram:

1. Open Telegram
2. Go to your chat/group
3. Should receive notification with:
   - Photo of item
   - Price (JPY + USD)
   - Brand, Size, Condition
   - Link to Mercari

### Check Web UI:

1. Open `/items` page
2. Should see found items
3. Can filter by search
4. View photos and details

---

## TROUBLESHOOTING

### Issue 1: Service Won't Start

**Symptoms:**
- Deployment fails
- Logs show import errors

**Solution:**
1. Check `requirements.txt` is present
2. Clear build cache (Settings → Danger Zone)
3. Redeploy

### Issue 2: Can't Connect to Database

**Symptoms:**
- Logs show: `WARNING: DATABASE_URL not set, using SQLite`

**Solution:**
1. Add PostgreSQL service
2. Verify `DATABASE_URL` in Variables tab
3. Restart both services

### Issue 3: Telegram Not Sending

**Symptoms:**
- Worker logs show "Telegram error"
- No notifications received

**Solution:**
1. Verify `TELEGRAM_BOT_TOKEN` is correct
   - Test: `https://api.telegram.org/bot<TOKEN>/getMe`
2. Verify `TELEGRAM_CHAT_ID` is correct
3. Ensure bot is added to group/chat
4. Check bot has "Send Messages" permission

### Issue 4: No Items Found

**Symptoms:**
- Worker logs show: `Found 0 items`

**Solution:**
1. Check search URL is valid (test in browser)
2. Check search is active in database
3. Check Mercari.jp isn't blocking requests
   - Enable proxies if needed
4. Check logs for 403/429 errors

### Issue 5: Build Cache Error (mise)

**Symptoms:**
```
ERROR: no precompiled python found for core:python@3.11.0
```

**Solution:**
1. Service → Settings → Danger Zone
2. Click **"Clear Build Cache"**
3. Verify `nixpacks.toml` exists in repo
4. Redeploy

---

## ALTERNATIVE: Use Railway CLI (Local)

If you want to use Railway CLI locally:

### Install Railway CLI:

```bash
# macOS
brew install railway

# Or npm
npm install -g @railway/cli
```

### Login:

```bash
railway login
# Opens browser for authentication
```

### Link Project:

```bash
cd /Users/extndd/MRS
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
```

### Deploy:

```bash
railway up
```

### Watch Logs:

```bash
railway logs --service web
railway logs --service worker
```

### Add Variables:

```bash
railway variables set TELEGRAM_BOT_TOKEN=your_token
railway variables set TELEGRAM_CHAT_ID=your_chat_id
```

---

## SUMMARY CHECKLIST

Use this checklist to ensure everything is set up:

- [ ] GitHub repository connected to Railway
- [ ] PostgreSQL service added
- [ ] Environment variables added (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
- [ ] WEB service created and deployed
- [ ] WORKER service created and deployed
- [ ] Both services show green ✓ in Deployments
- [ ] Web UI accessible via Public Domain
- [ ] Worker logs show "Scheduler: Started"
- [ ] At least one search added via Web UI
- [ ] Telegram bot responding

---

## USEFUL LINKS

- **Railway Project**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **GitHub Repo**: https://github.com/2extndd/MRS
- **Railway Docs**: https://docs.railway.app
- **Telegram Bot API**: https://core.telegram.org/bots/api

---

## NEED HELP?

1. Check `DEPLOYMENT_FIX.md` for common issues
2. Check Railway logs for specific error messages
3. Open issue on GitHub: https://github.com/2extndd/MRS/issues

---

**Your MercariSearcher is ready to deploy on Railway!**

Follow these steps in order, and you'll be scanning Mercari.jp in minutes! 🚀
