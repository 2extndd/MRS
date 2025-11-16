#!/usr/bin/env python3
"""
Railway API Setup - Direct REST approach
Uses Railway Public API v2
"""

import requests
import json
import time

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
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

def gql_request(query, variables=None):
    """Execute GraphQL query"""
    headers = {
        "Authorization": f"Bearer {RAILWAY_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(RAILWAY_API, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL Errors:")
        for err in data["errors"]:
            print(f"   {err.get('message', 'Unknown')}")
        return None

    return data.get("data")

print("═" * 70)
print("🚀 Railway API Setup - MercariSearcher")
print("═" * 70)
print()

# Step 1: Verify authentication
print("🔐 Verifying authentication...")
result = gql_request("""
query {
  me {
    id
    email
  }
}
""")

if result and "me" in result:
    print(f"✓ Authenticated as: {result['me'].get('email', 'Unknown')}")
else:
    print("❌ Authentication failed")
    exit(1)

# Step 2: Get project details
print()
print("📋 Getting project details...")
result = gql_request("""
query project($id: String!) {
  project(id: $id) {
    id
    name
    services {
      edges {
        node {
          id
          name
        }
      }
    }
    plugins {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
""", {"id": PROJECT_ID})

if not result or "project" not in result:
    print("❌ Failed to get project")
    exit(1)

project = result["project"]
print(f"✓ Project: {project['name']}")

existing_services = {s["node"]["name"]: s["node"]["id"] for s in project.get("services", {}).get("edges", [])}
existing_plugins = {p["node"]["name"]: p["node"]["id"] for p in project.get("plugins", {}).get("edges", [])}

print(f"  Services: {list(existing_services.keys()) or 'None'}")
print(f"  Plugins: {list(existing_plugins.keys()) or 'None'}")

# Step 3: Get environments
print()
print("🌍 Getting project environments...")
result = gql_request("""
query project($id: String!) {
  project(id: $id) {
    environments {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
""", {"id": PROJECT_ID})

if result and "project" in result:
    envs = result["project"].get("environments", {}).get("edges", [])
    if envs:
        env_id = envs[0]["node"]["id"]
        env_name = envs[0]["node"]["name"]
        print(f"✓ Using environment: {env_name} ({env_id})")
    else:
        print("⚠️  No environments found")
        env_id = None
else:
    print("⚠️  Could not fetch environments")
    env_id = None

# Step 4: Add PostgreSQL if not exists
if "postgresql" not in [p.lower() for p in existing_plugins.keys()]:
    print()
    print("🐘 Adding PostgreSQL plugin...")
    result = gql_request("""
    mutation pluginCreate($projectId: String!) {
      pluginCreate(input: {
        projectId: $projectId
        name: "postgresql"
      }) {
        id
        name
      }
    }
    """, {"projectId": PROJECT_ID})

    if result and "pluginCreate" in result:
        print(f"✓ PostgreSQL added: {result['pluginCreate']['id']}")
        time.sleep(2)
    else:
        print("⚠️  Could not add PostgreSQL")
else:
    print()
    print("🐘 PostgreSQL already exists")

# Step 5: Create service from template
print()
print("📦 Attempting to create service from GitHub repo...")

# Try using serviceConnect mutation
result = gql_request("""
mutation serviceConnect($projectId: String!, $repo: String!, $branch: String!) {
  serviceConnect(input: {
    projectId: $projectId
    repo: $repo
    branch: $branch
  }) {
    id
    name
  }
}
""", {
    "projectId": PROJECT_ID,
    "repo": f"https://github.com/{GITHUB_REPO}",
    "branch": "main"
})

if result and "serviceConnect" in result:
    service_id = result["serviceConnect"]["id"]
    service_name = result["serviceConnect"]["name"]
    print(f"✓ Service created: {service_name} ({service_id})")

    # Set environment variables
    if env_id:
        print()
        print("🔧 Setting environment variables...")
        for key, value in ENV_VARS.items():
            var_result = gql_request("""
            mutation variableUpsert($envId: String!, $serviceId: String!, $name: String!, $value: String!) {
              variableUpsert(input: {
                environmentId: $envId
                serviceId: $serviceId
                name: $name
                value: $value
              }) {
                id
              }
            }
            """, {
                "envId": env_id,
                "serviceId": service_id,
                "name": key,
                "value": value
            })

            if var_result:
                display_val = "***" if "TOKEN" in key else value
                print(f"  ✓ {key}={display_val}")
            else:
                print(f"  ⚠️  Failed to set {key}")

            time.sleep(0.5)
else:
    print("⚠️  Could not create service via API")
    print()
    print("📋 Manual setup required:")
    print(f"  1. Go to: https://railway.app/project/{PROJECT_ID}")
    print(f"  2. Click '+ New' → 'GitHub Repo'")
    print(f"  3. Select: {GITHUB_REPO}")
    print("  4. Create TWO services:")
    print("     - web: gunicorn --bind 0.0.0.0:$PORT wsgi:application")
    print("     - worker: python mercari_notifications.py worker")
    print()
    print("  5. Add environment variables to BOTH services:")
    for key, value in ENV_VARS.items():
        display_val = "***" if "TOKEN" in key else value
        print(f"     {key}={display_val}")

print()
print("═" * 70)
print("✅ Setup process completed")
print("═" * 70)
print()
print(f"📍 Dashboard: https://railway.app/project/{PROJECT_ID}")
print()
