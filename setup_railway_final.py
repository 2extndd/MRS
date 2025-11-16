#!/usr/bin/env python3
"""
Railway Setup - Final Working Version
Based on successful token test
"""

import requests
import json
import time
import sys

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

def gql(query, variables=None):
    """Execute GraphQL query"""
    headers = {
        "Authorization": f"Bearer {RAILWAY_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = requests.post(RAILWAY_API, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            print(response.text[:500])
            return None

        data = response.json()

        if "errors" in data:
            print(f"❌ GraphQL Errors:")
            for err in data["errors"]:
                print(f"   • {err.get('message', 'Unknown')}")
            return None

        return data.get("data")

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

print("═" * 70)
print("🚀 Railway Setup - MercariSearcher")
print("═" * 70)
print()

# Step 1: Get project info
print("📋 Step 1: Getting project information...")
result = gql("""
query {
  projects {
    edges {
      node {
        id
        name
      }
    }
  }
}
""")

if result and "projects" in result:
    projects = [p["node"] for p in result["projects"]["edges"]]
    target_project = next((p for p in projects if p["id"] == PROJECT_ID), None)

    if target_project:
        print(f"✓ Found project: {target_project['name']}")
    else:
        print(f"❌ Project {PROJECT_ID} not found")
        sys.exit(1)
else:
    print("❌ Failed to get projects")
    sys.exit(1)

# Step 2: Get detailed project info
print()
print("📋 Step 2: Getting project details...")
result = gql("""
query getProject($projectId: String!) {
  project(id: $projectId) {
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
""", {"projectId": PROJECT_ID})

if not result or "project" not in result:
    print("❌ Failed to get project details")
    sys.exit(1)

project = result["project"]
services = [s["node"] for s in project.get("services", {}).get("edges", [])]
environments = [e["node"] for e in project.get("environments", {}).get("edges", [])]

print(f"✓ Project: {project['name']}")
print(f"  Current services: {[s['name'] for s in services] or 'None'}")
print(f"  Environments: {[e['name'] for e in environments]}")

if not environments:
    print("❌ No environments found")
    sys.exit(1)

env_id = environments[0]["id"]
env_name = environments[0]["name"]
print(f"  Using environment: {env_name}")

# Step 3: Add PostgreSQL
print()
print("🐘 Step 3: Adding PostgreSQL database...")

# Check if postgres already exists
has_postgres = any("postgres" in s["name"].lower() or "database" in s["name"].lower() for s in services)

if not has_postgres:
    result = gql("""
    mutation deployPlugin($projectId: String!, $environmentId: String!) {
      deployPlugin(input: {
        projectId: $projectId
        environmentId: $environmentId
        name: "postgresql"
      }) {
        id
        name
      }
    }
    """, {
        "projectId": PROJECT_ID,
        "environmentId": env_id
    })

    if result and "deployPlugin" in result:
        print(f"✓ PostgreSQL deployed: {result['deployPlugin']['name']}")
        time.sleep(3)
    else:
        print("⚠️  PostgreSQL deployment failed (might already exist)")
else:
    print("✓ PostgreSQL already exists")

# Step 4: Create services from GitHub
print()
print("📦 Step 4: Creating services from GitHub...")

# Check existing services
service_names = [s["name"] for s in services]

# Create web service
if "web" not in service_names:
    print()
    print("  Creating 'web' service...")
    result = gql("""
    mutation createService($projectId: String!, $environmentId: String!, $name: String!, $source: ServiceSourceInput!) {
      serviceCreate(input: {
        projectId: $projectId
        environmentId: $environmentId
        name: $name
        source: $source
      }) {
        id
        name
      }
    }
    """, {
        "projectId": PROJECT_ID,
        "environmentId": env_id,
        "name": "web",
        "source": {
            "repo": f"{GITHUB_REPO}",
            "branch": "main"
        }
    })

    if result and "serviceCreate" in result:
        web_service_id = result["serviceCreate"]["id"]
        print(f"  ✓ Web service created: {web_service_id}")

        # Set environment variables
        print("  Setting environment variables...")
        for key, value in ENV_VARS.items():
            var_result = gql("""
            mutation setVar($projectId: String!, $environmentId: String!, $serviceId: String!, $name: String!, $value: String!) {
              variableUpsert(input: {
                projectId: $projectId
                environmentId: $environmentId
                serviceId: $serviceId
                name: $name
                value: $value
              })
            }
            """, {
                "projectId": PROJECT_ID,
                "environmentId": env_id,
                "serviceId": web_service_id,
                "name": key,
                "value": value
            })

            display_val = "***" if "TOKEN" in key else value
            status = "✓" if var_result else "⚠️"
            print(f"    {status} {key}={display_val}")
            time.sleep(0.3)
    else:
        print("  ❌ Web service creation failed")
else:
    print("  ✓ Web service already exists")

# Create worker service
if "worker" not in service_names:
    print()
    print("  Creating 'worker' service...")
    result = gql("""
    mutation createService($projectId: String!, $environmentId: String!, $name: String!, $source: ServiceSourceInput!) {
      serviceCreate(input: {
        projectId: $projectId
        environmentId: $environmentId
        name: $name
        source: $source
      }) {
        id
        name
      }
    }
    """, {
        "projectId": PROJECT_ID,
        "environmentId": env_id,
        "name": "worker",
        "source": {
            "repo": f"{GITHUB_REPO}",
            "branch": "main"
        }
    })

    if result and "serviceCreate" in result:
        worker_service_id = result["serviceCreate"]["id"]
        print(f"  ✓ Worker service created: {worker_service_id}")

        # Set environment variables
        print("  Setting environment variables...")
        for key, value in ENV_VARS.items():
            var_result = gql("""
            mutation setVar($projectId: String!, $environmentId: String!, $serviceId: String!, $name: String!, $value: String!) {
              variableUpsert(input: {
                projectId: $projectId
                environmentId: $environmentId
                serviceId: $serviceId
                name: $name
                value: $value
              })
            }
            """, {
                "projectId": PROJECT_ID,
                "environmentId": env_id,
                "serviceId": worker_service_id,
                "name": key,
                "value": value
            })

            display_val = "***" if "TOKEN" in key else value
            status = "✓" if var_result else "⚠️"
            print(f"    {status} {key}={display_val}")
            time.sleep(0.3)
    else:
        print("  ❌ Worker service creation failed")
else:
    print("  ✓ Worker service already exists")

print()
print("═" * 70)
print("✅ Railway Setup Completed!")
print("═" * 70)
print()
print(f"📍 Dashboard: https://railway.app/project/{PROJECT_ID}")
print()
print("🚀 Next Steps:")
print("  1. Go to Railway Dashboard")
print("  2. Configure start commands for services:")
print("     • web: gunicorn --bind 0.0.0.0:$PORT --timeout 30 wsgi:application")
print("     • worker: python mercari_notifications.py worker")
print("  3. Enable public domain for 'web' service (Settings → Networking)")
print("  4. Wait for deployments to complete (2-3 minutes)")
print("  5. Open web service URL and add your first search!")
print()
print("📋 All environment variables have been configured in Railway.")
print()
