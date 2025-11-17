#!/usr/bin/env python3
"""
Test Mercari API functionality using pyMercariAPI
Tests the actual Mercari search with mercapi library
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyMercariAPI import Mercari
import json

def test_mercari_api():
    """Test Mercari API with user's search"""

    # User's search keyword from URL
    keyword = "Y-3"

    print("="*80)
    print("🧪 MERCARI API TEST")
    print("="*80)
    print(f"\n📍 Testing search:")
    print(f"   Keyword: {keyword}\n")

    # Initialize API
    api = Mercari()

    print("🔍 Searching Mercari.jp via API...")
    try:
        # Search using API (sync wrapper)
        results = api.search(keyword, limit=10)

        print(f"\n✅ Search completed successfully!")
        print(f"📦 Found {len(results)} items\n")

        if results:
            print("=" * 80)
            print("FIRST 3 ITEMS:")
            print("=" * 80)

            for i, item in enumerate(results[:3], 1):
                print(f"\n--- ITEM #{i} ---")
                item_dict = item.to_dict() if hasattr(item, 'to_dict') else item

                print(f"ID:        {item_dict.get('id', 'N/A')}")
                print(f"Name:      {item_dict.get('name', 'N/A')[:60]}...")
                print(f"Price:     ¥{item_dict.get('price', 0):,}")
                print(f"Status:    {item_dict.get('status', 'N/A')}")

                if item_dict.get('url'):
                    print(f"Link:      {item_dict.get('url')}")
                if item_dict.get('image_url'):
                    print(f"Image:     {item_dict.get('image_url')[:60]}...")
                if item_dict.get('brand'):
                    print(f"Brand:     {item_dict.get('brand')}")
                if item_dict.get('size'):
                    print(f"Size:      {item_dict.get('size')}")
                if item_dict.get('condition'):
                    print(f"Condition: {item_dict.get('condition')}")

            # Show full JSON for first item
            print("\n" + "=" * 80)
            print("FULL JSON FOR FIRST ITEM:")
            print("=" * 80)
            first_item = results[0].to_dict() if hasattr(results[0], 'to_dict') else results[0]
            print(json.dumps(first_item, indent=2, ensure_ascii=False))

            return True

        else:
            print("⚠️  No items found!")
            print("   This might indicate:")
            print("   - No items match the search")
            print("   - API is rate limited")
            print("   - API connection issue")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    # Run sync function (it uses sync wrapper internally)
    success = test_mercari_api()

    print("\n" + "=" * 80)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
