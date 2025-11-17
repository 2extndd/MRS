#!/bin/bash
# Automatic database fix for Railway

set -e

echo "================================================================================"
echo "🔥 FIXING DATABASE ISSUE"
echo "================================================================================"
echo ""

# Step 1: Remove old DATABASE_URL from both services
echo "Step 1: Removing old DATABASE_URL from services..."
echo ""

echo "  Removing from web service..."
railway service web
railway variables --unset DATABASE_URL 2>&1 | grep -v "Failed to prompt" || echo "    ✅ DATABASE_URL removed from web"

echo "  Removing from worker service..."
railway service worker
railway variables --unset DATABASE_URL 2>&1 | grep -v "Failed to prompt" || echo "    ✅ DATABASE_URL removed from worker"

echo ""
echo "✅ Step 1 complete: Old DATABASE_URL removed"
echo ""

# Step 2: Guide for adding PostgreSQL via Dashboard
echo "================================================================================"
echo "Step 2: ADD NEW POSTGRESQL DATABASE"
echo "================================================================================"
echo ""
echo "⚠️  Railway CLI cannot create databases non-interactively."
echo "   You must add PostgreSQL via Dashboard:"
echo ""
echo "   📍 Open: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d"
echo ""
echo "   Steps:"
echo "   1. Click '+ New' button (top right)"
echo "   2. Select 'Database'"
echo "   3. Click 'Add PostgreSQL'"
echo "   4. Wait 30 seconds for database to create"
echo ""
echo "   Railway will AUTOMATICALLY:"
echo "   - Generate new DATABASE_URL with correct password"
echo "   - Add DATABASE_URL to web & worker services"
echo "   - Trigger auto-redeploy (takes 2-3 minutes)"
echo ""
echo "================================================================================"
echo ""
echo "After database is added, run this to verify:"
echo ""
echo "  railway service web && railway logs | grep \"DB\""
echo ""
echo "Expected output:"
echo "  [DB] Connected to PostgreSQL ✅"
echo ""
echo "================================================================================"
