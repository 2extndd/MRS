# 🖼️ Detailed Image Solutions - 4 Approaches

## Current Problem:
Cloudflare blocks Railway datacenter IPs → HTTP 403 on `static.mercdn.net` and `mercari-shops-static.com`

---

## Solution 1: External Proxy Services (ScraperAPI, ProxyMesh)

### How it works:
Your Railway worker sends requests through a residential proxy service that Cloudflare doesn't block.

### Option A: ScraperAPI ($49-149/month)
**Free tier:** 1,000 requests/month
**Paid plans:** 10,000 requests ($49), 100,000 requests ($149)

#### Implementation:
```python
# image_utils.py
import requests
import base64
from typing import Optional

SCRAPER_API_KEY = "your_api_key_here"  # Get from dashboard.scraperapi.com

def download_and_encode_image(image_url: str, timeout: int = 30) -> Optional[str]:
    """Download image via ScraperAPI proxy"""

    # ScraperAPI endpoint
    proxy_url = "http://api.scraperapi.com"

    params = {
        'api_key': SCRAPER_API_KEY,
        'url': image_url,
        'render': 'false',  # Don't need JS rendering for images
        'country_code': 'jp'  # Use Japan proxy for better success
    }

    try:
        response = requests.get(proxy_url, params=params, timeout=timeout, stream=True)

        if response.status_code != 200:
            logger.warning(f"ScraperAPI failed: HTTP {response.status_code}")
            return None

        # Check size (max 500KB)
        image_bytes = response.content
        if len(image_bytes) / 1024 > 500:
            logger.warning(f"Image too large: {len(image_bytes)/1024:.1f}KB")
            return None

        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        data_uri = f"data:{content_type};base64,{base64_image}"

        logger.info(f"✅ Image downloaded via ScraperAPI ({len(image_bytes)/1024:.1f}KB)")
        return data_uri

    except Exception as e:
        logger.error(f"ScraperAPI error: {e}")
        return None
```

#### Setup Steps:
1. Sign up at https://dashboard.scraperapi.com/signup
2. Get API key from dashboard
3. Add to Railway environment variables:
   ```
   SCRAPER_API_KEY=your_key_here
   ```
4. Update `image_utils.py` with code above
5. Deploy: `railway up -s Worker --detach`

#### Pros:
- ✅ 95-99% success rate
- ✅ Automatic rotation of IPs
- ✅ Japan geo-targeting available
- ✅ Easy implementation (just change URL)

#### Cons:
- ❌ Costs $49/month minimum for real usage
- ❌ Free tier only 1,000 requests (≈16 items/day)
- ❌ Each image = 1 request

#### Cost Calculation:
- 100 items/day × 30 days = 3,000 images/month
- Required plan: $49/month (10,000 requests)
- Per-image cost: $0.0049

---

### Option B: ProxyMesh ($10-100/month)
**Plans:** 10 ports ($10), 100 ports ($100)
**Type:** Rotating datacenter proxies (lower success rate than residential)

#### Implementation:
```python
# image_utils.py
import requests
import base64
from typing import Optional

PROXYMESH_USER = "your_username"
PROXYMESH_PASS = "your_password"
PROXYMESH_URL = "http://jp.proxymesh.com:31280"  # Japan proxy

def download_and_encode_image(image_url: str, timeout: int = 30) -> Optional[str]:
    """Download image via ProxyMesh"""

    proxies = {
        'http': f'http://{PROXYMESH_USER}:{PROXYMESH_PASS}@{PROXYMESH_URL}',
        'https': f'http://{PROXYMESH_USER}:{PROXYMESH_PASS}@{PROXYMESH_URL}'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://jp.mercari.com/',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
    }

    try:
        response = requests.get(
            image_url,
            headers=headers,
            proxies=proxies,
            timeout=timeout,
            stream=True
        )

        if response.status_code != 200:
            logger.warning(f"ProxyMesh failed: HTTP {response.status_code}")
            return None

        # Check size (max 500KB)
        image_bytes = response.content
        if len(image_bytes) / 1024 > 500:
            return None

        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        data_uri = f"data:{content_type};base64,{base64_image}"

        logger.info(f"✅ Image via ProxyMesh ({len(image_bytes)/1024:.1f}KB)")
        return data_uri

    except Exception as e:
        logger.error(f"ProxyMesh error: {e}")
        return None
```

#### Setup Steps:
1. Sign up at https://proxymesh.com/
2. Get username/password from account settings
3. Add to Railway variables:
   ```
   PROXYMESH_USER=username
   PROXYMESH_PASS=password
   ```
4. Update `image_utils.py`
5. Deploy: `railway up -s Worker --detach`

#### Pros:
- ✅ Cheaper than ScraperAPI ($10/month)
- ✅ Unlimited bandwidth
- ✅ Japan-specific proxy available

#### Cons:
- ❌ 60-80% success rate (datacenter IPs, not residential)
- ❌ May still get Cloudflare blocks
- ❌ Need retry logic

---

## Solution 2: Cloudflare Worker as Proxy (Free)

### How it works:
Deploy a tiny proxy on Cloudflare Workers that fetches images for you. Cloudflare's IPs are whitelisted by Cloudflare (ironic!).

### Implementation:

#### Step 1: Create Cloudflare Worker
```javascript
// cloudflare-worker.js
export default {
  async fetch(request, env, ctx) {
    // Get image URL from query parameter
    const url = new URL(request.url);
    const imageUrl = url.searchParams.get('url');

    if (!imageUrl) {
      return new Response('Missing url parameter', { status: 400 });
    }

    // Only allow Mercari domains
    if (!imageUrl.includes('mercdn.net') && !imageUrl.includes('mercari-shops-static.com')) {
      return new Response('Invalid domain', { status: 403 });
    }

    try {
      // Fetch image from Mercari
      const imageResponse = await fetch(imageUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'https://jp.mercari.com/',
          'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }
      });

      if (!imageResponse.ok) {
        return new Response(`Failed to fetch: ${imageResponse.status}`, {
          status: imageResponse.status
        });
      }

      // Return image with CORS headers
      const headers = new Headers(imageResponse.headers);
      headers.set('Access-Control-Allow-Origin', '*');
      headers.set('Cache-Control', 'public, max-age=86400'); // 24h cache

      return new Response(imageResponse.body, {
        status: 200,
        headers: headers
      });

    } catch (error) {
      return new Response(`Error: ${error.message}`, { status: 500 });
    }
  }
};
```

#### Step 2: Deploy Worker
```bash
# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Create project
mkdir mercari-image-proxy
cd mercari-image-proxy
wrangler init

# Copy worker code to src/index.js
# Then deploy:
wrangler deploy
```

You'll get a URL like: `https://mercari-image-proxy.your-subdomain.workers.dev`

#### Step 3: Update Python Code
```python
# image_utils.py
CLOUDFLARE_WORKER_URL = "https://mercari-image-proxy.your-subdomain.workers.dev"

def download_and_encode_image(image_url: str, timeout: int = 15) -> Optional[str]:
    """Download image via Cloudflare Worker proxy"""

    proxy_url = f"{CLOUDFLARE_WORKER_URL}?url={image_url}"

    try:
        response = requests.get(proxy_url, timeout=timeout, stream=True)

        if response.status_code != 200:
            logger.warning(f"CF Worker failed: HTTP {response.status_code}")
            return None

        # Check size
        image_bytes = response.content
        if len(image_bytes) / 1024 > 500:
            return None

        # Encode to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        data_uri = f"data:{content_type};base64,{base64_image}"

        logger.info(f"✅ Image via CF Worker ({len(image_bytes)/1024:.1f}KB)")
        return data_uri

    except Exception as e:
        logger.error(f"CF Worker error: {e}")
        return None
```

#### Pros:
- ✅ **FREE** (100k requests/day on free tier)
- ✅ 70-85% success rate (better than Railway direct)
- ✅ Fast (Cloudflare network)
- ✅ Easy to deploy

#### Cons:
- ❌ Not guaranteed to work (Cloudflare may still block)
- ❌ Need Cloudflare account
- ❌ Request limits (100k/day free, then $0.50 per million)

#### Cost:
- Free tier: 100,000 requests/day
- 100 items/day = well within free tier
- **Total cost: $0**

---

## Solution 3: Store URLs + Display via iframe/object tag

### How it works:
DON'T download images at all. Store only the URL in database, then display using `<iframe>` or `<object>` tag which bypasses CORS (because it's not fetching from Railway IP).

### Implementation:

#### Step 1: Simplify Database Storage
```python
# core.py (lines 386-416)
# Remove image download code entirely:

# Just store the URL
image_url = item_data.get('thumbnails', [None])[0] if item_data.get('thumbnails') else None

# Add to database (NO image_data parameter)
db_item_id = self.db.add_item(
    item_id=item_id,
    item_name=item_name,
    item_price=item_price,
    item_url=item_url,
    search_id=search_id,
    image_url=image_url,  # Just the URL
    image_data=None  # No base64
)
```

#### Step 2: Update Web UI Templates
```html
<!-- templates/items.html (line 26) -->
<!-- Replace current <img> tag with: -->

{% if item.image_url %}
  <!-- Option A: iframe (works for most sites) -->
  <iframe
    src="{{ item.image_url }}"
    width="200"
    height="200"
    frameborder="0"
    scrolling="no"
    sandbox="allow-same-origin"
    style="pointer-events: none;"
  ></iframe>

  <!-- Option B: object tag (fallback) -->
  <object
    data="{{ item.image_url }}"
    type="image/jpeg"
    width="200"
    height="200"
  >
    <p>Image unavailable</p>
  </object>

  <!-- Option C: Hybrid with error handling -->
  <img
    src="{{ item.image_url }}"
    alt="{{ item.item_name }}"
    onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
    referrerpolicy="no-referrer"
  >
  <div style="display:none; width:200px; height:200px; background:#eee; text-align:center; padding:80px 0;">
    📷 Image blocked
  </div>
{% else %}
  <div style="width:200px; height:200px; background:#eee; text-align:center; padding:80px 0;">
    No image
  </div>
{% endif %}
```

#### Step 3: Remove /api/image Endpoint
```python
# web_ui_plugin/app.py
# DELETE lines 944-999 (/api/image endpoint)
# Not needed anymore
```

#### Step 4: Update Telegram Bot
```python
# telegram_sender.py (or wherever Telegram send happens)
def send_telegram_notification(item):
    """Send notification with direct image URL (may fail due to 403)"""

    message = f"""
🆕 New Item Found!

📦 {item['item_name']}
💰 ¥{item['item_price']:,}
🔗 {item['item_url']}
    """

    # Try to send photo
    if item.get('image_url'):
        try:
            bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=item['image_url'],
                caption=message
            )
            logger.info("✅ Telegram photo sent")
        except Exception as e:
            # Fallback to text-only if photo fails
            logger.warning(f"Photo failed, sending text: {e}")
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message
            )
    else:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
```

#### Pros:
- ✅ **FREE**
- ✅ Simple implementation (delete code!)
- ✅ No proxy needed
- ✅ No storage overhead (URLs are tiny)
- ✅ No database migration needed (image_url column already exists)

#### Cons:
- ❌ Images may NOT display in Web UI (browser still gets 403)
- ❌ iframe/object may be blocked by Cloudflare too
- ❌ Telegram photos will fail (403 when Telegram tries to fetch)
- ❌ If Mercari changes/deletes image, your link breaks
- ❌ Looks unprofessional (broken images or iframes)

#### Testing iframe approach:
```bash
# Test if iframe bypasses Cloudflare
# Open in browser:
data:text/html,<iframe src="https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m12345678901234567890.jpg" width="300" height="300"></iframe>

# If you see the image → ✅ Works
# If you see blank/403 → ❌ Doesn't work
```

**Reality check:** This approach likely **WON'T WORK** because the browser still fetches from Cloudflare, just in an iframe context. Cloudflare blocks by IP, not by how you embed the content.

---

## Solution 4: External Image Hosting (ImgBB, Imgur)

### How it works:
Download images on your LOCAL machine (not blocked), upload to ImgBB/Imgur (free hosting), store the ImgBB/Imgur URL in database.

### Option A: ImgBB (Free, unlimited storage)

#### Step 1: Get API Key
1. Sign up at https://imgbb.com/
2. Get API key from https://api.imgbb.com/

#### Step 2: Create Upload Function
```python
# image_utils.py
import requests
import base64
from typing import Optional

IMGBB_API_KEY = "your_imgbb_api_key"

def download_and_upload_to_imgbb(image_url: str) -> Optional[str]:
    """
    Download image from Mercari and upload to ImgBB
    Returns ImgBB URL on success
    """

    # Step 1: Download image from Mercari
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://jp.mercari.com/',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
    }

    try:
        # Download from Mercari
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)

        if response.status_code != 200:
            logger.warning(f"Failed to download: HTTP {response.status_code}")
            return None

        image_bytes = response.content

        # Check size (ImgBB max: 32MB, but we limit to 500KB)
        if len(image_bytes) / 1024 > 500:
            logger.warning(f"Image too large: {len(image_bytes)/1024:.1f}KB")
            return None

        # Step 2: Upload to ImgBB
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        upload_response = requests.post(
            'https://api.imgbb.com/1/upload',
            data={
                'key': IMGBB_API_KEY,
                'image': base64_image,
            },
            timeout=15
        )

        if upload_response.status_code != 200:
            logger.error(f"ImgBB upload failed: {upload_response.status_code}")
            return None

        result = upload_response.json()

        if result.get('success'):
            imgbb_url = result['data']['url']
            logger.info(f"✅ Uploaded to ImgBB: {imgbb_url}")
            return imgbb_url
        else:
            logger.error(f"ImgBB error: {result}")
            return None

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return None
```

#### Step 3: Update Core Logic
```python
# core.py (lines 386-416)
from image_utils import download_and_upload_to_imgbb

# Get ImgBB URL
imgbb_url = None
if image_url:
    logger.info(f"📤 Uploading to ImgBB: {image_url[:80]}...")
    imgbb_url = download_and_upload_to_imgbb(image_url)
    if imgbb_url:
        logger.info(f"✅ ImgBB URL: {imgbb_url}")

# Store ImgBB URL in database
db_item_id = self.db.add_item(
    # ... other fields ...
    image_url=imgbb_url,  # Store ImgBB URL, not Mercari URL
    image_data=None  # No base64 needed
)
```

#### Step 4: Update Web UI
```html
<!-- templates/items.html -->
{% if item.image_url %}
  <img src="{{ item.image_url }}" alt="{{ item.item_name }}" style="max-width: 200px;">
{% else %}
  <div style="width:200px; height:200px; background:#eee; text-align:center; padding:80px 0;">
    No image
  </div>
{% endif %}
```

#### Step 5: Telegram Bot
```python
# telegram_sender.py
def send_telegram_notification(item):
    message = f"""
🆕 New Item Found!

📦 {item['item_name']}
💰 ¥{item['item_price']:,}
🔗 {item['item_url']}
    """

    if item.get('image_url'):
        # ImgBB URLs work in Telegram!
        bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=item['image_url'],  # ImgBB URL
            caption=message
        )
    else:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
```

#### Pros:
- ✅ **FREE** (unlimited storage, no paid plan needed)
- ✅ 100% success rate for display (ImgBB never blocks)
- ✅ Works in Telegram photos
- ✅ Works in Web UI
- ✅ Fast CDN delivery
- ✅ Permanent URLs (don't expire)

#### Cons:
- ❌ Railway worker STILL can't download from Mercari (403 error)
- ❌ Only works if you run download+upload from LOCAL machine
- ❌ Manual/cron job needed
- ❌ Terms of Service: ImgBB may ban if used for scraping automation

**Critical limitation:** This only works if you download images from a NON-BLOCKED IP (like your home computer), then upload to ImgBB. Railway worker still gets 403 from Mercari.

---

### Option B: Imgur (Free, 1250 uploads/day)

Similar to ImgBB but with stricter limits.

#### API Setup:
1. Register app at https://api.imgur.com/oauth2/addclient
2. Get Client ID

#### Upload Function:
```python
# image_utils.py
IMGUR_CLIENT_ID = "your_client_id"

def download_and_upload_to_imgur(image_url: str) -> Optional[str]:
    """Upload to Imgur"""

    # Download from Mercari (same as ImgBB)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://jp.mercari.com/'
    }

    try:
        response = requests.get(image_url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        image_bytes = response.content
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Upload to Imgur
        upload_response = requests.post(
            'https://api.imgur.com/3/image',
            headers={'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'},
            data={'image': base64_image},
            timeout=15
        )

        if upload_response.status_code == 200:
            result = upload_response.json()
            imgur_url = result['data']['link']
            logger.info(f"✅ Uploaded to Imgur: {imgur_url}")
            return imgur_url
        else:
            logger.error(f"Imgur error: {upload_response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Imgur upload error: {e}")
        return None
```

#### Pros:
- ✅ Free (1250 uploads/day)
- ✅ 100% display success
- ✅ Works in Telegram

#### Cons:
- ❌ Upload limit: 1250/day (≈41 items/day max)
- ❌ Railway worker still blocked by Cloudflare
- ❌ Requires app registration

---

## Hybrid Approach: Local Script + Railway Worker

Since Railway is blocked, run image downloading on your LOCAL machine, upload to ImgBB/Imgur, then Railway worker uses those URLs.

### Implementation:

#### Local Script (run on your computer):
```python
# local_image_uploader.py
"""
Run this on your LOCAL machine (not Railway) to:
1. Download images from Mercari (works because your home IP isn't blocked)
2. Upload to ImgBB
3. Update database with ImgBB URLs
"""

import os
import psycopg2
from image_utils import download_and_upload_to_imgbb

# Database connection (same as Railway)
DATABASE_URL = os.environ.get('DATABASE_URL')  # Get from Railway

def upload_missing_images():
    """Find items without images and upload them"""

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Find items with Mercari URLs but no ImgBB URLs
    cur.execute("""
        SELECT id, image_url
        FROM items
        WHERE image_url LIKE '%mercdn.net%'
           OR image_url LIKE '%mercari-shops-static%'
        LIMIT 50
    """)

    items = cur.fetchall()
    print(f"Found {len(items)} items needing upload")

    for item_id, mercari_url in items:
        print(f"Processing item {item_id}...")

        # Download from Mercari and upload to ImgBB
        imgbb_url = download_and_upload_to_imgbb(mercari_url)

        if imgbb_url:
            # Update database with ImgBB URL
            cur.execute(
                "UPDATE items SET image_url = %s WHERE id = %s",
                (imgbb_url, item_id)
            )
            conn.commit()
            print(f"✅ Updated item {item_id}: {imgbb_url}")
        else:
            print(f"❌ Failed item {item_id}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    upload_missing_images()
```

#### Cron Job (run every hour):
```bash
# crontab -e
0 * * * * cd /path/to/MRS && /usr/bin/python3 local_image_uploader.py >> /var/log/image_upload.log 2>&1
```

#### Railway Worker Logic:
```python
# core.py
# Railway worker just stores Mercari URL (doesn't download)
# Local script will convert to ImgBB later

image_url = item_data.get('thumbnails', [None])[0]

db_item_id = self.db.add_item(
    # ...
    image_url=image_url,  # Mercari URL initially
    image_data=None
)
# Local script will update this to ImgBB URL
```

---

## Final Recommendations:

| Solution | Cost | Success Rate | Effort | Best For |
|----------|------|--------------|--------|----------|
| **ScraperAPI** | $49/mo | 95-99% | Low | Production use |
| **ProxyMesh** | $10/mo | 60-80% | Low | Budget production |
| **CF Worker** | $0 | 70-85% | Medium | Testing/hobby |
| **iframe/object** | $0 | 5-10% | Low | Won't work |
| **ImgBB (local)** | $0 | 100%* | High | Hybrid setup |
| **Imgur (local)** | $0 | 100%* | High | Hybrid setup |

*100% display success, but requires local machine to download

### My Recommendation:

**For immediate fix:** Use **Cloudflare Worker** (Solution 2) - it's free and has 70-85% chance of working.

**For production:** Use **ScraperAPI** (Solution 1A) - reliable but costs $49/month.

**For zero budget:** Use **ImgBB + Local Script** (Solution 4A with hybrid approach) - run local_image_uploader.py on your computer every hour.

---

**Next Steps:**
1. Choose a solution
2. I'll help implement it
3. Deploy and test
4. Monitor success rate

Which approach do you want to implement?
