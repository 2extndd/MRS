#!/usr/bin/env python3
"""
Railway Project Setup Script v2
Fixed GraphQL queries for Railway API
"""

import requests
import json
import sys

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
GITHUB_REPO = "2extndd/MRS"
GITHUB_BRANCH = "main"
RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

TELEGRAM_BOT_TOKEN = "8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw"
TELEGRAM_CHAT_ID = "-4997297083"

def railway_query(query, variables=None):
    """Execute GraphQL query"""
    headers = {
        "Authorization": f"Bearer {RAILWAY_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {"query": query, "variables": variables or {}}
    response = requests.post(RAILWAY_API_URL, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL Errors:")
        for error in data["errors"]:
            print(f"  - {error.get('message', 'Unknown error')}")
        return None
    
    return data.get("data")

print("""
═══════════════════════════════════════════════════════════════════
🚀 RAILWAY SETUP v2 - MercariSearcher
═══════════════════════════════════════════════════════════════════
""")

# 1. Get project info
print("📋 Getting project information...")
query = """
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
  }
}
"""

result = railway_query(query, {"id": PROJECT_ID})
if not result:
    print("❌ Failed to get project info")
    sys.exit(1)

project = result["project"]
print(f"✓ Project: {project['name']}")

existing_services = [edge["node"]["name"] for edge in project.get("services", {}).get("edges", [])]
print(f"  Existing services: {existing_services if existing_services else 'None'}")

# 2. Add PostgreSQL plugin
if "postgresql" not in [s.lower() for s in existing_services]:
    print("\n🐘 Adding PostgreSQL database...")
    query = """
    mutation pluginCreate($input: PluginCreateInput!) {
      pluginCreate(input: $input) {
        id
        name
      }
    }
    """
    
    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "name": "postgresql"
        }
    }
    
    result = railway_query(query, variables)
    if result and "pluginCreate" in result:
        print(f"✓ PostgreSQL added: {result['pluginCreate']['id']}")
    else:
        print("⚠️  Failed to add PostgreSQL (might already exist)")
else:
    print("\n🐘 PostgreSQL already exists")

# 3. Deploy from GitHub
print("\n📦 Deploying from GitHub...")
query = """
mutation serviceCreate($input: ServiceCreateInput!) {
  serviceCreate(input: $input) {
    id
    name
  }
}
"""

# Create web service
if "web" not in existing_services:
    print("\n📦 Creating 'web' service...")
    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "name": "web",
            "source": {
                "repo": f"github:{GITHUB_REPO}",
                "branch": GITHUB_BRANCH
            }
        }
    }
    
    result = railway_query(query, variables)
    if result and "serviceCreate" in result:
        web_service_id = result["serviceCreate"]["id"]
        print(f"✓ Web service created: {web_service_id}")
        
        # Set environment variables for web
        print("  Setting environment variables...")
        env_vars = {
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
        
        for key, value in env_vars.items():
            var_query = """
            mutation variableUpsert($input: VariableUpsertInput!) {
              variableUpsert(input: $input) {
                id
              }
            }
            """
            var_variables = {
                "input": {
                    "projectId": PROJECT_ID,
                    "serviceId": web_service_id,
                    "name": key,
                    "value": value
                }
            }
            if railway_query(var_query, var_variables):
                display_val = value if key != "TELEGRAM_BOT_TOKEN" else "***"
                print(f"    ✓ {key}={display_val}")
else:
    print("\n📦 Service 'web' already exists")

# Create worker service  
if "worker" not in existing_services:
    print("\n📦 Creating 'worker' service...")
    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "name": "worker",
            "source": {
                "repo": f"github:{GITHUB_REPO}",
                "branch": GITHUB_BRANCH
            }
        }
    }
    
    result = railway_query(query, variables)
    if result and "serviceCreate" in result:
        worker_service_id = result["serviceCreate"]["id"]
        print(f"✓ Worker service created: {worker_service_id}")
        
        # Set environment variables for worker
        print("  Setting environment variables...")
        for key, value in env_vars.items():
            var_query = """
            mutation variableUpsert($input: VariableUpsertInput!) {
              variableUpsert(input: $input) {
                id
              }
            }
            """
            var_variables = {
                "input": {
                    "projectId": PROJECT_ID,
                    "serviceId": worker_service_id,
                    "name": key,
                    "value": value
                }
            }
            if railway_query(var_query, var_variables):
                display_val = value if key != "TELEGRAM_BOT_TOKEN" else "***"
                print(f"    ✓ {key}={display_val}")
else:
    print("\n📦 Service 'worker' already exists")

print("""
═══════════════════════════════════════════════════════════════════
✅ RAILWAY SETUP COMPLETE!
═══════════════════════════════════════════════════════════════════

📍 Project: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

🚀 Next steps:
   1. Go to Railway Dashboard
   2. Check 'web' and 'worker' services are deploying
   3. Set start commands:
      - web: gunicorn --bind 0.0.0.0:$PORT wsgi:application
      - worker: python mercari_notifications.py worker
   4. Enable public networking for 'web' service
   5. Wait for deployments to complete (2-3 minutes)
   6. Open web service domain and add your first search!

💡 Check logs in Railway Dashboard → Deployments
""")

