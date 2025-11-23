#!/bin/bash
# Railway start script - determines which process to start based on SERVICE_NAME or RAILWAY_SERVICE_NAME

SERVICE="${RAILWAY_SERVICE_NAME:-${SERVICE_NAME:-web}}"
# Convert to lowercase for comparison
SERVICE_LOWER=$(echo "$SERVICE" | tr '[:upper:]' '[:lower:]')

echo "Starting Railway service: $SERVICE (checking as: $SERVICE_LOWER)"

if [ "$SERVICE_LOWER" = "worker" ]; then
    echo "Starting worker process..."
    exec python3 mercari_notifications.py worker
else
    echo "Starting web process..."
    exec gunicorn --config gunicorn_config.py wsgi:application
fi
