#!/usr/bin/env python3
"""
Test with REAL Mercari URLs provided by user
Tests both search and specific item
"""

import sys
import logging
import asyncio
from mercapi import Mercapi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print(" REAL MERCARI TEST")
print("="*80 + "\n")

async def test_search():
    """Test search URL"""
    print("TEST 1: Search URL")
    print("URL: https://jp.mercari.com/search?keyword=archive%20...")
    print("-" * 80)

    m = Mercapi()

    # Extract search params from URL
    keyword = "archive "
    category_ids = [
        "d5dbe802-d454-4368-b988-5c14f003e507",  # Likely men's fashion
        "7cbcbdb2-e79a-412e-b568-6e519620c9aa",
        "54979258-8c53-47d7-8475-dbb156547650",
        "897918aa-7b7b-4da6-b7be-06accb9b4cac"
    ]

    try:
        # Search with keyword only first
        results = await m.search(query=keyword)

        print(f"\n✅ Search successful!")
        print(f"   Found: {len(results.items)} items")
        print(f"   Total available: {results.total or 'unknown'}")

        if results.items:
            print(f"\n📦 First 3 items:")
            for i, item in enumerate(results.items[:3], 1):
                item_id = getattr(item, 'id_', getattr(item, 'id', 'unknown'))
                print(f"\n   Item {i}:")
                print(f"   ID: {item_id}")
                print(f"   Title: {item.name[:60]}...")
                print(f"   Price: ¥{item.price}")
                print(f"   Status: {item.status}")

                # Try to get thumbnails
                thumbnails = getattr(item, 'thumbnails', [])
                if thumbnails:
                    print(f"   Image: {thumbnails[0][:80]}...")
                else:
                    print(f"   Image: None")

        return True
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_item():
    """Test specific item"""
    print("\n" + "="*80)
    print("TEST 2: Specific Item")
    print("URL: https://jp.mercari.com/item/m28611174799")
    print("ID: m28611174799")
    print("-" * 80)

    m = Mercapi()
    item_id = "m28611174799"

    try:
        item = await m.item(item_id)

        if item:
            print(f"\n✅ Item found!")
            print(f"   ID: {getattr(item, 'id_', item_id)}")
            print(f"   Title: {item.name}")
            print(f"   Price: ¥{item.price}")
            print(f"   Status: {item.status}")
            print(f"   Description: {item.description[:100] if item.description else 'None'}...")

            # Thumbnails
            thumbnails = getattr(item, 'thumbnails', [])
            if thumbnails:
                print(f"\n   📸 Images ({len(thumbnails)} total):")
                for i, url in enumerate(thumbnails[:3], 1):
                    print(f"      {i}. {url}")
            else:
                print(f"   📸 No images")

            # Photos (original quality)
            photos = getattr(item, 'photos', [])
            if photos:
                print(f"\n   🖼️  Original Photos ({len(photos)} total):")
                for i, url in enumerate(photos[:3], 1):
                    # Check if it's /orig/ path
                    is_orig = '/orig/' in url or '/detail/orig/' in url
                    quality = "ORIGINAL ✨" if is_orig else "thumbnail"
                    print(f"      {i}. {url[:80]}... [{quality}]")

            return True
        else:
            print(f"❌ Item not found or returned None")
            return False

    except Exception as e:
        print(f"❌ Item fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_image_download():
    """Test downloading image from real item"""
    print("\n" + "="*80)
    print("TEST 3: Image Download")
    print("-" * 80)

    from image_utils import download_and_encode_image
    from proxies import proxy_manager, proxy_rotator

    # Get item first
    m = Mercapi()
    item = await m.item("m28611174799")

    if not item:
        print("❌ Cannot test - item not found")
        return False

    thumbnails = getattr(item, 'thumbnails', [])
    photos = getattr(item, 'photos', [])

    if not thumbnails and not photos:
        print("❌ No images to test")
        return False

    test_url = photos[0] if photos else thumbnails[0]

    print(f"Image URL: {test_url[:80]}...")

    # Check proxy status
    if proxy_manager:
        stats = proxy_manager.get_proxy_stats()
        print(f"\n🔧 Proxy Manager: {stats['working']}/{stats['total']} working")
    else:
        print(f"\n⚠️  Proxy Manager NOT initialized")

    if proxy_rotator:
        current = proxy_rotator.get_proxy()
        if current:
            print(f"   Current proxy: {current.get('http', 'unknown')[:60]}...")
    else:
        print(f"⚠️  Proxy Rotator NOT initialized")

    # Try download
    print(f"\n📥 Downloading...")
    result = download_and_encode_image(test_url, timeout=15, use_proxy=True)

    if result:
        size_kb = len(result) / 1024
        print(f"✅ SUCCESS! Downloaded {size_kb:.1f}KB")
        return True
    else:
        print(f"❌ FAILED - HTTP 403 or timeout")
        return False

async def main():
    """Run all tests"""
    results = {}

    results['search'] = await test_search()
    results['item'] = await test_item()
    results['image'] = await test_image_download()

    # Summary
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\nTOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*80)

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
