#!/usr/bin/env python3
"""Check database for blacklist entries"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from db import DatabaseManager

db = DatabaseManager()

print("=" * 60)
print("CHECKING DATABASE FOR BLACKLIST ENTRIES")
print("=" * 60)
print()

# Check for all keys containing "blacklist" or "category"
query = """
    SELECT key, value, updated_at
    FROM key_value_store
    WHERE key LIKE '%blacklist%' OR key LIKE '%category%'
    ORDER BY key
"""

results = db.execute_query(query)

if results:
    for row in results:
        key = row[0]
        value = row[1]
        updated = row[2] if len(row) > 2 else 'N/A'

        print(f"Key: {key}")
        print(f"Updated: {updated}")
        print(f"Value: {value[:200]}...")
        print("-" * 60)
        print()
else:
    print("❌ No blacklist entries found!")
    print()

print("=" * 60)
