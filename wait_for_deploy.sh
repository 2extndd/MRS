#!/bin/bash
# Wait for Railway deployment to complete

for i in $(seq 1 10); do
    echo "[$i/10] Checking app status..."
    RESPONSE=$(curl -s "https://mrs-production-64ce.up.railway.app/")

    if echo "$RESPONSE" | grep -q "Application not found"; then
        echo "   Still 404, waiting 30s..."
        sleep 30
    else
        echo "✅ APP IS UP!"
        echo "Testing heartbeat endpoint:"
        curl -s "https://mrs-production-64ce.up.railway.app/api/scheduler/heartbeat" | python3 -m json.tool
        exit 0
    fi
done

echo "❌ Deployment did not complete after 5 minutes"
exit 1
