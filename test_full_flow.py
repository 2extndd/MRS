#!/usr/bin/env python3
"""
Test the full flow: mercapi search -> Item creation -> check category
"""
import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s [%(name)s]: %(message)s'
)

async def test_full_flow():
    """Test full flow from search to Item object"""
    try:
        # Import pyMercariAPI
        sys.path.insert(0, '.')
        from pyMercariAPI.mercari import Mercari

        # Create API instance
        api = Mercari()

        # Search for "archive"
        print("\n" + "="*60)
        print("Testing Mercari.search() method")
        print("="*60)

        # Use a real Mercari search URL that returns Shops items
        search_url = "https://jp.mercari.com/search?keyword=archive"

        results = api.search(search_url, limit=5)

        print(f"\nGot {len(results)} items from search")

        # Check each item
        for idx, item in enumerate(results.items, 1):
            is_shops = not item.id.startswith('m')
            print(f"\n{'='*60}")
            print(f"Item {idx}: {item.id} ({'SHOPS' if is_shops else 'REGULAR'})")
            print(f"  Title: {item.title[:50]}...")
            print(f"  Category: '{item.category}'")
            print(f"  Price: ¥{item.price}")

            if is_shops and not item.category:
                print("  ⚠️  WARNING: Shops item has no category!")
            elif is_shops and item.category:
                print(f"  ✅ SUCCESS: Shops item has category: {item.category}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_full_flow())
