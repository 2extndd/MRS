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

    # Global health check state
    scheduler_health = {
        'last_heartbeat': None,
        'is_alive': False,
        'restart_count': 0,
        'thread': None
    }

    # Start background scheduler in separate thread with auto-restart
    def start_scheduler():
        """Start the search scheduler in background thread with auto-restart on failure"""
        import time
        from datetime import datetime
        from db import get_db

        restart_count = 0
        max_restart_delay = 60  # Maximum 60 seconds between restarts

        while True:  # Infinite loop - restart scheduler forever
            db = None
            restart_count += 1
            scheduler_health['restart_count'] = restart_count

            try:
                logger.info("=" * 60)
                logger.info(f"[WSGI] Starting background scheduler (attempt #{restart_count})...")
                logger.info("=" * 60)

                # Get DB connection for logging
                db = get_db()
                try:
                    db.add_log_entry('INFO', f'[WSGI] Starting scheduler (attempt #{restart_count})...', 'wsgi')
                except Exception as db_error:
                    logger.warning(f"[WSGI] Failed to log to DB: {db_error}")

                from mercari_notifications import MercariNotificationApp

                logger.info("[WSGI] Imported MercariNotificationApp")
                try:
                    db.add_log_entry('INFO', '[WSGI] Imported MercariNotificationApp', 'wsgi')
                except:
                    pass

                # Create app instance and run scheduler
                logger.info("[WSGI] Creating MercariNotificationApp instance...")
                try:
                    db.add_log_entry('INFO', '[WSGI] Creating MercariNotificationApp instance...', 'wsgi')
                except:
                    pass

                mercari_app = MercariNotificationApp()

                logger.info("[WSGI] MercariNotificationApp created successfully")
                try:
                    db.add_log_entry('INFO', '[WSGI] MercariNotificationApp created successfully', 'wsgi')
                except:
                    pass

                logger.info("[WSGI] Calling run_scheduler()...")
                try:
                    db.add_log_entry('INFO', '[WSGI] Calling run_scheduler()...', 'wsgi')
                except:
                    pass

                # Mark as alive before starting
                scheduler_health['is_alive'] = True
                scheduler_health['last_heartbeat'] = datetime.now()

                mercari_app.run_scheduler()

                # If we get here, scheduler exited normally (shouldn't happen)
                logger.warning("[WSGI] ⚠️ Scheduler exited normally - restarting in 5 seconds...")
                scheduler_health['is_alive'] = False
                try:
                    db.add_log_entry('WARNING', '[WSGI] Scheduler exited unexpectedly! Restarting in 5s...', 'wsgi')
                except:
                    pass
                time.sleep(5)

            except Exception as e:
                scheduler_health['is_alive'] = False
                logger.error(f"[WSGI] ❌ Scheduler crashed: {e}")
                import traceback
                error_msg = f"[WSGI] Scheduler crashed (attempt #{restart_count}): {str(e)[:200]}"
                logger.error(f"[WSGI] Traceback:\n{traceback.format_exc()}")

                if db:
                    try:
                        db.add_log_entry('ERROR', error_msg, 'wsgi')
                    except Exception as db_error:
                        logger.warning(f"[WSGI] Failed to log error to DB: {db_error}")

                # Exponential backoff - wait longer after each failure (up to 60s)
                restart_delay = min(restart_count * 2, max_restart_delay)
                logger.info(f"[WSGI] 🔄 Restarting scheduler in {restart_delay} seconds...")
                if db:
                    try:
                        db.add_log_entry('INFO', f'[WSGI] Auto-restarting in {restart_delay}s...', 'wsgi')
                    except:
                        pass

                time.sleep(restart_delay)

    def health_check_monitor():
        """Monitor scheduler health and restart if dead - MORE AGGRESSIVE!"""
        import time
        from datetime import datetime, timedelta

        logger.info("[HEALTH] ⚡ AGGRESSIVE health check monitor started (checks every 30s)")

        while True:
            try:
                time.sleep(30)  # Check every 30 seconds (was 60)

                # Check if scheduler thread is alive
                if not scheduler_health.get('thread') or not scheduler_health['thread'].is_alive():
                    logger.error("[HEALTH] ❌❌❌ Scheduler thread is DEAD or MISSING! RESTARTING NOW...")

                    # Restart scheduler thread
                    new_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
                    new_thread.start()
                    scheduler_health['thread'] = new_thread

                    logger.info("[HEALTH] ✅✅✅ Scheduler thread RESTARTED successfully")

                # Check heartbeat timeout (no updates for 2 minutes = RESTART!)
                if scheduler_health['last_heartbeat']:
                    elapsed = datetime.now() - scheduler_health['last_heartbeat']
                    # AGGRESSIVE: Restart after 2 min of no heartbeat (was 5 min)
                    if elapsed > timedelta(minutes=2):
                        logger.error(f"[HEALTH] ❌❌❌ No heartbeat for {elapsed.total_seconds():.0f} seconds - FORCING RESTART!")

                        # Kill existing thread if it exists
                        if scheduler_health.get('thread'):
                            logger.warning("[HEALTH] Killing zombie scheduler thread...")

                        # Force restart
                        new_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
                        new_thread.start()
                        scheduler_health['thread'] = new_thread
                        scheduler_health['is_alive'] = False  # Will be set to True by new thread

                        logger.info("[HEALTH] ✅ Scheduler force-restarted due to heartbeat timeout")
                else:
                    # No heartbeat ever recorded = scheduler never started!
                    elapsed_since_boot = time.time()  # Rough estimate
                    if elapsed_since_boot > 120:  # 2 minutes after boot
                        logger.error("[HEALTH] ❌ No heartbeat recorded after 2 min! Starting scheduler...")
                        new_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
                        new_thread.start()
                        scheduler_health['thread'] = new_thread

            except Exception as e:
                logger.error(f"[HEALTH] Health check error: {e}")

    # Start scheduler in daemon thread (dies when main process exits)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
    scheduler_thread.start()
    scheduler_health['thread'] = scheduler_thread

    # Start health check monitor
    health_thread = threading.Thread(target=health_check_monitor, daemon=True, name="HealthCheckThread")
    health_thread.start()

    logger.info("✅ Background scheduler thread started with auto-restart")
    logger.info("✅ Health check monitor started")
    logger.info("✅ Web UI + Auto-scan scheduler are both running")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


# ============================================================================
# CRITICAL FIX: Ensure scheduler starts in Gunicorn worker process
# ============================================================================
def post_worker_init(worker):
    """
    Called just after a worker has been initialized.
    This ensures scheduler starts in the actual worker process, not the master.
    """
    logger.info(f"[GUNICORN] Worker {worker.pid} initialized - ensuring scheduler is running")
    
    # Check if scheduler thread exists and is alive
    if not scheduler_health.get('thread') or not scheduler_health['thread'].is_alive():
        logger.warning(f"[GUNICORN] Scheduler not running in worker {worker.pid}, starting now...")
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=start_scheduler, daemon=True, name="SchedulerThread")
        scheduler_thread.start()
        scheduler_health['thread'] = scheduler_thread
        
        # Start health check monitor
        health_thread = threading.Thread(target=health_check_monitor, daemon=True, name="HealthCheckThread")
        health_thread.start()
        
        logger.info(f"[GUNICORN] ✅ Scheduler started in worker {worker.pid}")
    else:
        logger.info(f"[GUNICORN] ✅ Scheduler already running in worker {worker.pid}")


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
