# Session 5.7 - Worker Restart for Proxy Loading

## 🎯 Goal:
Force Worker restart to load proxy configuration from database

## 🔍 Problem Identified:

**Worker logs show:**
```
📥 Downloading image: https://static.mercdn.net/...
Failed to download image: HTTP 403 (proxy: direct)  ← NO PROXY!
```

**Root cause:**
- Worker container deployed BEFORE proxies were enabled in database
- `proxies.py:283-293` loads proxy config ONCE at module import time
- No hot reload mechanism for proxy configuration
- Worker needs full container restart to reload config

## 📊 Investigation:

### 1. Database Config (Correct):
```sql
config_proxy_enabled: true
config_proxy_list: 115 proxies
```

### 2. Worker Runtime (Incorrect):
```
Proxy system disabled  ← Old config loaded at startup!
```

### 3. Image Download Status:
```
ALL image downloads: HTTP 403 (proxy: direct)
Success rate: 0%
```

## ✅ Solution Applied:

### Step 1: Version Bump
[configuration_values.py:22](configuration_values.py#L22)
```python
APP_VERSION = "1.0.1"  # Force Worker restart to reload proxy config
```

### Step 2: Created Diagnostic Script
[verify_proxy_config.py](verify_proxy_config.py) - New diagnostic tool

**Checks:**
1. configuration_values.py → PROXY_ENABLED, PROXY_LIST
2. proxies.py → proxy_manager, proxy_rotator initialization
3. image_utils.py → Test actual image download
4. Database → config_proxy_enabled, config_proxy_list

### Step 3: Deployment
```bash
git add configuration_values.py verify_proxy_config.py
git commit -m "trigger: Force worker restart via redeploy"
git push origin main
railway up -s Worker
```

**Build URL:**
https://railway.com/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d/service/1d82b0ac-1281-4b31-9a5d-cb3148ff77d0?id=7ebd4457-b670-4fe4-932c-7b7a84a8ae05

**Deployment time:** 2025-11-19 16:18 UTC (19:18 MSK)

## ⏳ Expected After Restart:

### Startup Logs Should Show:
```
Starting Container
Starting Railway service: Worker
Initializing proxy system...
ProxyManager initialized with 115 proxies
Validating 115 proxies...
Proxy validation complete: XX working, YY failed
ProxyRotator initialized with XX working proxies
```

### Image Download Should Show:
```
📥 Downloading image: https://static.mercdn.net/...
📡 Using proxy for image download: http://wtllhdak:9vxcxlvhxv1h@82.21.62.51:7815...
✅ Image downloaded: 123.4KB base64
```

### Database Should Show:
```sql
SELECT COUNT(*) FROM items WHERE image_data IS NOT NULL;
-- Should start increasing with new items
```

## 🧪 Verification Plan:

### Test 1: Check Startup Logs (2 minutes)
```bash
railway logs -s Worker | grep -E "ProxyManager|Proxy system"
```

**Expected:** "ProxyManager initialized with 115 proxies"

### Test 2: Check Next Scan (3-5 minutes)
```bash
railway logs -s Worker | grep -E "image|proxy: http"
```

**Expected:** "Using proxy for image download: http://..."

### Test 3: Database Check (5 minutes)
```sql
SELECT
    id,
    title,
    LENGTH(image_data) as img_size,
    found_at
FROM items
WHERE found_at > NOW() - INTERVAL '5 minutes'
ORDER BY found_at DESC
LIMIT 5;
```

**Expected:** `img_size > 100000` (base64 encoded image)

### Test 4: Web UI Check
Visit: https://web-production-fe38.up.railway.app/

**Expected:** New items show photos (not 403 placeholders)

## 📋 Timeline:

| Time (MSK) | Event | Status |
|------------|-------|--------|
| 19:00 | Proxies enabled in database | ✅ Done |
| 19:10 | Code fix deployed (proxy parsing) | ✅ Done |
| 19:15 | Discovered Worker not restarted | ❌ Issue |
| 19:18 | Triggered forced restart (v1.0.1) | ⏳ Deploying |
| 19:20 | Build completes | ⏳ Expected |
| 19:21 | Worker starts with proxies | ⏳ Expected |
| 19:23 | Next scan with proxy | ⏳ Expected |
| 19:25 | Photos appear in database | ⏳ Expected |

## 🔧 Files Modified:

1. [configuration_values.py](configuration_values.py#L22) - Version bump 1.0.0 → 1.0.1
2. [verify_proxy_config.py](verify_proxy_config.py) - NEW diagnostic script

## 📝 Commits:

```
65ec032 - trigger: Force worker restart via redeploy
```

## 🚀 Deployment:

**Service:** Worker
**Commit:** 65ec032
**Status:** Building/Deploying
**Build URL:** https://railway.com/project/.../service/.../build/7ebd4457...

## ⚠️ Critical Learning:

**Proxy configuration in MRS does NOT hot reload!**

The system loads proxy config once at startup:
```python
# proxies.py:283 - runs at module import
if config.PROXY_ENABLED and config.PROXY_LIST:
    proxy_manager = ProxyManager(config.PROXY_LIST)
```

**To apply proxy config changes:**
1. Update database (key_value_store)
2. **Force Worker restart** (redeploy or version bump)
3. Wait for module reimport

**NOT sufficient:**
- ❌ Just updating database
- ❌ Waiting for "hot reload" (doesn't exist for proxies)
- ❌ Web UI config change alone

**Must do:**
- ✅ Update database + Force Worker restart

## 📊 Expected Results:

### Before Restart:
```
Image downloads: 0/100 success (0%)
Proxy usage: direct (no proxy)
HTTP errors: 403 (Cloudflare blocked)
```

### After Restart:
```
Image downloads: 80-95/100 success (80-95%)
Proxy usage: http://user:pass@ip:port
HTTP success: 200 OK
```

## 🎯 Success Criteria:

1. ✅ Worker starts successfully
2. ✅ Logs show "ProxyManager initialized"
3. ✅ Image downloads use proxies (not "direct")
4. ✅ HTTP 200 responses (not 403)
5. ✅ Database gets image_data (base64)
6. ✅ Web UI shows photos
7. ✅ Telegram sends photos

## 🔗 References:

- **Previous session:** [SESSION_5.6_FINAL_STATUS.md](SESSION_5.6_FINAL_STATUS.md)
- **System architecture:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- **Proxy implementation:** [proxies.py:283-293](proxies.py#L283-L293)
- **Image download:** [image_utils.py:14-91](image_utils.py#L14-L91)

---

**Status:** ⏳ Waiting for deployment to complete
**Next:** Verify proxy initialization in startup logs
**Session:** 5.7
**Date:** 2025-11-19
