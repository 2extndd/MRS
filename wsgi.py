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
    logger.info("[WSGI] Application loaded successfully")
    logger.info("=" * 60)
    logger.info(f"[WSGI] Application: {application}")
    logger.info("[WSGI] ✅ Web UI is running")
    logger.info("=" * 60)

    # Auto-start scheduler in background thread (only in production)
    if os.getenv('RAILWAY_ENVIRONMENT'):
        logger.info("[AUTOSTART] Railway environment detected - starting scheduler...")

        def start_scheduler_with_restart():
            """Start scheduler with automatic restart on failure"""
            import time
            restart_count = 0
            max_restart_delay = 60  # Max 60 seconds between restarts

            while True:  # Infinite restart loop
                restart_count += 1
                try:
                    logger.info("=" * 60)
                    logger.info(f"[AUTOSTART] Starting scheduler (attempt #{restart_count})...")
                    logger.info("=" * 60)

                    if restart_count == 1:
                        time.sleep(5)  # Initial delay only on first start

                    from mercari_notifications import MercariNotificationApp
                    app_instance = MercariNotificationApp()

                    logger.info("[AUTOSTART] ✅ Scheduler starting infinite loop...")
                    app_instance.run_scheduler()  # This runs infinite loop

                    # If run_scheduler() returns (shouldn't happen), restart it
                    logger.warning("[AUTOSTART] ⚠️ Scheduler loop ended unexpectedly - restarting...")

                except Exception as e:
                    logger.error(f"[AUTOSTART] ❌ Scheduler crashed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                # Calculate restart delay (exponential backoff, max 60 seconds)
                restart_delay = min(restart_count * 5, max_restart_delay)
                logger.info(f"[AUTOSTART] Restarting scheduler in {restart_delay} seconds...")
                time.sleep(restart_delay)

        scheduler_thread = threading.Thread(target=start_scheduler_with_restart, daemon=True, name="SchedulerAutostart")
        scheduler_thread.start()
        logger.info("[AUTOSTART] ✅ Scheduler thread started in background with auto-restart")
    else:
        logger.info("[AUTOSTART] Local environment - scheduler not auto-started")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
