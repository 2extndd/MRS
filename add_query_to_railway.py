#!/usr/bin/env python3
"""
Add query to Railway database directly
"""

import requests
import json

# Railway web API endpoint
RAILWAY_WEB_URL = "https://web-production-fe38.up.railway.app"

def add_query():
    """Add test query to Railway database via web API"""

    print("=" * 80)
    print("ADDING QUERY TO RAILWAY DATABASE")
    print("=" * 80)

    # Query data
    query_data = {
        "name": "Y-3 Clothing & Shoes",
        "search_url": "https://jp.mercari.com/search?keyword=Y-3",
        "telegram_chat_id": "-4997297083",
        "is_active": True,
        "scan_interval": 300,
        "brand_filter": "Y-3",
        "min_price": None,
        "max_price": None,
        "condition_filter": None,
        "size_filter": None
    }

    print(f"\nQuery to add:")
    print(f"  Name: {query_data['name']}")
    print(f"  URL: {query_data['search_url']}")
    print(f"  Chat ID: {query_data['telegram_chat_id']}")
    print(f"  Active: {query_data['is_active']}")
    print(f"  Scan Interval: {query_data['scan_interval']}s")

    # Add query via API
    print(f"\nSending POST request to {RAILWAY_WEB_URL}/api/queries/add...")

    try:
        response = requests.post(
            f"{RAILWAY_WEB_URL}/api/queries/add",
            json=query_data,
            timeout=10
        )

        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS!")
            print(f"Response: {json.dumps(result, indent=2)}")

            # Verify by checking queries list
            print(f"\nVerifying query was added...")
            verify_response = requests.get(f"{RAILWAY_WEB_URL}/api/queries", timeout=10)

            if verify_response.status_code == 200:
                queries = verify_response.json().get('queries', [])
                print(f"Total queries in database: {len(queries)}")

                if queries:
                    print(f"\nFirst 3 queries:")
                    for i, q in enumerate(queries[:3], 1):
                        print(f"  {i}. {q.get('name')} - Active: {q.get('is_active')}")

                return True

        else:
            print(f"❌ ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    success = add_query()
    print("\n" + "=" * 80)
    if success:
        print("✅ QUERY ADDED TO RAILWAY DATABASE")
        print("\nNext: Wait for worker to pick it up (check logs)")
        print("  Railway Dashboard → worker service → Logs")
    else:
        print("❌ FAILED TO ADD QUERY")
    print("=" * 80)
    print()
