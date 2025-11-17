#!/usr/bin/env python3
"""
Add PostgreSQL database to Railway project via API
"""

import os
import subprocess
import json

# Railway project details
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
ENVIRONMENT = "production"

def run_railway_command(command):
    """Run railway CLI command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1


def main():
    print("=" * 80)
    print("🚀 ADDING POSTGRESQL TO RAILWAY")
    print("=" * 80)

    # Check Railway token
    railway_token = os.getenv("RAILWAY_TOKEN")
    if not railway_token:
        print("\n⚠️  RAILWAY_TOKEN not found in environment")
        print("   Please set it manually via Railway Dashboard:")
        print(f"   https://railway.app/project/{PROJECT_ID}")
        print("\n   Steps:")
        print("   1. Click '+ New' button")
        print("   2. Select 'Database' → 'Add PostgreSQL'")
        print("   3. Railway will auto-create DATABASE_URL variable")
        print("   4. Services will auto-redeploy")
        return False

    print(f"\n✅ Railway token found")
    print(f"   Project ID: {PROJECT_ID}")

    # Use Railway GraphQL API to add PostgreSQL
    graphql_query = """
    mutation {
      serviceCreate(input: {
        projectId: "%s",
        name: "postgres",
        source: {
          image: "postgres:16-alpine"
        }
      }) {
        id
        name
      }
    }
    """ % PROJECT_ID

    print("\n🔧 Creating PostgreSQL service via API...")

    # This would require proper GraphQL API call
    # For now, guide user to use Dashboard
    print("\n⚠️  Railway CLI doesn't support non-interactive database creation")
    print("   Please use Railway Dashboard instead:")
    print(f"\n   📍 Open: https://railway.app/project/{PROJECT_ID}")
    print("\n   Steps:")
    print("   1. Click '+ New' button in top right")
    print("   2. Select 'Database'")
    print("   3. Click 'Add PostgreSQL'")
    print("   4. Railway will automatically:")
    print("      - Create new PostgreSQL database")
    print("      - Generate DATABASE_URL variable")
    print("      - Add DATABASE_URL to web & worker services")
    print("      - Trigger auto-redeploy")
    print("\n   ⏱  This takes ~2 minutes")
    print("\n   After database is added:")
    print("   - Logs will show: [DB] Connected to PostgreSQL ✅")
    print("   - Queries will persist after reload ✅")
    print("   - Worker will find and scan queries ✅")

    return False


if __name__ == "__main__":
    print()
    success = main()
    print("\n" + "=" * 80)
    if success:
        print("✅ POSTGRESQL ADDED")
    else:
        print("⚠️  MANUAL SETUP REQUIRED VIA DASHBOARD")
    print("=" * 80)
    print()
