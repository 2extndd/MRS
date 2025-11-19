#!/usr/bin/env python3
"""
Execute database migration via Railway API
Gets DATABASE_URL and runs SQL migration
"""
import requests
import json
import psycopg2

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
RAILWAY_API = "https://backboard.railway.app/graphql/v2"

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
        print(f"❌ HTTP {response.status_code}")
        return None

    data = response.json()
    if "errors" in data:
        print(f"❌ GraphQL Errors: {data['errors']}")
        return None

    return data.get("data")

print("=" * 70)
print("🔧 DATABASE MIGRATION - Add image_data column")
print("=" * 70)

# Step 1: Get project services and environment
print("\n1️⃣  Getting project info...")
result = gql_request("""
query project($id: String!) {
  project(id: $id) {
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
""", {"id": PROJECT_ID})

if not result or "project" not in result:
    print("❌ Failed to get project")
    exit(1)

project = result["project"]
print(f"   ✓ Project: {project['name']}")

services = {s["node"]["name"]: s["node"]["id"] for s in project.get("services", {}).get("edges", [])}
print(f"   ✓ Services: {list(services.keys())}")

envs = project.get("environments", {}).get("edges", [])
if not envs:
    print("❌ No environments found")
    exit(1)

env_id = envs[0]["node"]["id"]
env_name = envs[0]["node"]["name"]
print(f"   ✓ Environment: {env_name}")

# Step 2: Get DATABASE_URL from web service variables
print("\n2️⃣  Getting DATABASE_URL...")
web_service_id = services.get('web')
if not web_service_id:
    print("❌ Web service not found")
    exit(1)

result = gql_request("""
query variables($projectId: String!, $environmentId: String!, $serviceId: String) {
  variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) {
    edges {
      node {
        name
        value
      }
    }
  }
}
""", {
    "projectId": PROJECT_ID,
    "environmentId": env_id,
    "serviceId": web_service_id
})

if not result or "variables" not in result:
    print("❌ Failed to get variables")
    exit(1)

variables = {v["node"]["name"]: v["node"]["value"] for v in result["variables"]["edges"]}
database_url = variables.get("DATABASE_URL")

if not database_url:
    print("❌ DATABASE_URL not found in variables")
    exit(1)

print(f"   ✓ DATABASE_URL found: postgresql://...{database_url[-30:]}")

# Step 3: Connect to PostgreSQL and run migration
print("\n3️⃣  Connecting to PostgreSQL...")
try:
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    print("   ✓ Connected!")

    print("\n4️⃣  Adding image_data column...")
    cursor.execute("""
        ALTER TABLE items
        ADD COLUMN IF NOT EXISTS image_data TEXT
    """)
    print("   ✓ Column added (or already exists)")

    print("\n5️⃣  Creating index...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_image_data
        ON items(id)
        WHERE image_data IS NOT NULL
    """)
    print("   ✓ Index created (or already exists)")

    conn.commit()
    print("\n6️⃣  Changes committed!")

    # Verify
    print("\n7️⃣  Verifying migration...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'items' AND column_name = 'image_data'
    """)
    result = cursor.fetchone()

    if result:
        print(f"   ✓ Column verified: {result[0]} ({result[1]})")
    else:
        print("   ❌ Could not verify column")

    # Check existing items
    cursor.execute("SELECT COUNT(*) FROM items")
    total_items = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE image_data IS NOT NULL")
    items_with_images = cursor.fetchone()[0]

    print(f"\n📊 Database status:")
    print(f"   Total items: {total_items}")
    print(f"   Items with images: {items_with_images}")
    print(f"   Items without images: {total_items - items_with_images}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 70)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Deploy worker service: railway up --service worker")
    print("  2. Worker will start downloading images for new items")
    print("  3. Check web UI to verify images loading")

except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
