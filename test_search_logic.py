#!/usr/bin/env python3
"""
Test script to diagnose why automatic scans don't find items
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db
from datetime import datetime
import pytz

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

def get_moscow_time():
    """Get current time in Moscow timezone"""
    return datetime.now(MOSCOW_TZ)

def main():
    print("=" * 60)
    print("MercariSearcher - Auto-Scan Diagnostic")
    print("=" * 60)

    db = get_db()

    # Check all searches
    all_searches = db.execute_query(
        "SELECT id, name, is_active, scan_interval, last_scanned_at, total_scans FROM searches",
        fetch=True
    )

    print(f"\n📊 Total searches in database: {len(all_searches)}")
    print()

    current_time = get_moscow_time()
    print(f"🕐 Current Moscow time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()

    for search in all_searches:
        print(f"🔍 Search: {search['name']}")
        print(f"   ID: {search['id']}")
        print(f"   Active: {search['is_active']}")
        print(f"   Scan Interval: {search['scan_interval']}s ({search['scan_interval']/60:.1f} min)")
        print(f"   Last Scanned: {search['last_scanned_at']}")
        print(f"   Total Scans: {search['total_scans']}")

        # Check if ready for scan
        if not search['is_active']:
            print(f"   ❌ NOT READY: Search is not active")
        elif search['last_scanned_at'] is None:
            print(f"   ✅ READY: Never scanned before")
        else:
            # Parse last scan time
            if isinstance(search['last_scanned_at'], str):
                last_scan = datetime.fromisoformat(search['last_scanned_at'].replace('Z', '+00:00'))
            else:
                last_scan = search['last_scanned_at']

            # Make timezone aware
            if last_scan.tzinfo is None:
                last_scan = MOSCOW_TZ.localize(last_scan)

            # Calculate next scan time
            from datetime import timedelta
            interval = search.get('scan_interval', 300)
            next_scan = last_scan + timedelta(seconds=interval)

            time_until_scan = (next_scan - current_time).total_seconds()

            if current_time >= next_scan:
                print(f"   ✅ READY: Next scan was {abs(time_until_scan):.0f}s ago")
            else:
                print(f"   ⏰ WAITING: Next scan in {time_until_scan:.0f}s ({time_until_scan/60:.1f} min)")

        print()

    # Get ready searches using the actual function
    ready_searches = db.get_searches_ready_for_scan()
    print(f"📋 Searches ready for scan (using db.get_searches_ready_for_scan()): {len(ready_searches)}")

    for search in ready_searches:
        print(f"   - {search['name']} (ID: {search['id']})")

    print()
    print("=" * 60)

    # Check recent items
    try:
        recent_items = db.execute_query(
            "SELECT id, title, found_at FROM items ORDER BY found_at DESC LIMIT 5",
            fetch=True
        )

        print(f"\n📦 Recent items in database: {len(recent_items)}")
        for item in recent_items:
            print(f"   - {item['title'][:50]}... (Found: {item['found_at']})")
    except Exception as e:
        print(f"\n❌ Could not fetch recent items: {e}")

    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
