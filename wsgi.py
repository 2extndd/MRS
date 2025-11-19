"""
WSGI entry point for MercariSearcher web UI
Used by Gunicorn on Railway

This module:
1. Loads Flask web application
2. Starts background scheduler thread for automatic search cycles
"""

import os
import sys
import logging
import threading

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

    logger.info("WSGI application loaded successfully")
    logger.info(f"Application: {application}")

    # Start background scheduler in separate thread
    def start_scheduler():
        """Start the search scheduler in background thread"""
        try:
            logger.info("=" * 60)
            logger.info("Starting background scheduler thread...")
            logger.info("=" * 60)

            from mercari_notifications import MercariApp

            # Create app instance and run scheduler
            mercari_app = MercariApp()
            mercari_app.run_scheduler()

        except Exception as e:
            logger.error(f"Background scheduler error: {e}")

    # Start scheduler in daemon thread (dies when main process exits)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
    scheduler_thread.start()

    logger.info("✅ Background scheduler thread started")
    logger.info("✅ Web UI + Auto-scan scheduler are both running")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
