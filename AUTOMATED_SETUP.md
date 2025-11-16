# Automated Railway Setup

## Quick Setup with Python Script

I've created an automated setup script that will configure your entire Railway project automatically.

---

## Prerequisites

You need 3 things:

### 1. Railway API Token
- Go to: https://railway.app/account/tokens
- Click **"Create Token"**
- Copy the token

### 2. Telegram Bot Token
- Open Telegram → Find **@BotFather**
- Send `/newbot` and follow instructions
- Copy the token (looks like `123456789:ABCdefGHI...`)

### 3. Telegram Chat ID
- Open Telegram → Find **@userinfobot**
- Send `/start`
- Copy your ID (looks like `1234567890` or `-1001234567890` for groups)

---

## Run Automated Setup

### Option 1: With Environment Variable

```bash
cd /Users/extndd/MRS

export RAILWAY_TOKEN='your_railway_api_token_here'
python setup_railway.py
```

### Option 2: As Argument

```bash
cd /Users/extndd/MRS

python setup_railway.py --token 'your_railway_api_token_here'
```

---

## What the Script Does

The script will automatically:

1. ✅ Connect to your Railway project
2. ✅ Add PostgreSQL database
3. ✅ Create **web** service (Flask UI)
   - Start command: `gunicorn --bind 0.0.0.0:$PORT wsgi:application`
   - Public networking enabled
   - Public domain generated
4. ✅ Create **worker** service (Background scanner)
   - Start command: `python mercari_notifications.py worker`
   - No public networking
5. ✅ Set environment variables for both services
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID
   - DISPLAY_CURRENCY=USD
   - USD_CONVERSION_RATE=0.0067
   - SEARCH_INTERVAL=300
   - And more...
6. ✅ Deploy both services

---

## During Setup

You'll be prompted for:

```
🤖 Enter TELEGRAM_BOT_TOKEN (from @BotFather): 
💬 Enter TELEGRAM_CHAT_ID (from @userinfobot): 
```

Just paste your tokens and press Enter.

---

## After Setup

The script will output:

```
═══════════════════════════════════════════════════════════════════
✅ RAILWAY SETUP COMPLETE!
═══════════════════════════════════════════════════════════════════

📍 Project: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

📦 Services created:
   ✓ web (Flask UI with public domain)
   ✓ worker (Background scanner)

🐘 PostgreSQL: Added

⚙️  Environment variables: Set

🚀 Next steps:
   1. Check deployments in Railway Dashboard
   2. Wait for services to start (2-3 minutes)
   3. Open web service public domain
   4. Add first search via /queries
```

---

## Verify Setup

### 1. Check Railway Dashboard

Go to: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

You should see:
- ✅ PostgreSQL service
- ✅ web service (with public domain)
- ✅ worker service

### 2. Check Deployments

Both **web** and **worker** should show:
- Green checkmark ✓
- Status: "Running"

### 3. Check Logs

**Web service logs:**
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:3000
```

**Worker service logs:**
```
[INFO] MercariSearcher v1.0.0 Worker Starting...
[INFO] Database: PostgreSQL connected
[INFO] Telegram: Bot connected
[INFO] Scheduler: Started
```

### 4. Open Web UI

1. Railway Dashboard → **web** service
2. **Settings** → **Networking**
3. Copy Public Domain
4. Open in browser
5. Should see MercariSearcher Dashboard

---

## Add Your First Search

1. Open Web UI
2. Go to `/queries`
3. Click **"Add New Search"**
4. Fill form:
   ```
   Name: Julius Denim
   URL: https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
   Telegram Chat ID: (your chat ID)
   Active: ✓
   ```
5. Click **"Add Search"**

Wait 5 minutes → You'll receive Telegram notification when items are found!

---

## Troubleshooting

### Script fails with "Failed to get project info"

**Problem:** Invalid Railway token or project ID

**Solution:**
1. Verify token from https://railway.app/account/tokens
2. Check project ID: `f17da572-14c9-47b5-a9f1-1b6d5b6dea2d`

### Service created but not deploying

**Problem:** GitHub repo not connected

**Solution:**
1. Railway Dashboard → Service → **Settings** → **Source**
2. Connect to `2extndd/MRS` repository
3. Branch: `main`
4. Click **"Redeploy"**

### Environment variables not set

**Problem:** GraphQL mutation failed

**Solution:**
- Manually add via Railway Dashboard → **Variables**
- Or run script again

---

## Manual Alternative

If automated script doesn't work, follow:
- **RAILWAY_MANUAL_SETUP.md** - Step-by-step manual setup

---

## Script Source Code

The script is open source and available at:
- **setup_railway.py** in the repository
- Uses Railway GraphQL API v2
- Built with Python `requests` library

---

## Support

- **GitHub Issues**: https://github.com/2extndd/MRS/issues
- **Railway Docs**: https://docs.railway.app
- **Script Help**: `python setup_railway.py --help`

---

**Let's automate your Railway setup! 🚀**
