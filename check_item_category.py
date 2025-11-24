#!/usr/bin/env python3
"""Check category for specific Shops item"""
import asyncio
import sys
sys.path.insert(0, '.')

async def check_item():
    from mercapi import Mercapi

    m = Mercapi()

    # Search for "archive" to find Shops items
    print("Searching for archive items...")
    results = await m.search(query="archive")

    target_id = "2JHRdD4gvpxGpLntnGhNSH"

    print(f"\nLooking for item: {target_id}")
    print("=" * 60)

    found = False
    for item in results.items:
        item_id = getattr(item, 'id_', None)
        if item_id == target_id:
            found = True
            print(f"✅ FOUND!")
            print(f"   ID: {item_id}")
            print(f"   Name: {getattr(item, 'name', 'N/A')}")
            print(f"   Price: ¥{getattr(item, 'price', 0)}")

            # Check category_id
            if hasattr(item, 'category_id'):
                cat_id = item.category_id
                print(f"   category_id: {cat_id}")
                print(f"   Format for blacklist: ID:{cat_id}")
            else:
                print(f"   ⚠️  No category_id attribute")

            break

    if not found:
        print(f"❌ Item {target_id} not found in search results")
        print(f"   (might not be in first 100 results for 'archive')")

asyncio.run(check_item())
