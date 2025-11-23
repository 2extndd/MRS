"""
Gunicorn configuration for MercariSearcher
Handles scheduler startup in worker processes after fork
"""

import logging
import threading
import os

logger = logging.getLogger(__name__)

# Bind address - use PORT from environment (Railway sets this dynamically)
port = int(os.getenv('PORT', 8080))
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = 1  # Single worker to avoid multiple scheduler instances
timeout = 30
loglevel = "info"

# Store scheduler thread reference
_scheduler_thread = None


def post_fork(server, worker):
    """
    Called just after a worker has been forked.
    Start the background scheduler here to avoid fork() issues.
    """
    global _scheduler_thread

    # Print to stdout immediately (logger might not work yet)
    print("=" * 60, flush=True)
    print(f"[GUNICORN] post_fork hook CALLED for worker PID {worker.pid}", flush=True)
    print("=" * 60, flush=True)

    logger.info("=" * 60)
    logger.info(f"[GUNICORN] post_fork hook called for worker {worker.pid}")
    logger.info("=" * 60)

    def start_scheduler():
        """Start the search scheduler in background thread"""
        from db import get_db
        db = None

        try:
            logger.info("[GUNICORN] Starting background scheduler thread...")

            # Get DB connection for logging
            db = get_db()
            db.add_log_entry('INFO', f'[GUNICORN] post_fork: Starting scheduler in worker {worker.pid}', 'gunicorn')

            from mercari_notifications import MercariNotificationApp

            logger.info("[GUNICORN] Imported MercariNotificationApp")
            db.add_log_entry('INFO', '[GUNICORN] Imported MercariNotificationApp', 'gunicorn')

            # Create app instance and run scheduler
            logger.info("[GUNICORN] Creating MercariNotificationApp instance...")
            db.add_log_entry('INFO', '[GUNICORN] Creating MercariNotificationApp instance...', 'gunicorn')

            mercari_app = MercariNotificationApp()

            logger.info("[GUNICORN] MercariNotificationApp created successfully")
            db.add_log_entry('INFO', '[GUNICORN] MercariNotificationApp created successfully', 'gunicorn')

            logger.info("[GUNICORN] Calling run_scheduler()...")
            db.add_log_entry('INFO', '[GUNICORN] Calling run_scheduler()...', 'gunicorn')

            mercari_app.run_scheduler()

            logger.info("[GUNICORN] run_scheduler() returned (this should never happen)")
            db.add_log_entry('ERROR', '[GUNICORN] run_scheduler() returned unexpectedly!', 'gunicorn')

        except Exception as e:
            logger.error(f"[GUNICORN] ❌ Background scheduler error: {e}")
            import traceback
            error_msg = f"[GUNICORN] Scheduler error: {e}\n{traceback.format_exc()}"
            logger.error(f"[GUNICORN] Traceback:\n{traceback.format_exc()}")

            if db:
                db.add_log_entry('ERROR', error_msg, 'gunicorn')

    # Start scheduler in daemon thread (dies when worker exits)
    try:
        _scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
        _scheduler_thread.start()

        print(f"[GUNICORN] ✅ Scheduler thread started successfully", flush=True)
        logger.info(f"✅ Background scheduler thread started in worker {worker.pid}")
    except Exception as e:
        print(f"[GUNICORN] ❌ Failed to start scheduler thread: {e}", flush=True)
        logger.error(f"❌ Failed to start scheduler thread: {e}")
        import traceback
        logger.error(traceback.format_exc())


def on_exit(server):
    """Called just before the master process is exited."""
    logger.info("[GUNICORN] Master process exiting")
