#!/usr/bin/env python3
"""
Direct Railway Deployment via API
Using environment ID from URL
"""

import requests
import json
import time

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
ENVIRONMENT_ID = "acc3b600-3ee9-4e2b-9070-a5a6f3403fd8"
GITHUB_REPO = "2extndd/MRS"
RAILWAY_API = "https://backboard.railway.app/graphql/v2"

TELEGRAM_BOT_TOKEN = "8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw"
TELEGRAM_CHAT_ID = "-4997297083"

ENV_VARS = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    "DISPLAY_CURRENCY": "USD",
    "USD_CONVERSION_RATE": "0.0067",
    "SEARCH_INTERVAL": "300",
    "MAX_ITEMS_PER_SEARCH": "50",
    "REQUEST_DELAY_MIN": "1.5",
    "REQUEST_DELAY_MAX": "3.5",
    "LOG_LEVEL": "INFO"
}

def api(query, variables=None):
    headers = {
        "Authorization": f"Bearer {RAILWAY_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(RAILWAY_API, headers=headers, json={"query": query, "variables": variables or {}})

    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:300]}")
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ Errors:")
        for e in data["errors"]:
            print(f"   {e.get('message')}")
        return None

    return data.get("data")

print("=" * 70)
print("🚀 DIRECT RAILWAY DEPLOYMENT")
print("=" * 70)

# Step 1: Add PostgreSQL
print("\n🐘 Adding PostgreSQL...")
result = api("""
mutation {
  pluginCreate(input: {
    projectId: "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
    name: "postgresql"
  }) {
    id
  }
}
""")

if result:
    print(f"✓ PostgreSQL added")
else:
    print("⚠️  PostgreSQL failed (might exist)")

time.sleep(2)

# Step 2: Create service from GitHub
print("\n📦 Creating service from GitHub...")
result = api("""
mutation {
  serviceCreate(input: {
    projectId: "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
    source: {
      repo: "2extndd/MRS"
    }
  }) {
    id
    name
  }
}
""")

if result and "serviceCreate" in result:
    service_id = result["serviceCreate"]["id"]
    print(f"✓ Service created: {service_id}")

    # Set variables
    print("\n🔧 Setting environment variables...")
    for key, value in ENV_VARS.items():
        var_result = api("""
        mutation($serviceId: String!, $envId: String!, $name: String!, $value: String!) {
          variableUpsert(input: {
            serviceId: $serviceId
            environmentId: $envId
            name: $name
            value: $value
          }) {
            id
          }
        }
        """, {
            "serviceId": service_id,
            "envId": ENVIRONMENT_ID,
            "name": key,
            "value": value
        })

        display = "***" if "TOKEN" in key else value
        if var_result:
            print(f"  ✓ {key}={display}")
        else:
            print(f"  ✗ {key} failed")
        time.sleep(0.3)

    # Set start command for web
    print("\n⚙️  Setting start command...")
    api("""
    mutation($serviceId: String!) {
      serviceUpdate(input: {
        serviceId: $serviceId
        startCommand: "gunicorn --bind 0.0.0.0:$PORT --timeout 30 wsgi:application"
      })
    }
    """, {"serviceId": service_id})

    print("\n✅ WEB SERVICE CREATED!")
    print(f"Service ID: {service_id}")

else:
    print("❌ Failed to create service")

print("\n" + "=" * 70)
print("✅ DEPLOYMENT COMPLETED")
print("=" * 70)
print(f"\n📍 Check: https://railway.app/project/{PROJECT_ID}")
