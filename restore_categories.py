#!/usr/bin/env python3
"""
Restore lost category blacklist
"""
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from db import DatabaseManager

# Original 18 categories that were lost
ORIGINAL_CATEGORIES = [
    "ゲーム・おもちゃ・グッズ",
    "本・音楽・ゲーム",
    "エンタメ・ホビー",
    "ベビー・キッズ",
    "コスメ・美容",
    "CD・DVD・ブルーレイ",
    "フラワー・ガーデニング",
    "本・雑誌・漫画",
    "車・バイク・自転車",
    "その他",
    "生活家電・空調",
    "ホビー・楽器・アート",
    "家具・インテリア",
    "キッチン・日用品・その他",
    "スマホ・タブレット・パソコン",
    "ペット用品",
    "アウトドア・釣り・旅行用品",
    "チケット"
]

print("=" * 60)
print("RESTORING CATEGORY BLACKLIST")
print("=" * 60)
print()

db = DatabaseManager()

# Load current blacklist
current_blacklist = db.load_config('config_category_blacklist', default=[])
print(f"📊 Current blacklist: {current_blacklist}")
print(f"   Type: {type(current_blacklist)}")
print(f"   Count: {len(current_blacklist) if isinstance(current_blacklist, list) else 'N/A'}")
print()

# Convert to list if needed
if isinstance(current_blacklist, str):
    try:
        current_blacklist = json.loads(current_blacklist)
    except:
        current_blacklist = []

if not isinstance(current_blacklist, list):
    current_blacklist = []

print(f"🔄 Merging with {len(ORIGINAL_CATEGORIES)} original categories...")
print()

# Merge: add original categories that are not yet in the list
new_blacklist = list(current_blacklist)  # Make a copy
added_count = 0

for category in ORIGINAL_CATEGORIES:
    if category not in new_blacklist:
        new_blacklist.append(category)
        added_count += 1
        print(f"   ✅ Added: {category}")

print()
print(f"📈 Total added: {added_count}")
print(f"📋 New total: {len(new_blacklist)} categories")
print()

# Save to database
print("💾 Saving to database...")
blacklist_json = json.dumps(new_blacklist, ensure_ascii=False)
success = db.save_config('config_category_blacklist', blacklist_json)

if success:
    print("✅ Successfully restored category blacklist!")
    print()
    print("Final list:")
    for i, cat in enumerate(new_blacklist, 1):
        print(f"   {i}. {cat}")
else:
    print("❌ Failed to save to database!")
    sys.exit(1)

print()
print("=" * 60)
print()
