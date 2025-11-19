# 🤖 WARP.md - Critical Context for AI Agents

**⚠️ READ THIS ENTIRE FILE BEFORE MAKING ANY CHANGES! ⚠️**

This file contains all gotchas, critical issues, and hard-learned lessons from building MercariSearcher.

---

## 📋 Quick Facts

- **Project:** MercariSearcher (MRS) - Automated Mercari.jp monitoring with Telegram
- **Based on:** KufarSearcher (https://github.com/2extndd/KS1)
- **Deployment:** Railway (2 services: web + worker)
- **Database:** PostgreSQL (Railway) / SQLite (local)
- **API:** mercapi library (async wrapper for Mercari.jp)

---

## 🚨 CRITICAL ISSUE #1: Railway Worker Deployment

### THE BIGGEST GOTCHA IN THIS PROJECT!

**PROBLEM:** Worker service does NOT auto-update from GitHub!

```bash
# ❌ WRONG - this won't update worker!
git push origin main
# Worker stays on old commit!

# ✅ CORRECT - always do this:
git push origin main
railway up --service worker
railway up --service web
```

**WHY:** 
- `railway up` uploads LOCAL files, not from GitHub
- Railway caches old builds
- Worker gets stuck on old commit even after successful push

**HOW TO VERIFY:**
```bash
# Check worker logs for recent timestamp
railway logs --service worker | grep "STARTUP"

# If timestamp is old (hours ago) - worker NOT updated!
# Solution: railway up --service worker
```

**MUST SET:**
```bash
# In Railway Dashboard for each service:
RAILWAY_SERVICE_NAME=worker  # For worker service
RAILWAY_SERVICE_NAME=web     # For web service
```

Without these, `start.sh` won't route correctly!

---

## 🚨 CRITICAL ISSUE #2: Event Loop Errors

**PROBLEM:** `RuntimeError: Event loop is closed`

**CAUSE:** `asyncio.run()` creates NEW event loop each time

**SOLUTION:** Shared event loop in `pyMercariAPI/mercari.py`

```python
# ❌ NEVER DO THIS:
result = asyncio.run(some_async_function())  # Creates new loop!

# ✅ ALWAYS DO THIS (in mercari.py):
result = self._run_async(some_async_function())  # Uses shared loop

# Implementation:
def _get_or_create_loop(self):
    if self._loop is None or self._loop.is_closed():
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    return self._loop

def _run_async(self, coro):
    loop = self._get_or_create_loop()
    if loop.is_running():
        # Use ThreadPoolExecutor for Flask context
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return loop.run_until_complete(coro)
```

**IF EVENT LOOP ERRORS RETURN:**
1. Someone added `asyncio.run()` somewhere
2. Check `pyMercariAPI/mercari.py` - shared loop broken?
3. Look for new async code without proper handling

---

## 🚨 CRITICAL ISSUE #3: SQLite vs PostgreSQL

**PROBLEM:** Different SQL syntax!

```python
# PostgreSQL: ✅
ALTER TABLE searches ADD COLUMN IF NOT EXISTS name TEXT

# SQLite: ❌ FAILS!
# Doesn't support IF NOT EXISTS in ALTER TABLE
```

**SOLUTION:**
```python
if self.db_type == 'postgresql':
    self.execute_query("ALTER TABLE searches ADD COLUMN IF NOT EXISTS name TEXT")
else:
    # SQLite - check first
    cursor.execute("PRAGMA table_info(searches)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'name' not in columns:
        self.execute_query("ALTER TABLE searches ADD COLUMN name TEXT")
```

**ALWAYS:** Check `db_type` before migrations!

---

## 🚨 CRITICAL ISSUE #4: Cross-Process Visibility

**PROBLEM:** Web and Worker are SEPARATE processes on Railway

```python
# ❌ WRONG - only visible in current process
shared_state.increment('api_count')

# ✅ CORRECT - visible to ALL processes
db.save_config('api_request_count', new_value)
db.increment_api_counter()
```

**RULE:** Data shared between web/worker MUST go in database!

---

## 🚨 CRITICAL ISSUE #5: Force Scan in Flask

**PROBLEM:** Flask is sync, mercapi is async → deadlock

**SOLUTION:** Run in background thread

```python
# ❌ WRONG - blocks Flask
from core import MercariSearcher
searcher = MercariSearcher()
results = searcher.search_all_queries()  # BLOCKS!
return jsonify({'results': results})

# ✅ CORRECT - background thread
def run_scan():
    from core import MercariSearcher
    searcher = MercariSearcher()
    results = searcher.search_all_queries()

scan_thread = threading.Thread(target=run_scan, daemon=True)
scan_thread.start()
return jsonify({'success': True, 'message': 'Scan started'})
```

**NEVER** run searches directly in Flask handler!

---

## 📂 Project Structure

### Core Files (Most Important)

```
mercari_notifications.py   # Main entry, scheduler, worker loop
core.py                     # MercariSearcher class
db.py                       # DatabaseManager (PostgreSQL/SQLite)
simple_telegram_worker.py   # Telegram notifications
configuration_values.py     # Config with hot reload
pyMercariAPI/mercari.py     # Sync wrapper around async mercapi
```

### Web UI

```
web_ui_plugin/
  app.py                    # Flask routes
  templates/
    dashboard.html          # Main page
    items.html              # 6 cards/row, 4:5 format
    logs.html               # System logs
    queries.html            # Search management
  static/
    js/app.js               # Frontend
    css/style.css           # Styles
```

---

## 🗄️ Database Schema

### searches
```sql
- id, search_url, name, thread_id
- keyword, min_price, max_price, category_id, brand, condition, size, color
- scan_interval (INDIVIDUAL per search!)
- is_active, notify_on_price_drop
- last_scanned_at, total_scans, items_found
```

**CRITICAL:** Each search has own `scan_interval`. Worker checks:
```python
if current_time >= (last_scanned_at + scan_interval):
    # Ready to scan
```

### items
```sql
- id, mercari_id, search_id
- title, price, currency, brand, condition, size
- item_url, image_url
- is_sent, sent_at, found_at
```

### key_value_store
```sql
- key, value, updated_at
# Hot reload config + cross-process data
```

---

## ⚙️ Configuration

### Required Environment Variables

```bash
DATABASE_URL=postgresql://...  # Railway provides
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
RAILWAY_SERVICE_NAME=web|worker  # ⚠️ CRITICAL!
```

### Optional (have defaults)

```bash
TELEGRAM_THREAD_ID=...  # For topics
SEARCH_INTERVAL=300
MAX_ITEMS_PER_SEARCH=50
USD_CONVERSION_RATE=0.0067
```

### Hot Reload

Config updates from DB every 10 seconds without restart:

```python
# In worker main loop
if config.reload_if_needed():
    logger.info("[CONFIG] Reloaded from database")
    # Changes applied automatically!
```

**What can be hot reloaded:**
- SEARCH_INTERVAL
- MAX_ITEMS_PER_SEARCH
- USD_CONVERSION_RATE
- Any value in key_value_store

**What requires restart:**
- TELEGRAM_BOT_TOKEN
- DATABASE_URL
- Code changes

---

## 🎨 UI Design (Like KS1)

### Items Page
- **6 cards per row:** `col-lg-2 col-md-3 col-sm-4 col-6`
- **Photo format:** 4:5 aspect ratio (vertical)
- **Compact:** Title (60 chars), Price + Size, Search badge
- **Fast:** Simple `get_all_items(limit=30)`

### Telegram Format (MINIMAL)
```
<b>Item Title</b>

💶: $33.49 (¥4,999)
📏 Size: XL (if available)
🔍: search_keyword
```

**Removed (user request):**
- ❌ Condition
- ❌ Seller
- ❌ Category
- ❌ Brand

---

## 🐛 Common Problems

### Worker not finding items

**Check:**
1. Is worker running? `railway logs --service worker`
2. Searches active? `SELECT * FROM searches WHERE is_active = true`
3. Event loop errors? `grep "Event loop" logs`

### Telegram not sending

**Check:**
1. Worker on latest code? `railway logs | grep "Checking for pending"`
2. Bot token valid? `curl https://api.telegram.org/bot$TOKEN/getMe`
3. Unsent items? `SELECT COUNT(*) FROM items WHERE is_sent = false`

**Solution:**
- Old code: `railway up --service worker`
- Check env vars in Railway Dashboard

### Recent Items slow

**Fixed!** Uses `get_all_items(limit=30)` like KS1
- NO complex SQL WHERE filters
- Filter in Python after fetch (faster for small data)

### Photos low quality

**Fixed!** Fetches full item details:
```python
full_item = self.api.get_item_details(item.id)
image_url = full_item['image_url']  # High res!
```

Trade-off: +100-200ms per item, but much better quality

---

## 🚀 Deployment Checklist

### Before Push
```bash
# 1. Test locally
python mercari_notifications.py worker

# 2. Commit
git add .
git commit -m "Description"

# 3. Push
git push origin main
```

### After Push
```bash
# 4. ⚠️ MUST DEPLOY BOTH SERVICES!
railway up --service web
railway up --service worker

# 5. Verify (CRITICAL!)
railway logs --service worker | head -20

# Should see:
# [DB] Connected to PostgreSQL
# [STARTUP] ✅ Active searches: X
# [STARTUP] ✅ Scheduler is running

# 6. Check Telegram
# Should receive startup notification
```

### If Deployment Fails
```bash
# Check variables
railway variables --service worker

# Must have:
# RAILWAY_SERVICE_NAME=worker
# DATABASE_URL=postgresql://...
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
```

---

## 📚 Code Patterns

### Run Async in Sync Context
```python
# ❌ WRONG
result = asyncio.run(async_func())

# ✅ CORRECT (in mercari.py)
result = self._run_async(async_func())
```

### Background Task in Flask
```python
# ❌ WRONG - blocks
result = long_task()
return jsonify({'result': result})

# ✅ CORRECT
def run_bg():
    result = long_task()
    db.add_log_entry('INFO', f'Done: {result}', 'bg')

thread = threading.Thread(target=run_bg, daemon=True)
thread.start()
return jsonify({'success': True, 'message': 'Started'})
```

### Adding New Search Parameter
1. Add column to searches table (check DB type!)
2. Add to `add_search()` method
3. Add to search building in `core.py`
4. Add to Web UI form

---

## 🎓 Lessons Learned

### 1. Railway ≠ Heroku
- Worker doesn't auto-deploy from GitHub
- Must use `railway up` every time
- RAILWAY_SERVICE_NAME is critical

### 2. Async + Flask = Careful
- Use threads for async work
- Don't block request handlers
- ThreadPoolExecutor for event loop

### 3. PostgreSQL ≠ SQLite
- Different migration syntax
- Different placeholders (%s vs ?)
- Always check db_type

### 4. Simple > Complex
- Recent Items: simple query > complex SQL
- Event loop: shared > new each time
- API counter: DB > shared memory

### 5. User Wants Minimal
- Telegram: less is more
- Items: compact, 6 per row
- Fast > fancy

---

## 📖 Related Documentation

- **README.md** - User documentation
- **BOT_INFO_FOR_AGENTS.md** - Complete technical guide
- **TRANSLATION_IDEAS.md** - Future: JA→EN translation

---

## ✅ Checklist for New AI Agents

Before ANY changes:

- [ ] Read this entire file
- [ ] Understand Railway worker deployment gotcha
- [ ] Know event loop pattern
- [ ] Understand cross-process (DB not memory)
- [ ] Test locally first
- [ ] Deploy with `railway up` for BOTH services
- [ ] Verify in logs
- [ ] **Update this WARP.md with new lessons!**

---

## 🚨 Emergency Commands

```bash
# Worker not responding
railway restart --service worker

# Force redeploy
railway redeploy --service worker

# Check database
railway run psql $DATABASE_URL

# View variables
railway variables

# Check what commit worker uses
railway logs --service worker | head -20
```

---

## 🔄 Recent Changes Log

### 2025-11-19: Major UI overhaul
- Items page redesigned: 6 cards/row, 4:5 format (like KS1)
- Recent Items optimized: simple query instead of complex SQL
- Telegram format minimized: only Title, Price, Size, Query
- Photo quality improved: fetch full item details
- Documentation cleanup: removed 12 old .md files
- Created BOT_INFO_FOR_AGENTS.md

### Key lessons:
- Always `railway up --service worker` after push
- Simple `get_all_items(limit=30)` faster than SQL WHERE
- Users want minimal Telegram format
- High-res photos worth the extra API call

---

**⚠️ IMPORTANT: When you make changes, ADD THEM TO THIS FILE!**

Write a brief entry in "Recent Changes Log" section explaining:
- What changed
- Why it changed  
- Any new gotchas discovered
- Solutions that worked

This helps future agents avoid repeating mistakes!

---

**Last Updated:** 2025-11-19  
**Status:** Production, all major issues resolved  
**Always keep this file current!**
