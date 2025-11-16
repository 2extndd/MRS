# Railway Setup Instructions - Ready to Deploy

## Your Tokens (Already Configured)

```bash
RAILWAY_TOKEN=4f9d1671-b934-4a05-a97f-1067c18d4eb7
TELEGRAM_BOT_TOKEN=8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw
TELEGRAM_CHAT_ID=-4997297083
PROJECT_ID=f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
```

---

## Step-by-Step Setup (5 minutes)

### Step 1: Open Railway Dashboard

Go to: **https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d**

---

### Step 2: Add PostgreSQL Database

1. Click **"+ New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Wait 30 seconds for provisioning
5. Done! ✓

---

### Step 3: Connect GitHub Repository

1. Click **"+ New"**
2. Select **"GitHub Repo"**
3. Find and select: **"2extndd/MRS"**
4. Branch: **main**
5. Click **"Add Service"**

This creates your first service. We need TWO services total.

---

### Step 4: Configure FIRST Service (WEB)

1. Click on the newly created service
2. Click **"Settings"**
3. Change name to: **web**
4. Scroll to **"Deploy"** section
5. **Start Command**:
   ```
   gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application
   ```
6. Click **"Networking"** tab
7. Click **"Generate Domain"** (enables public access)
8. Go to **"Variables"** tab
9. Add these variables (click "+ New Variable" for each):

```
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

10. Click **"Deploy"** or it will auto-deploy

---

### Step 5: Create SECOND Service (WORKER)

1. Go back to project view
2. Click **"+ New"** again
3. Select **"Empty Service"**
4. Name it: **worker**
5. Click **"Settings"** → **"Source"**
6. Click **"Connect Repo"**
7. Select: **"2extndd/MRS"**
8. Branch: **main**
9. Scroll to **"Deploy"** section
10. **Start Command**:
    ```
    python mercari_notifications.py worker
    ```
11. Go to **"Variables"** tab
12. Add the SAME variables as Step 4:

```
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

13. Click **"Deploy"**

---

### Step 6: Verify Deployments

#### Check WEB Service:

1. Go to **web** service
2. Click **"Deployments"**
3. Wait for green ✓ (1-2 minutes)
4. Click **"View Logs"**
5. Should see:
   ```
   [INFO] Starting gunicorn 21.2.0
   [INFO] Listening at: http://0.0.0.0:3000
   ```
6. Go to **"Settings"** → **"Networking"**
7. Copy the public domain (e.g., `web-production.up.railway.app`)
8. Open in browser → Should see MercariSearcher Dashboard ✓

#### Check WORKER Service:

1. Go to **worker** service
2. Click **"Deployments"**
3. Wait for green ✓ (1-2 minutes)
4. Click **"View Logs"**
5. Should see:
   ```
   [INFO] MercariSearcher v1.0.0 Worker Starting...
   [INFO] Tokyo timezone: 2024-11-16 ...
   [INFO] Database: PostgreSQL connected
   [INFO] Telegram: Bot connected
   [INFO] Scheduler: Started (interval: 300s)
   [INFO] Active searches: 0
   ```

#### Check PostgreSQL:

1. Go to **PostgreSQL** service
2. Click **"Data"** tab
3. Should see database name
4. Tables will auto-create on first run

---

### Step 7: Add Your First Search

1. Open the **web service public domain** in browser
2. Navigate to: `/queries`
3. Click **"Add New Search"**
4. Fill in the form:

```
Name: Julius Denim
URL: https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
Telegram Chat ID: -4997297083
Telegram Thread ID: (leave empty or add if using topics)
Active: ✓ Checked
```

5. Click **"Add Search"**

---

### Step 8: Wait for First Notification

- Scanner runs every **5 minutes** (300 seconds)
- Check worker logs to see: `[INFO] Scanning search: Julius Denim`
- When items found → Telegram notification sent to chat ID: `-4997297083`
- Check your Telegram chat for notifications!

---

## Expected Telegram Notification Format

```
👔 JULIUS - Archive Distressed Denim Jacket

💴 $98.50 (¥14,700)
📏 Size: 2 (M)
🏷️ Condition: Used - Good
📦 Shipping: ¥700
🔍 Search: Julius Denim

[Photo of item]

[Open Mercari] button
```

---

## Troubleshooting

### Web service not starting?

**Check logs for errors:**
- Missing `DATABASE_URL` → Make sure PostgreSQL is added
- Import errors → Check nixpacks.toml is in repo
- Port binding error → Railway sets `$PORT` automatically

**Solution:**
1. Settings → Danger Zone → **Clear Build Cache**
2. **Redeploy**

### Worker service not scanning?

**Check logs for:**
- `[ERROR] TELEGRAM_BOT_TOKEN not set` → Add to Variables
- `[ERROR] Database connection failed` → Check PostgreSQL
- `[INFO] Active searches: 0` → Add search via Web UI

**Solution:**
1. Verify environment variables are set
2. Restart worker service

### No Telegram notifications?

**Test bot token:**
```bash
curl https://api.telegram.org/bot8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw/getMe
```

Should return bot info.

**Check:**
- Bot is added to chat ID `-4997297083`
- Bot has "Send Messages" permission
- Worker logs show: `[INFO] Telegram notification sent successfully`

---

## Summary Checklist

- [ ] PostgreSQL database added
- [ ] GitHub repo **2extndd/MRS** connected
- [ ] **web** service created and deployed
- [ ] **worker** service created and deployed
- [ ] Environment variables added to both services
- [ ] Public domain enabled for **web** service
- [ ] Both services showing green ✓ in Deployments
- [ ] Web UI accessible in browser
- [ ] Worker logs show "Scheduler: Started"
- [ ] First search added via Web UI
- [ ] Telegram bot responding

---

## Quick Links

- **Railway Dashboard**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **GitHub Repo**: https://github.com/2extndd/MRS
- **Telegram Bot**: @YourBotName (check via https://t.me/8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw)

---

**Your MercariSearcher is ready to scan Mercari.jp! 🚀**

Follow these steps and you'll be receiving Telegram notifications in minutes!
