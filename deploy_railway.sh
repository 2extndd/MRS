#!/bin/bash
set -e

export RAILWAY_TOKEN='4f9d1671-b934-4a05-a97f-1067c18d4eb7'
PROJECT_ID='f17da572-14c9-47b5-a9f1-1b6d5b6dea2d'

echo "🚀 Railway Deployment Script - MercariSearcher"
echo "═══════════════════════════════════════════════"
echo ""

# Link project
echo "📌 Linking to Railway project..."
railway link -p $PROJECT_ID 2>&1 || echo "Already linked"

# Add PostgreSQL
echo ""
echo "🐘 Adding PostgreSQL..."
railway add -d postgres 2>&1 || echo "PostgreSQL already exists"

# Deploy from GitHub
echo ""
echo "📦 Deploying from GitHub..."
railway up --detach 2>&1 || echo "Deployment initiated"

# Set environment variables
echo ""
echo "🔧 Setting environment variables..."

railway variables set \
  TELEGRAM_BOT_TOKEN='8312495672:AAG7dnspW-QFbWKJQXy6Mh04oG4uDp-3aSw' \
  TELEGRAM_CHAT_ID='-4997297083' \
  DISPLAY_CURRENCY='USD' \
  USD_CONVERSION_RATE='0.0067' \
  SEARCH_INTERVAL='300' \
  MAX_ITEMS_PER_SEARCH='50' \
  REQUEST_DELAY_MIN='1.5' \
  REQUEST_DELAY_MAX='3.5' \
  LOG_LEVEL='INFO' 2>&1

echo ""
echo "✅ Railway configuration complete!"
echo ""
echo "📍 Dashboard: https://railway.app/project/$PROJECT_ID"
echo ""
echo "Next steps:"
echo "  1. Check Railway Dashboard for deployment status"
echo "  2. Enable public networking for web service"
echo "  3. Wait for deployments (2-3 minutes)"
echo "  4. Open web service URL and add your first search!"
