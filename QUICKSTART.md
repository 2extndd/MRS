# MercariSearcher - Quick Start Guide

## Railway Deployment (Recommended)

### Your Project
- **Project ID**: `f17da572-14c9-47b5-a9f1-1b6d5b6dea2d`
- **Dashboard**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **Repository**: https://github.com/2extndd/MRS

---

## 5-Minute Setup

### Step 1: Get Telegram Bot Token (2 min)

1. Open Telegram → Find **@BotFather**
2. Send `/newbot`
3. Choose bot name: `MercariSearcher` (or any name)
4. Choose username: `mercari_searcher_bot` (must end with 'bot')
5. **Copy the token** (looks like `123456789:ABCdefGHI...`)

### Step 2: Get Your Chat ID (1 min)

**Option A - Personal Chat:**
1. Send any message to your new bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find: `"chat":{"id":1234567890}`

**Option B - Group Chat:**
1. Add your bot to a group
2. Send message in group
3. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find: `"chat":{"id":-1001234567890}` (negative for groups)

**Option C - Using @userinfobot:**
1. Add **@userinfobot** to Telegram
2. Send `/start`
3. Copy your ID

### Step 3: Railway Setup (2 min)

1. **Open Railway Dashboard:**
   - Go to https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

2. **Add PostgreSQL:**
   - Click **"+ New"**
   - Select **"Database"**
   - Choose **"PostgreSQL"**
   - Done! (Railway auto-connects)

3. **Add Environment Variables:**
   - Click **"Variables"** tab
   - Add **New Variable**:

   ```
   TELEGRAM_BOT_TOKEN = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID = -1001234567890
   DISPLAY_CURRENCY = USD
   USD_CONVERSION_RATE = 0.0067
   ```

4. **Connect GitHub:**
   - Click **"Settings"**
   - **"Connect Repo"**
   - Select: `2extndd/MRS`
   - Branch: `main`
   - **Deploy**

5. **Wait for Deploy** (1-2 minutes)
   - Watch logs in **Deployments** tab
   - Should see: ✓ Build successful

---

## Verify It's Working

### Check Web UI

1. Railway Dashboard → **web** service
2. Click **"Settings"** → **"Networking"**
3. Copy public URL (e.g., `https://mrs-production.up.railway.app`)
4. **Open in browser** → Should see Dashboard

### Check Worker

1. Railway Dashboard → **worker** service
2. Click **"Deployments"** → **View Logs**
3. Should see:
   ```
   [INFO] MercariSearcher v1.0.0 Worker Starting...
   [INFO] Database: PostgreSQL connected
   [INFO] Telegram: Bot connected
   [INFO] Scheduler: Started
   ```

### Test Telegram

1. Open Telegram
2. Find your bot
3. Send `/start`
4. Bot should respond (if you added commands) or just stay online

---

## Add Your First Search

### Step 1: Find Items on Mercari

1. Go to https://jp.mercari.com
2. Search for what you want (e.g., "Julius denim")
3. Apply filters:
   - Category
   - Price range
   - Condition
   - Size
4. **Copy the URL** from browser

Example URL:
```
https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621
```

### Step 2: Add Search via Web UI

1. Open your Railway Web UI: `https://your-domain.up.railway.app/queries`
2. Click **"Add New Search"**
3. Fill form:
   - **Name**: `Julius Denim Under $120`
   - **URL**: `https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=17621`
   - **Telegram Chat ID**: `-1001234567890` (your chat)
   - **Thread ID**: (leave empty or add if using topics)
   - **Active**: ✓ Checked
4. Click **"Add Search"**

### Step 3: Wait for Notifications

- Scanner runs every **5 minutes** (default)
- When new items found → Telegram notification
- Notification includes:
  - 📸 Photo
  - 💴 Price (USD + JPY)
  - 👔 Brand (if available)
  - 📏 Size
  - 🔗 Direct link to item

---

## Example Telegram Notification

```
👔 JULIUS - Archive Distressed Denim Jacket

💴 $98.50 (¥14,700)
📏 Size: 2 (M)
🏷️ Condition: Used - Good
📦 Shipping: ¥700
🔍 Search: Julius Denim Under $120

[Photo of item]

[Open Mercari] button
```

---

## Configuration via Web UI

### Dashboard (`/`)
- View statistics
- Recent items
- Uptime
- API requests

### Searches (`/queries`)
- Add/Edit/Delete searches
- Activate/Deactivate
- View stats per search

### Items (`/items`)
- All found items
- Filter by search
- View photos
- Direct links to Mercari

### Config (`/config`)
- **Search Interval**: 300 seconds (5 min)
- **Max Items per Search**: 50
- **Telegram Settings**
- **Proxy Settings**
- **Auto-Redeploy Config**

### Logs (`/logs`)
- System logs
- Filter by level
- Real-time updates

---

## Advanced Features

### 1. Price Drop Alerts

When adding a search, enable **"Notify on Price Drop"**:
- Set threshold: e.g., `1000` (¥1,000)
- Bot alerts when price drops by ≥ threshold

### 2. Topics/Threads Support

For organized notifications:
1. Enable **Topics** in Telegram group
2. Create topic: "Julius Items"
3. Get Thread ID (see RAILWAY_SETUP.md)
4. Add Thread ID when creating search

Different searches → Different topics!

### 3. Multiple Searches

Add unlimited searches:
- Different keywords
- Different categories
- Different price ranges
- Each with own chat/thread

### 4. Proxy Support

If Mercari blocks your IP:
1. Get proxies (HTTP/SOCKS5)
2. Add to Railway variables:
   ```
   PROXY_ENABLED=true
   PROXY_LIST=http://proxy1:8080,socks5://proxy2:1080
   ```
3. Proxies auto-rotate

### 5. Adjust Scan Frequency

**Via Web UI:**
- `/config` → Search Interval → `600` (10 min)

**Via Railway Variables:**
```
SEARCH_INTERVAL=600
```

---

## Troubleshooting

### No Telegram Notifications

**Check:**
1. Bot token correct? Test: `https://api.telegram.org/bot<TOKEN>/getMe`
2. Chat ID correct? Check logs: `/logs`
3. Bot added to group?
4. Bot has "Send Messages" permission?

**Fix:**
- Railway Variables → Update `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Restart worker service

### No Items Found

**Check:**
1. Search URL valid? Test in browser
2. Search active? Check `/queries`
3. Interval passed? Check Dashboard → "Last Scan Time"

**Debug:**
- `/logs` → Filter: ERROR
- Worker logs in Railway → Check for errors

### Web UI Not Loading

**Check:**
1. Railway **web** service running?
2. Public domain assigned?
3. Database connected?

**Fix:**
- Railway → web service → Redeploy
- Check logs for errors

### Database Errors

**Check:**
1. PostgreSQL service running?
2. `DATABASE_URL` set?

**Fix:**
- Railway → Add PostgreSQL service
- Restart both web and worker

---

## Useful Links

- **Railway Project**: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
- **GitHub Repo**: https://github.com/2extndd/MRS
- **Full Setup Guide**: [RAILWAY_SETUP.md](RAILWAY_SETUP.md)
- **Documentation**: [README.md](README.md)
- **Mercari Japan**: https://jp.mercari.com
- **Telegram Bot API**: https://core.telegram.org/bots/api

---

## Tips & Best Practices

### Efficient Searching

1. **Be Specific**: Use exact keywords
2. **Set Price Ranges**: Avoid too broad
3. **Use Categories**: More accurate results
4. **Multiple Searches**: Different criteria for same item

### Avoid Blocking

1. **Don't Spam**: 5-10 min intervals recommended
2. **Use Proxies**: If scanning frequently
3. **Limit Items**: 20-50 items per search
4. **Monitor Logs**: Watch for 403/429 errors

### Organize Notifications

1. **Use Topics**: One topic per category
2. **Name Searches**: Descriptive names
3. **Archive Old Searches**: Deactivate when done

### Price Tracking

1. **Enable Price Drop Alerts**: For expensive items
2. **Set Thresholds**: Meaningful amounts (¥1000+)
3. **Check History**: `/items` → View price changes

---

## Example Searches

### Fashion - Julius Archive
```
URL: https://jp.mercari.com/search?keyword=julius&category_id=3088&price_max=20000
Name: Julius Under $135
Interval: 300 sec
```

### Electronics - Vintage Cameras
```
URL: https://jp.mercari.com/search?keyword=フィルムカメラ&category_id=3091&price_max=10000
Name: Film Cameras Under $70
Interval: 600 sec
```

### Sneakers - Nike Dunk
```
URL: https://jp.mercari.com/search?keyword=nike+dunk&category_id=3089&size=27.5
Name: Nike Dunk Size 27.5
Interval: 300 sec
```

---

## Support

**Issues?** Open issue on GitHub:
https://github.com/2extndd/MRS/issues

**Questions?** Check:
- [README.md](README.md) - Full documentation
- [RAILWAY_SETUP.md](RAILWAY_SETUP.md) - Detailed Railway guide

---

**Happy hunting on Mercari! 🛍️**
