# 🤖 AI Memory: Mercari Research System (MRS)

**Last Updated:** 2025-11-28
**System Status:** ⚠️ BROKEN - Worker service stops after ~30 minutes on Railway

---

## 🚨 CRITICAL ISSUE: Scheduler Loop Stops (2025-11-28)

### ❌ Problem Summary

**Railway Worker service scheduler loop STOPS after running for ~30 minutes**, despite being in an infinite `while True` loop.

**Evidence:**
- Last heartbeat: `2025-11-28T16:56:59` (176+ minutes ago as of 22:53 UTC+3)
- Worker logs show activity until 16:26, then silence
- Heartbeat API returns `alive: false`
- No error messages, no exceptions, no crashes - loop just **silently stops**

### 🏗️ NEW Architecture (2025-11-28) - CURRENTLY BROKEN

**Railway now runs TWO separate services:**

```
Railway Project: MRS
├─ Service: web (Gunicorn + Flask UI)
│   ├─ Start Command: bash start.sh
│   ├─ Process: gunicorn wsgi:application
│   ├─ Port: 8080
│   └─ No scheduler (removed from wsgi.py)
│
└─ Service: Worker (Background Scheduler) ⚠️ STOPS AFTER 30 MIN
    ├─ Start Command: python mercari_notifications.py
    ├─ Process: Infinite while True loop
    ├─ Configured: Manually in Railway Dashboard
    └─ ISSUE: Loop stops silently, no errors
```

**Key Files:**
- [Procfile](Procfile): Defines both services (web + worker)
- [wsgi.py](wsgi.py): Web service only, scheduler removed (lines 67-69)
- [mercari_notifications.py](mercari_notifications.py): Worker process with infinite loop (line 291)

**Why Separate Services:**
- Web UI needs to be responsive
- Scheduler is CPU-intensive
- Allows independent scaling/restart
- Matches KufarSearcher architecture

### 🐛 Root Cause: PostgreSQL DB Write Blocks Scheduler

**Initial Discovery (2025-11-28 16:00-17:00):**

The infinite loop at [mercari_notifications.py:291](mercari_notifications.py#L291) was **blocking indefinitely** on line 385:

```python
# BEFORE FIX (commit 737e60d):
while True:  # Line 291
    # ... scheduler logic ...

    # Heartbeat update every 10 seconds
    if loop_iteration % 10 == 0:
        try:
            current_heartbeat = dt_for_heartbeat.now()
            self.shared_state.set('scheduler_last_heartbeat', current_heartbeat)
            self.shared_state.set('scheduler_is_alive', True)

            # THIS LINE BLOCKS FOREVER when PostgreSQL connection hangs:
            self.db.save_config('scheduler_heartbeat', current_heartbeat.isoformat())
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            pass

    time.sleep(1)
```

**Why try/except Doesn't Help:**
- `db.save_config()` **hangs** (doesn't raise exception)
- PostgreSQL connection becomes unstable/unresponsive
- Python thread **waits indefinitely** for DB response
- Try/except only catches exceptions, NOT hanging operations

**First Fix Attempt (commit 737e60d) - FAILED:**

Added threading timeout to prevent blocking:

```python
# First fix attempt - wrapped DB write in thread with timeout
def write_heartbeat_with_timeout():
    try:
        self.db.save_config('scheduler_heartbeat', current_heartbeat.isoformat())
    except Exception as e:
        logger.warning(f"DB heartbeat write failed: {e}")

heartbeat_thread = threading.Thread(target=write_heartbeat_with_timeout, daemon=True)
heartbeat_thread.start()
heartbeat_thread.join(timeout=2.0)  # Wait max 2 seconds

if heartbeat_thread.is_alive():
    logger.warning(f"⚠️ Heartbeat DB write timed out (>2s) - continuing without blocking")
```

**BUT: This fix never deployed to Worker!** GitHub webhook didn't trigger auto-deploy.

**Final Fix (commit 77cbdde) - NOT YET DEPLOYED:**

Completely removed DB write:

```python
# CURRENT FIX (commit 77cbdde) - lines 377-388
if loop_iteration % 10 == 0:
    try:
        current_heartbeat = dt_for_heartbeat.now()
        self.shared_state.set('scheduler_last_heartbeat', current_heartbeat)
        self.shared_state.set('scheduler_is_alive', True)
        # NO DATABASE WRITE - prevents blocking when DB connection fails
    except Exception as heartbeat_error:
        logger.warning(f"[SCHEDULER] Failed to update heartbeat: {heartbeat_error}")
        pass
```

**Changes:**
- ✅ Removed `self.db.save_config('scheduler_heartbeat', ...)` completely
- ✅ Scheduler now updates in-memory heartbeat only via `shared_state`
- ✅ Cannot be blocked by PostgreSQL connection issues
- ⚠️ **NOT YET DEPLOYED** - Worker still running old code from before commit 737e60d

### 🚧 Deployment Issues

**Problem:** Railway Worker service does NOT auto-deploy when code pushed to GitHub

**Timeline:**
1. **16:00** - Pushed commit `737e60d` (threading timeout fix)
2. **16:23** - Worker still running old code (no "[SCHEDULER] Loop alive!" logs)
3. **16:56** - Worker stopped (last heartbeat)
4. **17:00+** - Attempted multiple deploy methods:
   - `railway up --service Worker` - FAILED (Worker tied to GitHub, ignores local uploads)
   - Empty commit `c679229` - Triggered deploy but **web and worker both redeployed**, web API broke (missing dateutil)
   - Pushed commit `77cbdde` (remove DB write) - **NO AUTO-DEPLOY**

**Root Cause:**
- Worker service created manually in Railway Dashboard
- **GitHub webhook not configured** or not working
- Service shows as "GitHub-linked" but doesn't actually auto-deploy

**Evidence:**
- Git log shows commits pushed: `77cbdde`, `c679229`, `737e60d`
- Local code is correct (DB write removed)
- Worker logs still from 16:26 (old code without fixes)
- No deployment logs after 16:23

### ✅ SOLUTION: Manual Redeploy Required

**NEXT AGENT MUST DO THIS:**

1. **Open Railway Dashboard:**
   ```
   https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker
   ```

2. **Verify Configuration:**
   - Start Command: `python mercari_notifications.py`
   - Source: GitHub (main branch)
   - Latest commit should be `77cbdde` (fix: REMOVE heartbeat DB write completely)

3. **Manual Redeploy:**
   - Click "Deploy" or "Redeploy" button
   - Wait 2-3 minutes for deployment
   - Check Deployments tab for status

4. **Verify Fix Applied:**
   ```bash
   railway logs --service Worker 2>&1 | grep -E "SCHEDULER|Loop alive" | tail -30
   ```

   **Expected logs (NEW CODE):**
   ```
   [SCHEDULER] ⏰ First iteration starting...
   [SCHEDULER] ⏰ Loop alive! Iteration 30
   [SCHEDULER] ⏰ Loop alive! Iteration 60
   [SCHEDULER] ⏰ Loop alive! Iteration 90
   ```

   **Old code logs (if still not deployed):**
   ```
   [SCAN] ✅ Search completed
   [PROCESS] ✅ NEW ITEM ADDED
   # NO "[SCHEDULER] Loop alive!" messages
   ```

5. **Monitor Continuously:**
   ```bash
   # Check heartbeat every 2 minutes for 10 minutes
   for i in {1..5}; do
       echo "=== Check $i/5 at $(date) ==="
       curl -s "https://web-production-fe38.up.railway.app/api/scheduler/heartbeat" | python3 -m json.tool
       sleep 120
   done
   ```

   **Expected:** `alive: true`, `last_heartbeat` updating every check

6. **If Still Failing:**
   - Check Worker logs for ANY errors
   - Verify PostgreSQL connection is stable
   - Consider alternative: Store heartbeat in Redis instead of PostgreSQL
   - Consider alternative: Remove heartbeat system entirely, rely on Railway health checks

### 📊 Commit History (Last 5)

```bash
77cbdde (HEAD -> main) - fix: REMOVE heartbeat DB write completely - prevents scheduler blocking
c679229 - chore: Trigger Worker redeploy with heartbeat timeout fix
737e60d - fix: Add timeout to heartbeat DB writes to prevent scheduler blocking
2abe41a - fix: Remove autostart - use Railway worker service
3123648 - fix: Restore scheduler autostart in wsgi.py
```

### 🔍 Key Code Locations

**Infinite Loop (Must Never Stop):**
- [mercari_notifications.py:291-403](mercari_notifications.py#L291-L403)
- `while True:` with `schedule.run_pending()` and `time.sleep(1)`

**Heartbeat Update (No DB Write):**
- [mercari_notifications.py:377-388](mercari_notifications.py#L377-L388)
- Updates `shared_state` only, no blocking operations

**Worker Service Config:**
- Manual configuration in Railway Dashboard
- Start Command: `python mercari_notifications.py`
- Must deploy from GitHub main branch

**Logs to Check:**
```bash
# Scheduler alive (every 30 seconds)
[SCHEDULER] ⏰ Loop alive! Iteration {N}

# Scanning activity
[SCAN] ✅ Search completed: X total items from API

# Heartbeat updates (in-memory only, every 10 seconds)
# No DB write logs
```

---

## 📋 System Overview

**MRS (Marketplace Research System)** - автоматизированный сканер Mercari для поиска и мониторинга товаров.

### ⚠️ NEW Architecture: Two Railway Services

```
Railway Project: MRS (f17da572-14c9-47b5-a9f1-1b6d5b6dea2d)

Service 1: web
  ↓
  bash start.sh → gunicorn wsgi:application
  ↓
  Flask Web UI (port 8080)
  ├─ /dashboard - Main dashboard
  ├─ /config - Configuration
  ├─ /queries - Search queries management
  ├─ /items - Items list
  ├─ /api/scheduler/heartbeat - Scheduler health check
  └─ /logs - System logs

Service 2: Worker (BACKGROUND PROCESS)
  ↓
  python mercari_notifications.py
  ↓
  Infinite Loop Scheduler
  ├─ search_cycle() - Scan Mercari every N seconds
  ├─ telegram_cycle() - Send notifications
  ├─ hot_reload() - Reload config from DB every 60s
  └─ heartbeat update - Update shared_state every 10s
```

**Why Two Services:**
- Web UI must be responsive (user requests)
- Scheduler is CPU-intensive (continuous scanning)
- Independent scaling and restart
- Matches KufarSearcher architecture pattern

**Communication:**
- Web UI reads scheduler status from `shared_state` (in-memory)
- Both services connect to same PostgreSQL database
- Worker writes items, Web UI displays them

### Database
- **Production (Railway):** PostgreSQL (shared between web + worker)
- **Local (Development):** SQLite (`mercari_scanner.db`)
- **Auto-switches** based on `DATABASE_URL` env var

---

## 🔧 Key Components

### 1. Core Files

| File | Purpose | Key Functions |
|------|---------|---------------|
| `core.py` | Main search logic | `process_search_results()`, category filtering |
| `mercari_scraper.py` | Mercari API wrapper | `search_mercari()`, item parsing |
| `mercari_notifications.py` | **WORKER PROCESS** | Infinite loop scheduler, search/telegram cycles |
| `db.py` | Database abstraction | PostgreSQL/SQLite with hot reload |
| `configuration_values.py` | Config management | Hot reload every 60s from DB |
| `wsgi.py` | **WEB PROCESS** | Flask app only, NO scheduler |

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

## 🚀 Worker Service Deployment (Railway)

### Service Configuration

**Service Name:** Worker
**Start Command:** `python mercari_notifications.py`
**Source:** GitHub (main branch)
**Auto-Deploy:** ⚠️ NOT WORKING - requires manual redeploy

**Environment Variables (shared with web service):**
- `DATABASE_URL` - PostgreSQL connection string (auto-provided by Railway)
- `RAILWAY_ENVIRONMENT` - Set to `production`
- Telegram credentials (same as web service)

### How to Configure Worker Service (First Time)

1. **Create Service in Railway Dashboard:**
   - Go to Project → New Service → GitHub Repo
   - Select repository
   - Name: `Worker`

2. **Set Start Command:**
   - Service Settings → Start Command
   - Enter: `python mercari_notifications.py`
   - Save

3. **Link to Database:**
   - Service Settings → Variables
   - Add reference to PostgreSQL service
   - `DATABASE_URL` will auto-populate

4. **Deploy:**
   - Deployments tab → Deploy
   - Wait 2-3 minutes

### How to Redeploy (When Code Changes)

**⚠️ CRITICAL: Auto-deploy from GitHub is BROKEN**

**Manual Redeploy Required:**

1. Open Railway Dashboard: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker
2. Click "Deploy" or "Redeploy" button
3. Verify deployment in Deployments tab
4. Check logs for `[SCHEDULER] ⏰ Loop alive!` messages

**DO NOT USE `railway up --service Worker`** - Worker is GitHub-linked, ignores local uploads

### Logs to Monitor

```bash
# View Worker logs
railway logs --service Worker

# Check for scheduler activity (every 30 seconds)
railway logs --service Worker | grep "Loop alive"

# Check for errors
railway logs --service Worker | grep -E "error|Error|ERROR|Exception|Traceback"

# Monitor specific time range
railway logs --service Worker | grep "2025-11-28 19:"
```

**Expected logs (healthy Worker):**
```
[SCHEDULER] ⏰ First iteration starting...
[SCHEDULER] Jobs scheduled: 2
[SCHEDULER] ⏰ Loop alive! Iteration 30
[SCAN] 🔍 Running search cycle...
[SCAN] ✅ Search completed: 15 total items from API
[SCHEDULER] ⏰ Loop alive! Iteration 60
```

**Bad logs (old code or crashed):**
```
[SCAN] ✅ Search completed
[PROCESS] ✅ NEW ITEM ADDED
# No "[SCHEDULER] Loop alive!" messages
# Or logs stop completely after some time
```

---

## 🐛 Known Issues & Solutions

### ❌ Issue #1: Worker Scheduler Loop Stops After ~30 Minutes

**Problem:** Infinite `while True` loop at [mercari_notifications.py:291](mercari_notifications.py#L291) silently stops running.

**Root Cause:** PostgreSQL `db.save_config()` call hangs indefinitely when connection becomes unstable (lines 377-388 OLD CODE).

**Solution Applied (commit 77cbdde):**
- Completely removed `self.db.save_config('scheduler_heartbeat', ...)`
- Heartbeat now updates `shared_state` (in-memory) only
- No blocking database operations in loop

**Status:** ⚠️ **FIX NOT DEPLOYED** - Worker running old code, manual redeploy required

**How to Fix:**
1. Manual redeploy Worker service via Railway Dashboard
2. Verify logs show `[SCHEDULER] ⏰ Loop alive!` every 30 seconds
3. Monitor heartbeat API for continuous updates

---

### ❌ Issue #2: Railway Auto-Deploy Not Working for Worker

**Problem:** Pushing code to GitHub does NOT trigger Worker service redeploy.

**Evidence:**
- Commits `77cbdde`, `c679229`, `737e60d` pushed to main
- Worker logs still from 16:26 (before commits)
- No deployment activity in Railway Dashboard

**Possible Causes:**
- GitHub webhook not configured
- Worker service misconfigured (not properly linked to GitHub)
- Railway bug/limitation

**Workaround:**
- **Manual redeploy via Railway Dashboard** (only reliable method)
- Click Deploy button after every code push
- Monitor deployment status

**DO NOT USE:**
- `railway up --service Worker` - Fails (Worker is GitHub-linked)
- Empty commits to trigger webhook - Unreliable

---

### Issue #3: Items with blacklisted categories in DB

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

---

### Issue #4: Query Delay not updating

**Problem:** Config cached, hot reload not triggered.

**Solution:**
- Wait 60 seconds for hot reload
- Or restart Railway Worker service
- Check logs: `[CONFIG] Hot reload triggered`

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

# 5. Run worker (scheduler) locally
python3 mercari_notifications.py
```

### Test on Railway

```bash
# 1. Link to project
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

# 2. Check Worker logs
railway logs --service Worker

# 3. Check Web logs
railway logs --service web

# 4. Check Worker status
curl -s "https://web-production-fe38.up.railway.app/api/scheduler/heartbeat" | python3 -m json.tool

# 5. Open Worker Dashboard
open "https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker"
```

### Key Log Patterns

```bash
# Worker scheduler alive (CRITICAL - must appear every 30 seconds)
[SCHEDULER] ⏰ Loop alive! Iteration 30
[SCHEDULER] ⏰ Loop alive! Iteration 60

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
```

---

## 🚨 Emergency Procedures

### Worker Scheduler Stopped

**Symptoms:**
- Heartbeat API shows `alive: false`
- `last_heartbeat` timestamp old (>5 minutes)
- No `[SCHEDULER] Loop alive!` logs in last 2 minutes

**Diagnosis:**
```bash
# 1. Check heartbeat status
curl -s "https://web-production-fe38.up.railway.app/api/scheduler/heartbeat" | python3 -m json.tool

# 2. Check Worker logs for last activity
railway logs --service Worker | tail -50

# 3. Look for errors
railway logs --service Worker | grep -E "error|Error|Exception"

# 4. Check loop alive messages
railway logs --service Worker | grep "Loop alive" | tail -10
```

**Fix:**
```bash
# Option 1: Restart Worker service via Railway Dashboard
# 1. Open: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker
# 2. Settings → Restart Service
# 3. Wait 1-2 minutes
# 4. Verify logs show [SCHEDULER] Loop alive!

# Option 2: Redeploy with latest code
# 1. Railway Dashboard → Worker → Deploy
# 2. Wait 2-3 minutes for deployment
# 3. Check logs
```

---

### Worker Not Deploying New Code

**Symptoms:**
- Code pushed to GitHub
- Worker logs show old code behavior
- No deployment activity in Railway Dashboard

**Fix:**
```bash
# Manual redeploy required
# 1. Open Railway Dashboard
open "https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker"

# 2. Click Deploy button
# 3. Verify deployment in Deployments tab
# 4. Check logs for new code behavior

# To verify code version:
railway logs --service Worker | grep "SCHEDULER.*Loop alive" | head -5
# If you see "[SCHEDULER] ⏰ Loop alive!" → NEW CODE (commit 77cbdde+)
# If you DON'T see it → OLD CODE (before commit 737e60d)
```

---

### Database Issues

```bash
# 1. Check connection
railway run --service Worker python3 -c "from db import get_db; print(get_db().db_type)"

# 2. Verify DATABASE_URL
railway variables --service Worker | grep DATABASE_URL

# 3. Test database from Worker
railway run --service Worker python3 -c "from db import get_db; db = get_db(); print(db.fetch_all('SELECT COUNT(*) FROM items'))"
```

---

## 📚 Additional Resources

- **Railway Dashboard:** https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **Worker Service:** https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker
- **Web UI:** https://web-production-fe38.up.railway.app
- **Heartbeat API:** https://web-production-fe38.up.railway.app/api/scheduler/heartbeat

---

## 🎯 PROMPT FOR NEXT AGENT

**CRITICAL TASK: Fix Worker Scheduler Loop Stopping Issue**

### Background

The MRS (Mercari Research System) runs on Railway with TWO services:
1. **web** - Flask UI (working fine)
2. **Worker** - Background scheduler (BROKEN - stops after ~30 min)

The Worker service runs an infinite `while True` loop in [mercari_notifications.py:291](mercari_notifications.py#L291) that should NEVER stop. However, it **silently stops** after ~30 minutes with no errors.

**Root Cause:** PostgreSQL `db.save_config()` hangs indefinitely when connection becomes unstable, blocking the entire loop.

**Fix Applied:** Commit `77cbdde` completely removed the blocking DB write from heartbeat update (lines 377-388).

**Problem:** This fix is NOT DEPLOYED to Worker service. Railway auto-deploy from GitHub is broken.

### Your Task

1. **Manually redeploy Worker service:**
   - Open: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/Worker
   - Click "Deploy" or "Redeploy"
   - Verify it deploys commit `77cbdde` or later
   - Wait 2-3 minutes

2. **Verify fix is working:**
   ```bash
   # Should see "[SCHEDULER] ⏰ Loop alive!" every 30 seconds
   railway logs --service Worker | grep "Loop alive"
   ```

3. **Monitor continuously for 10 minutes:**
   ```bash
   # Check heartbeat every 2 minutes
   for i in {1..5}; do
       echo "=== Check $i/5 at $(date) ==="
       curl -s "https://web-production-fe38.up.railway.app/api/scheduler/heartbeat" | python3 -m json.tool
       sleep 120
   done
   ```

   Expected: `alive: true` with `last_heartbeat` updating each check

4. **If still failing after 10 minutes:**
   - Check Worker logs for ANY errors
   - Investigate PostgreSQL connection stability
   - Consider removing heartbeat system entirely
   - Consider alternative: Use Redis for heartbeat instead of PostgreSQL

### Critical Files

- [mercari_notifications.py:291-403](mercari_notifications.py#L291-L403) - Infinite loop (must never stop)
- [mercari_notifications.py:377-388](mercari_notifications.py#L377-L388) - Heartbeat update (no DB write in latest code)
- [Procfile](Procfile) - Defines web + worker services
- [wsgi.py](wsgi.py) - Web service only (no scheduler)

### Success Criteria

- ✅ Worker logs show `[SCHEDULER] ⏰ Loop alive!` every 30 seconds
- ✅ Heartbeat API returns `alive: true` continuously
- ✅ `last_heartbeat` timestamp updates every 10 seconds
- ✅ Worker runs for 30+ minutes WITHOUT stopping
- ✅ No blocking database operations in main loop

### Failure Indicators

- ❌ No `[SCHEDULER] Loop alive!` messages in logs
- ❌ Heartbeat API shows `alive: false`
- ❌ `last_heartbeat` timestamp older than 2 minutes
- ❌ Worker logs show old code behavior (before commit 77cbdde)
- ❌ Logs stop updating after some time

---

**Last Known State (2025-11-28 22:53 UTC+3):**
- Worker stopped at: 16:56:59 (176 minutes ago)
- Last deployment: Unknown (auto-deploy broken)
- Current code version: OLD (before commit 737e60d)
- Heartbeat status: `alive: false`
- Latest commit: `77cbdde` (not deployed)

**Next agent: START HERE** 👆
