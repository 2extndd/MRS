#!/usr/bin/env python3
"""
Test Mercari search functionality
Tests the actual Mercari.jp URL provided by the user
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mercari_scraper import MercariScraper
import json

def test_mercari_search():
    """Test Mercari search with user's URL"""

    # User's URL: https://jp.mercari.com/search?keyword=Y-3%20 ...
    test_url = "https://jp.mercari.com/search?keyword=Y-3%20&f42ae390-04ff-46ea-808b-f5d97cb45db4=d5dbe802-d454-4368-b988-5c14f003e507%2C7cbcbdb2-e79a-412e-b568-6e519620c9aa%2Ce69a18b7-3a5b-4f20-855e-ae143007a36c%2C54979258-8c53-47d7-8475-dbb156547650%2C897918aa-7b7b-4da6-b7be-06accb9b4cac"

    print("="*80)
    print("🧪 MERCARI SEARCH TEST")
    print("="*80)
    print(f"\n📍 Testing URL:")
    print(f"   {test_url}\n")

    # Initialize scraper
    scraper = MercariScraper()

    # Perform search
    print("🔍 Searching Mercari.jp...")
    try:
        results = scraper.search_items(test_url, limit=50)

        print(f"\n✅ Search completed successfully!")
        print(f"📦 Found {len(results)} items\n")

        if results:
            print("=" * 80)
            print("FIRST 3 ITEMS:")
            print("=" * 80)

            for i, item in enumerate(results[:3], 1):
                print(f"\n--- ITEM #{i} ---")
                print(f"ID:        {item.get('id', 'N/A')}")
                print(f"Name:      {item.get('name', 'N/A')[:60]}...")
                print(f"Price:     ¥{item.get('price', 0):,}")
                print(f"Status:    {item.get('status', 'N/A')}")
                print(f"Link:      {item.get('url', 'N/A')}")

                if item.get('image_url'):
                    print(f"Image:     {item.get('image_url')[:60]}...")

                # Additional fields
                if item.get('brand'):
                    print(f"Brand:     {item.get('brand')}")
                if item.get('size'):
                    print(f"Size:      {item.get('size')}")
                if item.get('condition'):
                    print(f"Condition: {item.get('condition')}")

            # Show full JSON for first item
            print("\n" + "=" * 80)
            print("FULL JSON FOR FIRST ITEM:")
            print("=" * 80)
            print(json.dumps(results[0], indent=2, ensure_ascii=False))

        else:
            print("⚠️  No items found!")
            print("   This might indicate:")
            print("   - URL is invalid")
            print("   - No items match the search")
            print("   - Mercari blocked the request")
            print("   - Parser needs updating")

        return len(results) > 0

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_mercari_search()

    print("\n" + "=" * 80)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 80)

    sys.exit(0 if success else 1)
