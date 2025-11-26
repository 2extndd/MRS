"""
WSGI entry point for MercariSearcher web UI
Used by Gunicorn on Railway

This module loads Flask web application and starts automatic search scheduler.
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

    logger.info("=" * 60)
    logger.info("WSGI application loaded successfully")
    logger.info("=" * 60)
    logger.info(f"Application: {application}")
    logger.info("✅ Web UI is running")
    logger.info("=" * 60)

    # Auto-start scheduler in background thread (only in production)
    if os.getenv('RAILWAY_ENVIRONMENT'):
        logger.info("[AUTOSTART] Railway environment detected - starting scheduler...")

        def start_scheduler():
            try:
                import time
                time.sleep(5)  # Wait for app to fully initialize

                from mercari_notifications import MercariNotificationApp
                app_instance = MercariNotificationApp()

                logger.info("[AUTOSTART] Starting search scheduler...")
                app_instance.run_scheduler()  # This runs infinite loop

            except Exception as e:
                logger.error(f"[AUTOSTART] Failed to start scheduler: {e}")
                import traceback
                logger.error(traceback.format_exc())

        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerAutostart")
        scheduler_thread.start()
        logger.info("[AUTOSTART] ✅ Scheduler thread started in background")
    else:
        logger.info("[AUTOSTART] Local environment - scheduler not auto-started")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
