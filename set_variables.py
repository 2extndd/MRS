#!/usr/bin/env python3
"""Set variables for existing service"""

import requests

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
SERVICE_ID = "c5a6f7bc-b1d4-49be-9b40-6ce69efae43a"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
ENV_ID = "acc3b600-3ee9-4e2b-9070-a5a6f3403fd8"
API = "https://backboard.railway.app/graphql/v2"

vars_to_set = {
    "TELEGRAM_BOT_TOKEN": "8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw",
    "TELEGRAM_CHAT_ID": "-4997297083",
    "DISPLAY_CURRENCY": "USD",
    "USD_CONVERSION_RATE": "0.0067",
    "SEARCH_INTERVAL": "300",
    "MAX_ITEMS_PER_SEARCH": "50",
    "REQUEST_DELAY_MIN": "1.5",
    "REQUEST_DELAY_MAX": "3.5",
    "LOG_LEVEL": "INFO"
}

headers = {
    "Authorization": f"Bearer {RAILWAY_TOKEN}",
    "Content-Type": "application/json"
}

# Try simpler mutation
for name, value in vars_to_set.items():
    mutation = """
    mutation variableUpsert($input: VariableUpsertInput!) {
      variableUpsert(input: $input) {
        id
      }
    }
    """

    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "environmentId": ENV_ID,
            "serviceId": SERVICE_ID,
            "name": name,
            "value": value
        }
    }

    response = requests.post(API, headers=headers, json={"query": mutation, "variables": variables})

    display_val = "***" if "TOKEN" in name else value

    if response.status_code == 200:
        data = response.json()
        if "errors" not in data:
            print(f"✓ {name}={display_val}")
        else:
            print(f"✗ {name}: {data['errors'][0]['message']}")
    else:
        print(f"✗ {name}: HTTP {response.status_code}")

print("\n✅ Finished setting variables")
print(f"Check: https://railway.app/project/{PROJECT_ID}/service/{SERVICE_ID}")
