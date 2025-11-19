#!/usr/bin/env python3
"""
Verify proxy configuration is loaded correctly
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print(" PROXY CONFIGURATION VERIFICATION")
print("="*80 + "\n")

# 1. Check configuration_values.py
print("1. Checking configuration_values.py...")
import configuration_values as config

print(f"   PROXY_ENABLED: {config.PROXY_ENABLED}")
print(f"   PROXY_LIST type: {type(config.PROXY_LIST)}")
print(f"   PROXY_LIST length: {len(config.PROXY_LIST)}")

if config.PROXY_LIST:
    print(f"   First proxy: {config.PROXY_LIST[0][:60]}...")
    print(f"   Last proxy: {config.PROXY_LIST[-1][:60]}...")
else:
    print("   ⚠️  PROXY_LIST is empty!")

# 2. Check proxies.py module initialization
print("\n2. Checking proxies.py module...")
from proxies import proxy_manager, proxy_rotator

if proxy_manager:
    stats = proxy_manager.get_proxy_stats()
    print(f"   ✅ ProxyManager initialized")
    print(f"   Total proxies: {stats['total']}")
    print(f"   Working proxies: {stats['working']}")
    print(f"   Failed proxies: {stats['failed']}")
else:
    print("   ❌ ProxyManager NOT initialized")
    print("   This means:")
    print("      - Either PROXY_ENABLED = False")
    print("      - Or PROXY_LIST is empty")
    print("      - Or ProxyManager init failed")

if proxy_rotator:
    print(f"   ✅ ProxyRotator initialized")
    current = proxy_rotator.get_proxy()
    if current:
        print(f"   Current proxy: {current.get('http', 'unknown')[:60]}...")
else:
    print("   ❌ ProxyRotator NOT initialized")

# 3. Test image download with proxy
print("\n3. Testing image download...")
from image_utils import download_and_encode_image

test_url = "https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m18043642062_1.jpg"
print(f"   URL: {test_url[:70]}...")

result = download_and_encode_image(test_url, timeout=15, use_proxy=True)

if result:
    size_kb = len(result) / 1024
    print(f"   ✅ SUCCESS! Downloaded {size_kb:.1f}KB")
else:
    print(f"   ❌ FAILED to download image")
    print(f"   This usually means:")
    print(f"      - Cloudflare blocked the request (403)")
    print(f"      - Proxy connection failed")
    print(f"      - Proxy system not initialized")

# 4. Check database config
print("\n4. Checking database config...")
try:
    from db_utils import db_connection_manager

    with db_connection_manager.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM key_value_store WHERE key = 'config_proxy_enabled'")
            row = cur.fetchone()
            db_proxy_enabled = row[0] if row else 'NOT SET'
            print(f"   DB config_proxy_enabled: {db_proxy_enabled}")

            cur.execute("SELECT value FROM key_value_store WHERE key = 'config_proxy_list'")
            row = cur.fetchone()
            if row:
                proxy_count = len([p for p in row[0].split('\n') if p.strip()])
                print(f"   DB config_proxy_list: {proxy_count} proxies")
            else:
                print(f"   DB config_proxy_list: NOT SET")
except Exception as e:
    print(f"   ⚠️  Database check failed: {e}")

print("\n" + "="*80)
print(" SUMMARY")
print("="*80)

if proxy_manager and proxy_rotator and result:
    print("✅ ALL SYSTEMS GO - Proxies working correctly")
    sys.exit(0)
elif proxy_manager and proxy_rotator:
    print("⚠️  Proxy system initialized but image download failed")
    print("   Check if proxies are blocked by Cloudflare")
    sys.exit(1)
else:
    print("❌ PROXY SYSTEM NOT INITIALIZED")
    print("   Worker needs restart to load proxy config")
    sys.exit(1)
