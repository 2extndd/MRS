#!/usr/bin/env python3
"""
Test image download from specific Mercari items
https://jp.mercari.com/item/m18043642062
https://jp.mercari.com/item/m44454223480
"""

import sys
import logging
from mercapi import Mercapi
from image_utils import download_and_encode_image
from proxies import proxy_manager, proxy_rotator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_item_image_download(item_id: str, image_url: str):
    """Test downloading image from specific Mercari item"""

    print(f"\n{'='*80}")
    print(f"Testing item: {item_id}")
    print(f"URL: https://jp.mercari.com/item/{item_id}")
    print(f"Image: {image_url[:80]}...")
    print(f"{'='*80}\n")

    try:
        logger.info(f"📸 Testing image download from Mercari CDN...")

        # Check proxy system status
        if proxy_manager:
            stats = proxy_manager.get_proxy_stats()
            logger.info(f"🔧 Proxy Manager:")
            logger.info(f"   Total proxies: {stats['total']}")
            logger.info(f"   Working: {stats['working']}")
            logger.info(f"   Failed: {stats['failed']}")
        else:
            logger.warning(f"⚠️  Proxy Manager NOT initialized (proxies disabled or no proxies configured)")

        if proxy_rotator:
            logger.info(f"🔄 Proxy Rotator: Active (rotation count: {proxy_rotator.rotation_count})")
            current_proxy_dict = proxy_rotator.get_proxy()
            if current_proxy_dict:
                logger.info(f"   Current proxy: {current_proxy_dict.get('http', 'unknown')[:60]}...")
        else:
            logger.warning(f"⚠️  Proxy Rotator NOT initialized")

        # Download and encode image
        logger.info(f"\n📥 Downloading image...")
        result = download_and_encode_image(image_url, timeout=15, use_proxy=True)

        if result:
            size_kb = len(result) / 1024
            logger.info(f"✅ SUCCESS! Image downloaded and encoded")
            logger.info(f"   Size: {size_kb:.1f}KB base64")
            logger.info(f"   Format: {result[:30]}...")
            return True
        else:
            logger.error(f"❌ FAILED to download image")
            logger.error(f"   This usually means:")
            logger.error(f"   1. Cloudflare is blocking the IP (403)")
            logger.error(f"   2. Proxy connection failed")
            logger.error(f"   3. Network timeout")
            return False

    except Exception as e:
        logger.error(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test both items"""

    print("\n" + "="*80)
    print(" MERCARI IMAGE DOWNLOAD TEST")
    print("="*80)

    # Test with sample image URLs (you can get these by visiting the item pages)
    test_items = [
        ('m18043642062', 'https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m18043642062_1.jpg'),
        ('m44454223480', 'https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m44454223480_1.jpg'),
    ]

    results = {}

    for item_id, image_url in test_items:
        results[item_id] = test_item_image_download(item_id, image_url)

    # Summary
    print("\n" + "="*80)
    print(" TEST SUMMARY")
    print("="*80)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for item_id, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - https://jp.mercari.com/item/{item_id}")

    print("="*80)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*80)

    if passed == 0:
        print("\n⚠️  ALL TESTS FAILED")
        print("Possible reasons:")
        print("1. Proxies are disabled → Enable in Web UI config")
        print("2. All proxies are blocked/dead → Check proxy quality")
        print("3. Railway IP blocked by Cloudflare → This is expected without proxy")
        print("\nTo fix:")
        print("- Enable proxies in Web UI: https://web-production-fe38.up.railway.app/config")
        print("- Check proxy_enabled checkbox")
        print("- Save settings")
        print("- Wait 10 seconds for hot reload")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
