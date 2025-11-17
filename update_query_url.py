#!/usr/bin/env python3
"""
Update query URL in Railway database
"""

import requests
import json

# Railway web service URL
BASE_URL = "https://web-production-fe38.up.railway.app"

# New correct URL with filters
NEW_URL = "https://jp.mercari.com/search?keyword=Y-3%20&f42ae390-04ff-46ea-808b-f5d97cb45db4=d5dbe802-d454-4368-b988-5c14f003e507%2C7cbcbdb2-e79a-412e-b568-6e519620c9aa%2Ce69a18b7-3a5b-4f20-855e-ae143007a36c%2C54979258-8c53-47d7-8475-dbb156547650%2C897918aa-7b7b-4da6-b7be-06accb9b4cac"

print("=" * 80)
print("🔄 UPDATING QUERY URL")
print("=" * 80)
print()

# Get current query
print("📍 Fetching current query...")
response = requests.get(f"{BASE_URL}/api/queries")

if response.status_code != 200:
    print(f"❌ Failed to fetch queries: {response.status_code}")
    print(f"   Response: {response.text}")
    exit(1)

data = response.json()
queries = data.get("queries", [])

if not queries:
    print("❌ No queries found in database!")
    exit(1)

current_query = queries[0]
print(f"✅ Found query ID={current_query['id']}: {current_query['name']}")
print(f"   Current URL: {current_query['search_url'][:80]}...")
print()

# Update the query
print("🔧 Updating URL...")
update_data = {
    "name": current_query["name"],
    "search_url": NEW_URL,
    "telegram_chat_id": current_query["telegram_chat_id"],
    "is_active": current_query["is_active"],
    "scan_interval": current_query["scan_interval"],
    "brand_filter": current_query.get("brand_filter"),
    "min_price": current_query.get("min_price"),
    "max_price": current_query.get("max_price"),
    "condition_filter": current_query.get("condition_filter"),
    "size_filter": current_query.get("size_filter")
}

response = requests.put(
    f"{BASE_URL}/api/queries/{current_query['id']}",
    json=update_data,
    headers={"Content-Type": "application/json"}
)

if response.status_code == 200:
    print("✅ URL updated successfully!")
    result = response.json()
    print(f"\n   Response: {json.dumps(result, indent=2)}")
else:
    print(f"❌ Failed to update URL: {response.status_code}")
    print(f"   Response: {response.text}")
    exit(1)

print()

# Verify the update
print("🔍 Verifying update...")
response = requests.get(f"{BASE_URL}/api/queries")
data = response.json()
updated_query = data["queries"][0]

print(f"✅ Updated URL:")
print(f"   {updated_query['search_url']}")
print()
print("=" * 80)
print("✅ QUERY URL UPDATED!")
print("=" * 80)
print()
print("⚠️  NEXT STEP: Add DATABASE_URL to worker service!")
print("   1. Open: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d")
print("   2. Select 'worker' service")
print("   3. Variables → Add Variable Reference")
print("   4. Select: Postgres-T-E-.DATABASE_URL")
print("   5. Worker will auto-redeploy and connect to PostgreSQL")
print()
