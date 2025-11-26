# 🤖 AI Memory: Mercari Research System (MRS)

**Last Updated:** 2025-01-XX  
**System Status:** ✅ Production Ready on Railway

---

## 📋 System Overview

**MRS (Marketplace Research System)** - автоматизированный сканер Mercari для поиска и мониторинга товаров.

### Architecture
```
Railway Web Service (Single Process)
  ↓
  start.sh → gunicorn → wsgi.py
  ↓
  ├─ Flask Web UI (port 8080)
  │   ├─ /dashboard - Main dashboard
  │   ├─ /config - Configuration
  │   ├─ /queries - Search queries management
  │   ├─ /items - Items list
  │   └─ /logs - System logs
  │
  └─ Scheduler (Background Thread - 24/7)
      ├─ search_cycle() - Scan Mercari every N seconds
      ├─ telegram_cycle() - Send notifications
      └─ hot_reload() - Reload config from DB every 60s
```

### Database
- **Production (Railway):** PostgreSQL
- **Local (Development):** SQLite (`mercari_scanner.db`)
- **Auto-switches** based on `DATABASE_URL` env var

---

## 🔧 Key Components

### 1. Core Files

| File | Purpose | Key Functions |
|------|---------|---------------|
| `core.py` | Main search logic | `process_search_results()`, category filtering |
| `mercari_scraper.py` | Mercari API wrapper | `search_mercari()`, item parsing |
| `mercari_notifications.py` | Scheduler & cycles | `search_cycle()`, `telegram_cycle()` |
| `db.py` | Database abstraction | PostgreSQL/SQLite with hot reload |
| `configuration_values.py` | Config management | Hot reload every 60s from DB |
| `wsgi.py` | Production entry | Auto-starts scheduler on Railway |

### 2. Web UI Plugin

| File | Purpose |
|------|---------|
| `web_ui_plugin/app.py` | Flask application with all routes |
| `web_ui_plugin/templates/*.html` | Jinja2 templates |
| `web_ui_plugin/static/` | CSS, JS, favicon |

---

## ⚙️ Configuration System

### Config Storage
- **Database:** `key_value_store` table (PostgreSQL) or `config` table (SQLite)
- **Hot Reload:** Every 60 seconds via `configuration_values.py:reload_if_needed()`
- **Web UI:** `/config` page for editing

### Key Settings

| Setting | Key in DB | Default | Min | Max | Description |
|---------|-----------|---------|-----|-----|-------------|
| Query Delay | `config_search_interval` | 300s | **30s** | 3600s | How often to scan all queries |
| Max Items | `config_max_items_per_search` | 50 | 10 | 100 | Items per query scan |
| Category Blacklist | `config_category_blacklist` | `[]` | - | - | JSON array of blocked categories |
| Min Price | `config_min_price` | 100 | 0 | ∞ | Minimum price filter (JPY) |
| Max Price | `config_max_price` | 500000 | 0 | ∞ | Maximum price filter (JPY) |

---

## 🚨 Category Blacklist System

### How It Works

**Location:** `core.py` lines 390-418

```python
# 1. Get item category
item_category = getattr(full_item, 'category', None)

# 2. Check against blacklist (substring match)
if item_category and config.CATEGORY_BLACKLIST:
    for blacklisted_cat in config.CATEGORY_BLACKLIST:
        if blacklisted_cat in item_category:
            logger.info(f"[FILTER] 🚫 Item rejected")
            item_rejected = True
            break

# 3. Skip if rejected (BEFORE DB save, BEFORE image download)
if item_rejected:
    continue
```

### Important Notes

✅ **Filters BEFORE:**
- Saving to database
- Downloading images
- Sending notifications

⚠️ **Substring Matching:**
- Blacklist: `"ゲーム"` → Blocks: `"テレビゲーム"`, `"ゲーム・おもちゃ"`
- Use exact full category names from Mercari

⏰ **Timing:**
- Blacklist loaded at startup (`mercari_notifications.py:70`)
- Hot reload every 60 seconds
- **Old items stay in DB** if category added to blacklist later!

### Common Categories (Japanese)

```
ゲーム・おもちゃ・グッズ - Games, Toys, Goods
本・音楽・ゲーム - Books, Music, Games
エンタメ・ホビー - Entertainment, Hobbies
ベビー・キッズ - Baby, Kids
コスメ・美容 - Cosmetics, Beauty
CD・DVD・ブルーレイ - CD, DVD, Blu-ray
コップ・グラス・酒器 - Cups, Glasses, Sake ware
```

---

## 🚀 Scheduler & Cron Jobs

### ✅ NEW: Database-Based Heartbeat Monitoring (2025-01-26)

**Problem Solved:** Scheduler daemon thread was dying silently after some time, and Railway cron couldn't detect it.

**Solution:** Database-based heartbeat + health check script

#### How It Works

1. **Scheduler Writes Heartbeat** (`mercari_notifications.py:377-389`)
   - Every 10 seconds, scheduler writes timestamp to database
   - Uses `key_value_store` table with key `scheduler_heartbeat`
   - Persistent across process restarts

```python
# mercari_notifications.py:377-389
if loop_iteration % 10 == 0:
    current_heartbeat = dt_for_heartbeat.now()
    self.shared_state.set('scheduler_last_heartbeat', current_heartbeat)  # In-memory
    self.db.save_config('scheduler_heartbeat', current_heartbeat.isoformat())  # Database
```

2. **Health Check Script** ([health_check.py](health_check.py))
   - Runs via Railway cron job every 5 minutes
   - Reads heartbeat from database
   - If heartbeat older than 10 minutes → scheduler is DEAD
   - Exits with error code 1 (Railway logs show failure)

3. **Railway Cron Configuration**
   - Command: `python3 health_check.py`
   - Schedule: `*/5 * * * *` (every 5 minutes)
   - Service: `web`
   - Purpose: Monitor scheduler health, NOT run searches

**Key Points:**
- ✅ Query Delay controls scan frequency (30s-3600s)
- ✅ Cron job only monitors health (every 5 min)
- ✅ Heartbeat persists in database (survives process restarts)
- ✅ 10-minute timeout threshold (allows for temporary issues)

#### Logs to Check

```bash
# Scheduler writing heartbeat
[SCHEDULER] ⏰ Loop alive! Iteration 30 (1 min uptime)

# Health check SUCCESS
[HEALTH CHECK] ✅ Scheduler is ALIVE! Last heartbeat 2.3 minutes ago

# Health check FAILURE
[HEALTH CHECK] ❌ Scheduler is DEAD! No heartbeat for 15.7 minutes
```

### ⚠️ PREVIOUS: Railway Cron Limitation

**DO NOT use Railway Cron Job to run searches** (minimum 5 minutes limitation)

### How Scheduler Works

1. **Auto-Start:** `wsgi.py` lines 36-76 automatically starts scheduler on Railway
2. **Background Thread:** Runs 24/7 in daemon thread
3. **Auto-Restart:** Infinite loop with exponential backoff on crashes
4. **Configurable Interval:** `config.SEARCH_INTERVAL` can be **30 seconds to 1 hour**
5. **NEW: Heartbeat:** Writes to database every 10 seconds for health monitoring

```python
# wsgi.py:50-55
def start_scheduler_with_restart():
    while True:  # Infinite restart loop
        try:
            app_instance = MercariNotificationApp()
            app_instance.run_scheduler()  # Runs forever
        except Exception as e:
            logger.error(f"Scheduler crashed: {e}")
            time.sleep(restart_delay)
```

### Logs to Check

```bash
[AUTOSTART] Railway environment detected - starting scheduler...
[AUTOSTART] ✅ Scheduler thread started in background
[SCHEDULER] ⏰ Entering main loop...
[SCHEDULER] Jobs scheduled: 4
[SCHEDULER] ⏰ Loop alive! Iteration 30 (1 min uptime)
```

---

## 🐛 Known Issues & Solutions

### Issue #1: Items with blacklisted categories in DB

**Problem:** Old items remain in DB if category added to blacklist later.

**Solution:**
```python
# Manual cleanup (create script if needed)
from db import get_db
from configuration_values import config

db = get_db()
config.reload_if_needed()

for category in config.CATEGORY_BLACKLIST:
    db.execute_query(
        "DELETE FROM items WHERE category LIKE %s",
        (f'%{category}%',)
    )
```

### Issue #2: Query Delay not updating

**Problem:** Config cached, hot reload not triggered.

**Solution:**
- Wait 60 seconds for hot reload
- Or restart Railway service
- Check logs: `[CONFIG] Hot reload triggered`

### Issue #3: Scheduler not starting

**Problem:** Missing `RAILWAY_ENVIRONMENT` variable.

**Solution:**
- Check Railway Variables: `railway variables`
- Add if missing: `RAILWAY_ENVIRONMENT=production`

---

## 🧪 Testing & Debugging

### Test Locally

```bash
# 1. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Setup local database
export DATABASE_URL=""  # Use SQLite
python3 -c "from db import get_db; get_db()"

# 3. Run single cycle
python3 run_search_cycle.py

# 4. Run web UI
python3 web_ui_plugin/app.py
```

### Test on Railway

```bash
# 1. Link to project
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

# 2. Check logs
railway logs --service web

# 3. Run commands
railway run --service web python3 run_search_cycle.py

# 4. Open shell
railway shell --service web
```

### Key Log Patterns

```bash
# Successful scan
[SEARCH] Searching with keyword: "コペンハーゲン"
[SEARCH] Found 15 items for search "Royal Copenhagen"
[FILTER] ✅ Item passed: m12345678901

# Filtered item
[FILTER] 🚫 Item rejected: category 'ゲーム・おもちゃ・グッズ' is blacklisted
[FILTER]    Title: Nintendo Switch Game
[FILTER]    Matched blacklist: 'ゲーム・おもちゃ・グッズ'

# Database operations
[DB] Item added: m12345678901 - Title...
[DB] Item already exists: m12345678901

# Scheduler alive
[SCHEDULER] ⏰ Loop alive! Iteration 120 (2 min uptime)
```

---

## 🔄 Recent Changes (Last 10 Commits)

### Commit f531219 (Current)
```
✨ Fix: Query Delay can be less than 5 minutes + Documentation

Changes:
- config.html: Query Delay min 60s → 30s ⚡
- Added explanation: Railway Cron NOT needed
- Scheduler runs 24/7 inside web process

Key Findings:
- Category blacklist works correctly
- Filters BEFORE DB save and image download
- SEARCH_INTERVAL can be 30s-3600s
```

### Commit db74fe9
```
fix: Restart scheduler with improved logging
- Added restart count
- Exponential backoff on crashes
```

### Commit 26029a2
```
fix: Add auto-restart logic to scheduler thread
- Infinite loop with try-catch
- Daemon thread for auto-cleanup
```

### Commit b130f8e
```
feat: Restore automatic scheduler with configurable interval
- Removed external cron dependency
- Scheduler runs inside web process
```

---

## 📝 Best Practices

### Configuration
- ✅ Use Query Delay: 60-120 seconds (balanced)
- ✅ Use Max Items: 50 (default, good for most cases)
- ✅ Add full category names to blacklist (not partial)
- ⚠️ Test blacklist with few items first

### Deployment
- ✅ Always deploy through Git push (auto-deploy enabled)
- ✅ Monitor logs after deployment: `railway logs --service web`
- ✅ Check scheduler startup: Look for `[AUTOSTART] ✅ Scheduler thread started`
- ❌ Never use Railway Cron Job (not needed!)

### Debugging
- 🔍 Check Web UI `/logs` for recent errors
- 🔍 Use Railway logs with grep: `railway logs | grep "ERROR"`
- 🔍 Verify config loaded: Look for `[CONFIG] Category blacklist loaded: N categories`
- 🔍 Test single cycle: `python3 run_search_cycle.py`

---

## 🎯 Quick Reference

### Start/Stop Scheduler
```bash
# Scheduler auto-starts on Railway - no manual action needed!
# To restart: push code or restart Railway service
git push origin main
```

### Update Config
1. Web UI → `/config`
2. Change values
3. Click "Save"
4. Wait 60s for hot reload (or restart service)

### Add to Blacklist
1. Web UI → `/config` → Category Filter
2. Add category (one per line, in Japanese)
3. Click "Save Category Filter"
4. New items filtered immediately

### Check if Working
1. Railway logs: `[SCHEDULER] ⏰ Loop alive!`
2. Web UI `/dashboard`: "Last Scan" updates
3. Web UI `/items`: New items appear
4. Telegram: Notifications arrive

---

## 🚨 Emergency Procedures

### Scheduler Stopped
```bash
# 1. Check Railway logs
railway logs --service web | tail -50

# 2. Look for errors
railway logs --service web | grep "ERROR"

# 3. Restart service
railway service restart --service web
```

### Database Issues
```bash
# 1. Check connection
railway run --service web python3 -c "from db import get_db; print(get_db().db_type)"

# 2. Verify DATABASE_URL
railway variables --service web | grep DATABASE_URL
```

### Blacklist Not Working
```bash
# 1. Check config in DB
railway run --service web python3 -c "from configuration_values import config; config.reload_if_needed(); print(config.CATEGORY_BLACKLIST)"

# 2. Check logs for filter messages
railway logs --service web | grep "FILTER"
```

---

## 📚 Additional Resources

- **Railway Dashboard:** https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **Web UI:** https://your-domain.railway.app
- **Database:** PostgreSQL (internal Railway DNS)

---

**Notes for Future AI:**
- System uses PostgreSQL on Railway, SQLite locally
- Scheduler runs 24/7 in web process (wsgi.py), NOT via cron
- Category blacklist filters BEFORE DB save
- Hot reload every 60s from database
- Old items DON'T auto-delete when category added to blacklist
- **NEW:** Add to Blacklist button extracts ROOT category (before " > ")
- **NEW:** API returns `already_exists` flag to show if category was duplicate
- **ISSUE:** ~58% of items (70/120) have no category (old data from 2025-11-19)
