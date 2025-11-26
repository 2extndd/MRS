#!/usr/bin/env python3
"""
Check why item m10618241843 with blacklisted category is in database
Run this on Railway to access PostgreSQL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db
from configuration_values import config

print("="*60)
print("BLACKLIST ISSUE INVESTIGATION")
print("="*60)

db = get_db()
print(f"\nDatabase type: {db.db_type}")

# Item to investigate
ITEM_ID = "m10618241843"
EXPECTED_CATEGORY = "スマホ・タブレット・パソコン"

print(f"\nSearching for item: {ITEM_ID}")
print(f"Expected category: {EXPECTED_CATEGORY}")

# Check if item exists
query = """
    SELECT id, mercari_id, title, category, found_at, search_id
    FROM items
    WHERE mercari_id = %s
"""

result = db.execute_query(query, (ITEM_ID,), fetch=True)

if result:
    item = result[0]
    print(f"\n{'='*60}")
    print("✅ ITEM FOUND IN DATABASE")
    print(f"{'='*60}")
    print(f"ID: {item['id']}")
    print(f"Mercari ID: {item['mercari_id']}")
    print(f"Title: {item['title']}")
    print(f"Category: {item['category']}")
    print(f"Found at: {item['found_at']}")
    print(f"Search ID: {item.get('search_id', 'N/A')}")
    
    # Load blacklist from database
    print(f"\n{'='*60}")
    print("LOADING BLACKLIST FROM DATABASE")
    print(f"{'='*60}")
    
    # Force reload config
    config._last_reload_time = 0
    config.reload_if_needed()
    
    print(f"\nTotal categories in blacklist: {len(config.CATEGORY_BLACKLIST)}")
    print(f"Blacklist type: {type(config.CATEGORY_BLACKLIST)}")
    
    if config.CATEGORY_BLACKLIST:
        print(f"\nAll blacklisted categories:")
        for i, cat in enumerate(config.CATEGORY_BLACKLIST, 1):
            print(f"   {i}. {cat}")
            if cat == EXPECTED_CATEGORY:
                print(f"      ⚠️  MATCH! This is the item's category!")
    else:
        print("⚠️  Blacklist is EMPTY!")
    
    # Check if item's category is in blacklist
    item_category = item['category']
    print(f"\n{'='*60}")
    print("BLACKLIST CHECK")
    print(f"{'='*60}")
    print(f"Item category: '{item_category}'")
    
    if item_category == EXPECTED_CATEGORY:
        print(f"✅ Category matches expected")
    else:
        print(f"⚠️  Category different from expected!")
    
    # Check exact match
    if item_category in config.CATEGORY_BLACKLIST:
        print(f"\n❌ PROBLEM FOUND!")
        print(f"   Category '{item_category}' IS in blacklist (exact match)")
        print(f"   This item should have been REJECTED!")
    else:
        # Check substring match (как в core.py)
        matched = False
        for blacklisted_cat in config.CATEGORY_BLACKLIST:
            if blacklisted_cat in item_category:
                print(f"\n❌ PROBLEM FOUND!")
                print(f"   Category contains blacklisted substring!")
                print(f"   Item category: '{item_category}'")
                print(f"   Matched blacklist entry: '{blacklisted_cat}'")
                matched = True
                break
        
        if not matched:
            print(f"\n✅ No problem - category NOT in blacklist")
            print(f"   Item was correctly added to database")
    
    # Check when item was added vs when category was added to blacklist
    print(f"\n{'='*60}")
    print("TIMING ANALYSIS")
    print(f"{'='*60}")
    print(f"Item added: {item['found_at']}")
    
    # Try to find when category was added to blacklist
    # (This would require audit logs, which we might not have)
    print(f"\nPossible scenarios:")
    print(f"1. Item added BEFORE category was blacklisted")
    print(f"2. Blacklist was not loaded at time of scan")
    print(f"3. Bug in filtering logic")
    
else:
    print(f"\n❌ Item {ITEM_ID} NOT found in database")
    print(f"\nThis could mean:")
    print(f"1. Item was never added (correctly filtered)")
    print(f"2. Item was deleted")
    print(f"3. Wrong database being checked")

# Additional checks
print(f"\n{'='*60}")
print("ADDITIONAL DATABASE CHECKS")
print(f"{'='*60}")

# Count total items
total_result = db.execute_query("SELECT COUNT(*) as count FROM items", fetch=True)
total_items = total_result[0]['count'] if total_result else 0
print(f"Total items in database: {total_items}")

# Count items with this category
cat_result = db.execute_query(
    "SELECT COUNT(*) as count FROM items WHERE category = %s",
    (EXPECTED_CATEGORY,),
    fetch=True
)
cat_count = cat_result[0]['count'] if cat_result else 0
print(f"Items with category '{EXPECTED_CATEGORY}': {cat_count}")

if cat_count > 0:
    print(f"\n⚠️  WARNING: {cat_count} items with blacklisted category in database!")
    
    # Show sample
    sample = db.execute_query(
        "SELECT mercari_id, title, found_at FROM items WHERE category = %s ORDER BY found_at DESC LIMIT 5",
        (EXPECTED_CATEGORY,),
        fetch=True
    )
    
    if sample:
        print(f"\nSample items:")
        for item in sample:
            print(f"  - {item['mercari_id']}: {item['title'][:50]}... ({item['found_at']})")

print(f"\n{'='*60}\n")
