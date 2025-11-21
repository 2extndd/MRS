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
        from db import get_db
        db = None

        try:
            logger.info("=" * 60)
            logger.info("[WSGI] Starting background scheduler thread...")
            logger.info("=" * 60)

            # Get DB connection for logging
            db = get_db()
            db.add_log_entry('INFO', '[WSGI] Starting background scheduler thread...', 'wsgi')

            from mercari_notifications import MercariNotificationApp

            logger.info("[WSGI] Imported MercariNotificationApp")
            db.add_log_entry('INFO', '[WSGI] Imported MercariNotificationApp', 'wsgi')

            # Create app instance and run scheduler
            logger.info("[WSGI] Creating MercariNotificationApp instance...")
            db.add_log_entry('INFO', '[WSGI] Creating MercariNotificationApp instance...', 'wsgi')

            mercari_app = MercariNotificationApp()

            logger.info("[WSGI] MercariNotificationApp created successfully")
            db.add_log_entry('INFO', '[WSGI] MercariNotificationApp created successfully', 'wsgi')

            logger.info("[WSGI] Calling run_scheduler()...")
            db.add_log_entry('INFO', '[WSGI] Calling run_scheduler()...', 'wsgi')

            mercari_app.run_scheduler()

            logger.info("[WSGI] run_scheduler() returned (this should never happen)")
            db.add_log_entry('ERROR', '[WSGI] run_scheduler() returned unexpectedly!', 'wsgi')

        except Exception as e:
            logger.error(f"[WSGI] ❌ Background scheduler error: {e}")
            import traceback
            error_msg = f"[WSGI] Scheduler error: {e}\n{traceback.format_exc()}"
            logger.error(f"[WSGI] Traceback:\n{traceback.format_exc()}")

            if db:
                db.add_log_entry('ERROR', error_msg, 'wsgi')

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
