#!/usr/bin/env python3
import requests
import json

RAILWAY_TOKEN = "4f9d1671-b934-4a05-a97f-1067c18d4eb7"
PROJECT_ID = "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {RAILWAY_TOKEN}",
    "Content-Type": "application/json",
}

# Проверим базовую информацию о проекте
query = """
query {
  me {
    id
    email
  }
}
"""

print("Проверяю токен...")
response = requests.post(RAILWAY_API_URL, headers=headers, json={"query": query})
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

# Попробуем получить проекты
query2 = """
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
"""

print("\n\nПолучаю список проектов...")
response2 = requests.post(RAILWAY_API_URL, headers=headers, json={"query": query2})
print(f"Status: {response2.status_code}")
print(f"Response: {json.dumps(response2.json(), indent=2)}")
