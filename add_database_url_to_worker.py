#!/usr/bin/env python3
"""
Add DATABASE_URL reference variable to worker service via Railway GraphQL API
"""

import subprocess
import json

# Get Railway auth token from CLI
def get_railway_token():
    try:
        result = subprocess.run(
            ["railway", "whoami", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # Extract token from CLI config
            config_result = subprocess.run(
                ["cat", f"{subprocess.os.path.expanduser('~')}/.railway/config.json"],
                capture_output=True,
                text=True
            )
            if config_result.returncode == 0:
                config = json.loads(config_result.stdout)
                return config.get("token") or config.get("auth_token")
    except Exception as e:
        print(f"Failed to get token from CLI: {e}")

    return None

# Get service IDs
def get_service_ids():
    result = subprocess.run(
        ["railway", "service", "list", "--json"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        print("Failed to list services")
        return None, None, None

    services = json.loads(result.stdout)

    worker_id = None
    postgres_id = None

    for service in services:
        if service.get("name") == "worker":
            worker_id = service.get("id")
        elif "Postgres-T-E-" in service.get("name", ""):
            postgres_id = service.get("id")

    return worker_id, postgres_id

print("=" * 80)
print("Adding DATABASE_URL to worker service")
print("=" * 80)
print()

# Since Railway CLI doesn't support reference variables directly,
# we need to get the actual DATABASE_URL value and set it
print("Getting DATABASE_URL from Postgres service...")
result = subprocess.run(
    ["railway", "service", "Postgres-T-E-"],
    capture_output=True,
    text=True
)

result = subprocess.run(
    ["railway", "variables"],
    capture_output=True,
    text=True,
    timeout=15
)

# Extract DATABASE_URL from output
database_url = None
lines = result.stdout.split('\n')
for i, line in enumerate(lines):
    if 'DATABASE_URL' in line and 'postgresql://' in line:
        # DATABASE_URL is likely split across multiple lines
        url_parts = []
        for j in range(i, min(i + 5, len(lines))):
            if '│' in lines[j]:
                parts = lines[j].split('│')
                if len(parts) >= 3:
                    url_parts.append(parts[2].strip())
        database_url = ''.join(url_parts)
        break

if not database_url or not database_url.startswith('postgresql://'):
    print("❌ Failed to extract DATABASE_URL")
    print("Please add it manually via Railway Dashboard:")
    print("1. Go to worker service")
    print("2. Variables tab")
    print("3. Add Variable Reference")
    print("4. Select: Postgres-T-E-.DATABASE_URL")
    exit(1)

print(f"✅ Found DATABASE_URL: {database_url[:50]}...")
print()

# Switch to worker service and set the variable
print("Setting DATABASE_URL on worker service...")
result = subprocess.run(
    ["railway", "service", "worker"],
    capture_output=True,
    text=True
)

# Set the variable
result = subprocess.run(
    ["railway", "variables", "--set", f"DATABASE_URL={database_url}"],
    capture_output=True,
    text=True,
    timeout=15
)

if result.returncode == 0:
    print("✅ DATABASE_URL added to worker service!")
    print()
    print("Next: Redeploying worker service...")

    # Trigger redeploy
    subprocess.run(
        ["railway", "up", "--detach"],
        timeout=60
    )

    print("✅ Worker service redeploying!")
    print()
    print("=" * 80)
    print("DATABASE_URL successfully configured for worker")
    print("=" * 80)
else:
    print(f"❌ Failed to set DATABASE_URL: {result.stderr}")
    print()
    print("Please add it manually via Railway Dashboard")
