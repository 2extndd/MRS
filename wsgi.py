"""
WSGI entry point for MercariSearcher web UI
Used by Gunicorn on Railway

This module loads Flask web application.
Search cycles are now handled by Railway Cron jobs (see run_search_cycle.py)
"""

import os
import sys
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

try:
    # Import Flask app from web UI
    from web_ui_plugin.app import app as application

    logger.info("=" * 60)
    logger.info("WSGI application loaded successfully")
    logger.info("=" * 60)
    logger.info(f"Application: {application}")
    logger.info("✅ Web UI is running")
    logger.info("ℹ️  Search cycles are handled by Railway Cron jobs")
    logger.info("=" * 60)

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
