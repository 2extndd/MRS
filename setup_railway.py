#!/usr/bin/env python3
"""
Railway Project Setup Script
Automatically configures Railway project for MercariSearcher
"""

import requests
import json
import sys
import os

# Railway GraphQL API
RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

# Project configuration
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
GITHUB_REPO = "2extndd/MRS"
GITHUB_BRANCH = "main"

def get_railway_token():
    """Get Railway API token from environment or user input"""
    token = os.getenv("RAILWAY_TOKEN")
    if not token:
        print("❌ RAILWAY_TOKEN not found in environment variables")
        print("\nTo get your Railway token:")
        print("1. Go to https://railway.app/account/tokens")
        print("2. Click 'Create Token'")
        print("3. Copy the token")
        print("\nThen set it:")
        print("  export RAILWAY_TOKEN='your_token_here'")
        print("  or")
        print("  python setup_railway.py --token 'your_token_here'")
        sys.exit(1)
    return token

def railway_query(token, query, variables=None):
    """Execute GraphQL query on Railway API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "variables": variables or {}
    }

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

def get_project_info(token):
    """Get project information"""
    query = """
    query($projectId: String!) {
      project(id: $projectId) {
        id
        name
        description
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

    variables = {"projectId": PROJECT_ID}
    return railway_query(token, query, variables)

def create_service(token, service_name, start_command, enable_public_networking=False):
    """Create a new service"""
    query = """
    mutation($input: ServiceCreateInput!) {
      serviceCreate(input: $input) {
        id
        name
      }
    }
    """

    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "name": service_name,
            "source": {
                "repo": GITHUB_REPO,
                "branch": GITHUB_BRANCH
            }
        }
    }

    print(f"\n📦 Creating service: {service_name}...")
    result = railway_query(token, query, variables)

    if result and "serviceCreate" in result:
        service_id = result["serviceCreate"]["id"]
        print(f"✓ Service created: {service_id}")

        # Set start command
        set_start_command(token, service_id, start_command)

        # Enable public networking if needed
        if enable_public_networking:
            enable_public_domain(token, service_id)

        return service_id

    return None

def set_start_command(token, service_id, start_command):
    """Set start command for service"""
    query = """
    mutation($serviceId: String!, $startCommand: String!) {
      serviceUpdate(id: $serviceId, input: { startCommand: $startCommand }) {
        id
      }
    }
    """

    variables = {
        "serviceId": service_id,
        "startCommand": start_command
    }

    print(f"  Setting start command: {start_command}")
    result = railway_query(token, query, variables)

    if result:
        print(f"  ✓ Start command set")

def enable_public_domain(token, service_id):
    """Enable public networking for service"""
    query = """
    mutation($serviceId: String!) {
      serviceDomainCreate(serviceId: $serviceId) {
        id
        domain
      }
    }
    """

    variables = {"serviceId": service_id}

    print(f"  Enabling public networking...")
    result = railway_query(token, query, variables)

    if result and "serviceDomainCreate" in result:
        domain = result["serviceDomainCreate"].get("domain")
        print(f"  ✓ Public domain: {domain}")

def add_postgres(token):
    """Add PostgreSQL database to project"""
    query = """
    mutation($projectId: String!) {
      pluginCreate(input: { projectId: $projectId, name: "postgresql" }) {
        id
        name
      }
    }
    """

    variables = {"projectId": PROJECT_ID}

    print(f"\n🐘 Adding PostgreSQL database...")
    result = railway_query(token, query, variables)

    if result and "pluginCreate" in result:
        print(f"✓ PostgreSQL added: {result['pluginCreate']['id']}")
        return True

    return False

def set_environment_variable(token, service_id, key, value):
    """Set environment variable for service"""
    query = """
    mutation($input: VariableUpsertInput!) {
      variableUpsert(input: $input) {
        id
      }
    }
    """

    variables = {
        "input": {
            "serviceId": service_id,
            "name": key,
            "value": value
        }
    }

    result = railway_query(token, query, variables)
    return result is not None

def setup_environment_variables(token, service_id, env_vars):
    """Setup multiple environment variables"""
    print(f"\n⚙️  Setting environment variables...")

    for key, value in env_vars.items():
        if value:
            if set_environment_variable(token, service_id, key, value):
                # Mask sensitive values
                display_value = value if key not in ["TELEGRAM_BOT_TOKEN", "RAILWAY_TOKEN"] else "***"
                print(f"  ✓ {key}={display_value}")
            else:
                print(f"  ✗ Failed to set {key}")

def main():
    """Main setup function"""
    print("""
═══════════════════════════════════════════════════════════════════
🚀 RAILWAY AUTOMATIC SETUP - MercariSearcher
═══════════════════════════════════════════════════════════════════
    """)

    # Check for token in arguments
    if len(sys.argv) > 2 and sys.argv[1] == "--token":
        os.environ["RAILWAY_TOKEN"] = sys.argv[2]

    # Get Railway token
    token = get_railway_token()
    print(f"✓ Railway token found\n")

    # Get project info
    print(f"📋 Getting project information...")
    project_info = get_project_info(token)

    if not project_info:
        print("❌ Failed to get project info. Check your token and project ID.")
        sys.exit(1)

    project = project_info.get("project")
    print(f"✓ Project: {project.get('name', PROJECT_ID)}")

    # Check existing services
    existing_services = [edge["node"]["name"] for edge in project.get("services", {}).get("edges", [])]
    print(f"  Existing services: {existing_services if existing_services else 'None'}")

    # Add PostgreSQL
    if "postgresql" not in [s.lower() for s in existing_services]:
        add_postgres(token)
    else:
        print(f"\n🐘 PostgreSQL already exists")

    # Get environment variables from user
    print(f"\n" + "="*67)
    print("📝 ENVIRONMENT VARIABLES SETUP")
    print("="*67)

    telegram_bot_token = input("\n🤖 Enter TELEGRAM_BOT_TOKEN (from @BotFather): ").strip()
    telegram_chat_id = input("💬 Enter TELEGRAM_CHAT_ID (from @userinfobot): ").strip()

    if not telegram_bot_token or not telegram_chat_id:
        print("\n❌ TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required!")
        sys.exit(1)

    env_vars = {
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_CHAT_ID": telegram_chat_id,
        "DISPLAY_CURRENCY": "USD",
        "USD_CONVERSION_RATE": "0.0067",
        "SEARCH_INTERVAL": "300",
        "MAX_ITEMS_PER_SEARCH": "50",
        "REQUEST_DELAY_MIN": "1.5",
        "REQUEST_DELAY_MAX": "3.5",
        "LOG_LEVEL": "INFO"
    }

    # Create WEB service
    web_service_id = None
    if "web" not in existing_services:
        web_service_id = create_service(
            token,
            "web",
            "gunicorn --bind 0.0.0.0:$PORT --timeout 30 --log-level info wsgi:application",
            enable_public_networking=True
        )
    else:
        print(f"\n📦 Service 'web' already exists")

    # Create WORKER service
    worker_service_id = None
    if "worker" not in existing_services:
        worker_service_id = create_service(
            token,
            "worker",
            "python mercari_notifications.py worker",
            enable_public_networking=False
        )
    else:
        print(f"\n📦 Service 'worker' already exists")

    # Set environment variables for both services
    if web_service_id:
        setup_environment_variables(token, web_service_id, env_vars)

    if worker_service_id:
        setup_environment_variables(token, worker_service_id, env_vars)

    # Final summary
    print(f"\n" + "="*67)
    print("✅ RAILWAY SETUP COMPLETE!")
    print("="*67)
    print(f"\n📍 Project: https://railway.app/project/{PROJECT_ID}")
    print(f"\n📦 Services created:")
    if web_service_id:
        print(f"   ✓ web (Flask UI with public domain)")
    if worker_service_id:
        print(f"   ✓ worker (Background scanner)")
    print(f"\n🐘 PostgreSQL: Added")
    print(f"\n⚙️  Environment variables: Set")
    print(f"\n🚀 Next steps:")
    print(f"   1. Check deployments in Railway Dashboard")
    print(f"   2. Wait for services to start (2-3 minutes)")
    print(f"   3. Open web service public domain")
    print(f"   4. Add first search via /queries")
    print(f"\n💡 Monitor logs in Railway Dashboard → Deployments → Logs")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
