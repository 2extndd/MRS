# PostgreSQL Setup for Railway

## CRITICAL: Queries are deleted after redeploy!

This happens because the bot uses SQLite (local database in container). When Railway redeploys, the container is recreated and ALL DATA IS LOST.

## Solution: Use Railway PostgreSQL

### Step 1: Add PostgreSQL Plugin
1. Go to Railway project: https://railway.app/project/f17da572-14c9-47b5-a9f1-1b6d5b6dea2d
2. Click "+ New" → "Database" → "Add PostgreSQL"
3. Wait for PostgreSQL to deploy

### Step 2: Link to Services
The DATABASE_URL will be automatically available to all services in the project.

### Step 3: Verify
1. Check that `DATABASE_URL` variable exists in both web and worker services
2. The bot will automatically use PostgreSQL when DATABASE_URL is set
3. Queries and items will persist after redeploy

## Current Status
- ❌ Using SQLite (data lost on redeploy)
- ✅ Need to add PostgreSQL plugin

После добавления PostgreSQL все queries и настройки будут сохраняться!
