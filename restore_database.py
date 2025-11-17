#!/usr/bin/env python3
"""
Restore database by adding test query directly via PostgreSQL
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import DatabaseManager
import json

def restore_database():
    """Add test query to database"""

    print("="*80)
    print("🔧 DATABASE RESTORATION")
    print("="*80)

    # Get Railway DATABASE_URL
    import subprocess
    try:
        result = subprocess.run(
            ["railway", "service", "web", "&&", "railway", "variables"],
            capture_output=True,
            text=True,
            shell=True
        )
        output = result.stdout
        # Extract DATABASE_URL
        for line in output.split('\n'):
            if 'DATABASE_URL' in line and 'postgresql://' in line:
                # Extract the URL between │ symbols
                parts = line.split('│')
                if len(parts) >= 3:
                    db_url = parts[2].strip()
                    os.environ['DATABASE_URL'] = db_url
                    print(f"✅ Found Railway DATABASE_URL")
                    break
    except Exception as e:
        print(f"⚠️  Could not get Railway DATABASE_URL: {e}")
        print(f"   Using local database instead")

    # Initialize DB
    db = DatabaseManager()

    print(f"\n✅ Connected to: {db.db_type}")
    if db.db_type == 'postgresql':
        print(f"   PostgreSQL connection established\n")
    else:
        print(f"   SQLite (local): mercari_scanner.db\n")

    # Check current queries
    print("📊 Checking current queries...")
    queries = db.get_all_queries()
    print(f"   Found {len(queries)} existing queries\n")

    if queries:
        print("Existing queries:")
        for q in queries:
            print(f"   - {q.get('name')} ({q.get('search_url')[:50]}...)")
        print()

    # Add test query
    print("➕ Adding test query...")

    test_query = {
        "name": "Y-3 Clothing & Shoes",
        "search_url": "https://jp.mercari.com/search?keyword=Y-3",
        "telegram_chat_id": "-4997297083",
        "is_active": True,
        "scan_interval": 300,
        "brand_filter": "Y-3",
        "min_price": None,
        "max_price": None,
        "condition_filter": None,
        "size_filter": None,
        "price_drop_threshold": 0
    }

    try:
        query_id = db.add_query(**test_query)
        print(f"   ✅ Query added! ID: {query_id}\n")

        # Verify
        queries_after = db.get_all_queries()
        print(f"📊 Total queries now: {len(queries_after)}")

        for q in queries_after:
            print(f"\n   📍 Query: {q.get('name')}")
            print(f"      ID: {q.get('id')}")
            print(f"      URL: {q.get('search_url')[:60]}...")
            print(f"      Active: {q.get('is_active')}")
            print(f"      Interval: {q.get('scan_interval')}s")
            print(f"      Chat ID: {q.get('telegram_chat_id')}")

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    success = restore_database()
    print("\n" + "=" * 80)
    if success:
        print("✅ DATABASE RESTORED!")
        print("\nNext: Check worker logs to see if it finds the query:")
        print("  railway service worker && railway logs")
    else:
        print("❌ RESTORATION FAILED")
    print("=" * 80)
    print()

    sys.exit(0 if success else 1)
