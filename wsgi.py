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

    # Start background scheduler in separate thread with auto-restart
    def start_scheduler():
        """Start the search scheduler in background thread with auto-restart on failure"""
        import time
        from db import get_db

        restart_count = 0
        max_restart_delay = 60  # Maximum 60 seconds between restarts

        while True:  # Infinite loop - restart scheduler forever
            db = None
            restart_count += 1

            try:
                logger.info("=" * 60)
                logger.info(f"[WSGI] Starting background scheduler (attempt #{restart_count})...")
                logger.info("=" * 60)

                # Get DB connection for logging
                db = get_db()
                db.add_log_entry('INFO', f'[WSGI] Starting scheduler (attempt #{restart_count})...', 'wsgi')

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

                # If we get here, scheduler exited normally (shouldn't happen)
                logger.warning("[WSGI] ⚠️ Scheduler exited normally - restarting in 5 seconds...")
                db.add_log_entry('WARNING', '[WSGI] Scheduler exited unexpectedly! Restarting in 5s...', 'wsgi')
                time.sleep(5)

            except Exception as e:
                logger.error(f"[WSGI] ❌ Scheduler crashed: {e}")
                import traceback
                error_msg = f"[WSGI] Scheduler crashed (attempt #{restart_count}): {e}"
                logger.error(f"[WSGI] Traceback:\n{traceback.format_exc()}")

                if db:
                    db.add_log_entry('ERROR', error_msg, 'wsgi')

                # Exponential backoff - wait longer after each failure (up to 60s)
                restart_delay = min(restart_count * 2, max_restart_delay)
                logger.info(f"[WSGI] 🔄 Restarting scheduler in {restart_delay} seconds...")
                if db:
                    db.add_log_entry('INFO', f'[WSGI] Auto-restarting in {restart_delay}s...', 'wsgi')

                time.sleep(restart_delay)

    # Start scheduler in daemon thread (dies when main process exits)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
    scheduler_thread.start()

    logger.info("✅ Background scheduler thread started with auto-restart")
    logger.info("✅ Web UI + Auto-scan scheduler are both running")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
