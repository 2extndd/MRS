#!/bin/bash
#
# Create PostgreSQL database on Railway via GraphQL API
#

set -e

PROJECT_ID="f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
ENVIRONMENT_ID="acc3b600-3ee9-4e2b-9070-a5a6f3403fd8"  # production

echo "================================================================================"
echo "🚀 CREATING POSTGRESQL ON RAILWAY"
echo "================================================================================"

# Get Railway token
if [ -z "$RAILWAY_TOKEN" ]; then
    echo ""
    echo "❌ ERROR: RAILWAY_TOKEN environment variable not set!"
    echo ""
    echo "To get your token:"
    echo "1. Go to https://railway.app/account/tokens"
    echo "2. Create new token"
    echo "3. Export it: export RAILWAY_TOKEN='your-token-here'"
    echo ""
    exit 1
fi

echo ""
echo "✅ Railway token found"
echo "   Project ID: $PROJECT_ID"
echo "   Environment: production"
echo ""

# GraphQL mutation to create PostgreSQL plugin
echo "🔧 Creating PostgreSQL database..."
echo ""

GRAPHQL_QUERY=$(cat <<'EOF'
{
  "query": "mutation ServiceCreate($input: ServiceCreateInput!) { serviceCreate(input: $input) { id name } }",
  "variables": {
    "input": {
      "projectId": "f17da572-14c9-47b5-a9f1-1b6d5b6dea2d",
      "name": "postgres",
      "source": {
        "image": "postgres:16-alpine"
      }
    }
  }
}
EOF
)

# Make API request
RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$GRAPHQL_QUERY" \
  https://backboard.railway.app/graphql/v2)

echo "API Response:"
echo "$RESPONSE" | python3 -m json.tool

# Check for errors
if echo "$RESPONSE" | grep -q "errors"; then
    echo ""
    echo "❌ Failed to create PostgreSQL database"
    echo "   Response: $RESPONSE"
    echo ""
    echo "⚠️  Please create database manually via Dashboard:"
    echo "   https://railway.app/project/$PROJECT_ID"
    echo ""
    echo "   Steps:"
    echo "   1. Click '+ New' → 'Database' → 'Add PostgreSQL'"
    echo "   2. Railway will auto-create DATABASE_URL"
    echo "   3. Services will auto-redeploy"
    echo ""
    exit 1
fi

echo ""
echo "================================================================================"
echo "✅ POSTGRESQL DATABASE CREATED!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "1. Wait ~1 minute for database to initialize"
echo "2. Railway will automatically:"
echo "   - Generate DATABASE_URL variable"
echo "   - Add it to web & worker services"
echo "   - Trigger auto-redeploy"
echo "3. Check logs for: [DB] Connected to PostgreSQL ✅"
echo ""
echo "================================================================================"
