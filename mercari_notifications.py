"""
MercariSearcher - Main application file
Automated Mercari.jp item monitoring with Telegram notifications
Adapted from KufarSearcher (KS1)
"""

import os
import sys
import logging
import schedule
import time
from datetime import datetime
import pytz

from configuration_values import config
from db import get_db
from core import MercariSearcher
from simple_telegram_worker import process_pending_notifications, send_system_message
from shared_state import get_shared_state
from railway_redeploy import redeployer
from metrics_storage import metrics_storage
from proxies import proxy_manager

# Timezones
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
UTC_TZ = pytz.UTC

# Setup logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

# Configure logging based on environment
if os.getenv('RAILWAY_ENVIRONMENT'):
    # Railway: log to stdout
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        stream=sys.stdout
    )
else:
    # Local: log to file and stdout
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)


class MercariNotificationApp:
    """Main application class"""

    def __init__(self):
        self.db = get_db()
        self.shared_state = get_shared_state()
        self.searcher = None

        logger.info("=" * 60)
        logger.info(f"{config.APP_NAME} v{config.APP_VERSION} Starting...")
        logger.info("=" * 60)

        # CRITICAL: Load config from database BEFORE initializing scheduler
        # This ensures SEARCH_INTERVAL uses database value (60s) instead of .env default (300s)
        logger.info("[CONFIG] Loading configuration from database before scheduler init...")
        self.db.add_log_entry('INFO', '[CONFIG] Loading config from database...', 'config')

        config.reload_if_needed()

        logger.info(f"[CONFIG] Using SEARCH_INTERVAL = {config.SEARCH_INTERVAL}s from database")
        logger.info(f"[CONFIG] Category blacklist: {len(config.CATEGORY_BLACKLIST)} categories")

        self.db.add_log_entry('INFO', f'[CONFIG] SEARCH_INTERVAL={config.SEARCH_INTERVAL}s', 'config')
        self.db.add_log_entry('INFO', f'[CONFIG] Category blacklist: {len(config.CATEGORY_BLACKLIST)} categories', 'config')

        # Validate configuration
        errors = config.validate_config()
        if errors:
            logger.warning("Configuration warnings (some features may not work):")
            for error in errors:
                logger.warning(f"  - {error}")
            # Don't exit - allow web UI to work even if Telegram not configured
            # sys.exit(1)  # Commented out to allow graceful degradation

        # Initialize searcher
        self.init_searcher()

        # Update shared state
        self.shared_state.update(
            app_start_time=datetime.now(),
            worker_status='running'
        )

        logger.info("Application initialized successfully")

    def init_searcher(self):
        """Initialize Mercari searcher"""
        try:
            self.searcher = MercariSearcher(use_proxy=config.PROXY_ENABLED)
            logger.info("MercariSearcher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize searcher: {e}")
            raise

    def search_cycle(self):
        """Search cycle - ONLY searches and adds to DB"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                from datetime import datetime as dt_now
                current_time_str = dt_now.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
                logger.info("\n" + "=" * 60)
                logger.info(f"Starting search cycle at {current_time_str}")
                logger.info("=" * 60)

                # Perform searches
                results = self.searcher.search_all_queries()

                # Update metrics
                metrics_storage.set_last_search_time()

                # Check for auto-redeploy if configured
                if redeployer:
                    redeployer.check_and_redeploy_if_needed()

                # Only log to DB if there were actual results
                if results:
                    self.db.add_log_entry('INFO', f'[SEARCH] Completed at {current_time_str}', 'search')
                
                return  # Success, exit retry loop

            except Exception as e:
                retry_count += 1
                logger.error(f"Search cycle error (attempt {retry_count}/{max_retries}): {e}")
                self.shared_state.add_error(str(e))
                
                try:
                    self.db.log_error(str(e), 'search_cycle')
                    self.db.add_log_entry('ERROR', f'[SEARCH] Exception (attempt {retry_count}): {str(e)[:150]}', 'search')
                except Exception as db_error:
                    logger.error(f"Failed to log error to database: {db_error}")
                
                if retry_count < max_retries:
                    sleep_time = retry_count * 5  # Exponential backoff
                    logger.info(f"[SEARCH] Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"[SEARCH] All retry attempts exhausted")
                    import traceback
                    logger.error(f"[SEARCH] Traceback:\n{traceback.format_exc()}")
                    # Don't raise - let scheduler continue
    
    def telegram_cycle(self):
        """Telegram notification cycle - INDEPENDENT from search"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info("[TELEGRAM] Processing pending notifications...")

                # Process 60 items per cycle (2 items/sec = faster delivery)
                notification_stats = process_pending_notifications(max_items=60)

                if notification_stats['total'] > 0:
                    logger.info(f"[TELEGRAM] Sent {notification_stats['sent']}/{notification_stats['total']} notifications")
                    # Only log to DB if there were actual notifications sent
                    try:
                        self.db.add_log_entry('INFO', f'[TELEGRAM] Sent {notification_stats["sent"]}/{notification_stats["total"]}', 'telegram')
                    except Exception as db_error:
                        logger.error(f"Failed to log to database: {db_error}")
                    
                    if notification_stats['failed'] > 0:
                        logger.warning(f"[TELEGRAM] Failed to send {notification_stats['failed']} notifications")
                else:
                    logger.debug("[TELEGRAM] No pending notifications")  # Changed to debug to reduce noise
                
                return  # Success, exit retry loop

            except Exception as e:
                retry_count += 1
                logger.error(f"[TELEGRAM] Notification cycle error (attempt {retry_count}/{max_retries}): {e}")
                logger.error(f"[TELEGRAM] Error details: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"[TELEGRAM] Traceback:\n{traceback.format_exc()}")
                
                self.shared_state.add_error(str(e))
                
                try:
                    self.db.log_error(str(e), 'telegram_cycle')
                except Exception as db_error:
                    logger.error(f"Failed to log error to database: {db_error}")
                
                if retry_count < max_retries:
                    sleep_time = retry_count * 5  # Exponential backoff
                    logger.info(f"[TELEGRAM] Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"[TELEGRAM] All retry attempts exhausted")
                    # Don't raise - let scheduler continue

    def cleanup_old_data(self):
        """Periodic cleanup of old data"""
        logger.info("Running cleanup of old data...")
        try:
            self.db.cleanup_old_data()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def refresh_proxies(self):
        """Refresh proxy list"""
        if proxy_manager:
            logger.info("Refreshing proxy list...")
            try:
                proxy_manager.validate_proxies()
                stats = proxy_manager.get_proxy_stats()
                logger.info(f"Proxy refresh complete: {stats['working']}/{stats['total']} working")
            except Exception as e:
                logger.error(f"Proxy refresh error: {e}")

    def run_scheduler(self):
        """Run the scheduler"""
        logger.info("\n" + "=" * 60)
        logger.info("Starting scheduler")
        logger.info(f"Search cycle will run every {config.SEARCH_INTERVAL} seconds (Query Delay)")
        logger.info(f"Individual queries use their own scan intervals")
        logger.info("=" * 60 + "\n")

        # Initial schedule setup
        self._setup_schedule()

        # Run scheduler loop FIRST (most important!)
        logger.info("[STARTUP] ✅ Scheduler loop starting...")
        logger.info(f"[STARTUP] Config hot reload: enabled (every {config._reload_interval}s)")
        logger.info("="*60)

        # Send startup notification AFTER loop starts (non-blocking)
        # This runs in a separate thread to not block the scheduler
        def send_startup_notification():
            try:
                import time
                time.sleep(2)  # Small delay to ensure loop started

                active_searches = self.db.get_active_searches()
                logger.info(f"[STARTUP] ✅ Active searches: {len(active_searches)}")
                for search in active_searches:
                    logger.info(f"[STARTUP]    - {search.get('name')} (ID: {search.get('id')})")

                send_system_message(
                    f"🚀 MercariSearcher started\n"
                    f"Version: {config.APP_VERSION}\n"
                    f"Environment: {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}\n"
                    f"Active searches: {len(active_searches)}"
                )
                logger.info(f"[STARTUP] ✅ Startup notification sent to Telegram")
            except Exception as e:
                logger.warning(f"[STARTUP] ⚠️  Failed to send startup notification: {e}")
                import traceback
                logger.warning(f"[STARTUP] Traceback:\n{traceback.format_exc()}")

        # Start notification in background thread (non-blocking)
        import threading
        notification_thread = threading.Thread(target=send_startup_notification, daemon=True)
        notification_thread.start()

        last_interval = config.SEARCH_INTERVAL

        logger.info("[SCHEDULER] ⏰ Entering main loop...")
        logger.info(f"[SCHEDULER] Jobs scheduled: {len(schedule.get_jobs())}")

        # Log to DB (persistent)
        self.db.add_log_entry('INFO', f'[SCHEDULER] Entering main loop with {len(schedule.get_jobs())} jobs', 'scheduler')

        # Get health state from shared_state for heartbeat updates
        from datetime import datetime as dt_for_heartbeat
        self.shared_state.set('scheduler_last_heartbeat', dt_for_heartbeat.now())
        self.shared_state.set('scheduler_is_alive', True)

        loop_iteration = 0
        while True:
            try:
                loop_iteration += 1

                # Log first iteration and every 10 seconds
                if loop_iteration == 1:
                    # Debug: Check schedule state
                    current_time = dt_for_heartbeat.now()
                    jobs_info = []
                    for job in schedule.get_jobs():
                        jobs_info.append(f"{job.job_func.__name__}: next={job.next_run}")

                    logger.info(f"[SCHEDULER] ⏰ First iteration starting...")
                    logger.info(f"[SCHEDULER] Current time: {current_time}")
                    logger.info(f"[SCHEDULER] Jobs: {', '.join(jobs_info)}")

                    # Log to DB with full details
                    jobs_detail = ', '.join(jobs_info)
                    self.db.add_log_entry('INFO', f'[SCHEDULER] Time: {current_time}', 'scheduler')
                    self.db.add_log_entry('INFO', f'[SCHEDULER] Jobs detail: {jobs_detail}', 'scheduler')

                # Reduced logging frequency: every 60 iterations (1 minute) instead of 10 seconds
                if loop_iteration % 60 == 0:
                    logger.info(f"[SCHEDULER] ⏰ Loop alive! Iteration {loop_iteration}, calling run_pending()...")

                # HOT RELOAD CONFIG EVERY ITERATION (with error handling)
                try:
                    if config.reload_if_needed():
                        logger.info("[CONFIG] ✅ Configuration reloaded from database")
                        try:
                            self.db.add_log_entry('INFO', 'Configuration reloaded from database', 'config')
                        except Exception as db_log_error:
                            logger.warning(f"[CONFIG] Failed to log to database: {db_log_error}")

                        # If search interval changed, recreate schedule
                        if config.SEARCH_INTERVAL != last_interval:
                            logger.info(f"[CONFIG] Search interval changed from {last_interval}s to {config.SEARCH_INTERVAL}s, updating schedule...")
                            try:
                                self.db.add_log_entry('INFO', f"Search interval changed: {last_interval}s → {config.SEARCH_INTERVAL}s", 'config')
                            except Exception as db_log_error:
                                logger.warning(f"[CONFIG] Failed to log to database: {db_log_error}")
                            self._setup_schedule()
                            last_interval = config.SEARCH_INTERVAL
                except Exception as config_error:
                    logger.warning(f"[CONFIG] ⚠️ Failed to reload config: {config_error}")
                    # Continue with cached config - don't break the scheduler loop!

                # Run pending jobs (with error handling built into each job)
                try:
                    schedule.run_pending()
                except Exception as schedule_error:
                    logger.error(f"[SCHEDULER] ❌ Error in run_pending(): {schedule_error}")
                    import traceback
                    logger.error(f"[SCHEDULER] Traceback:\n{traceback.format_exc()}")
                    # Continue - don't break the loop!

                # Log after first run_pending() only
                if loop_iteration == 1:
                    logger.info(f"[SCHEDULER] ⏰ First run_pending() completed")
                    self.db.add_log_entry('INFO', '[SCHEDULER] First run_pending() done', 'scheduler')

                # Update heartbeat every 10 iterations (10 seconds)
                if loop_iteration % 10 == 0:
                    try:
                        self.shared_state.set('scheduler_last_heartbeat', dt_for_heartbeat.now())
                        self.shared_state.set('scheduler_is_alive', True)
                    except Exception as heartbeat_error:
                        # Don't break loop if heartbeat fails
                        pass

                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\nShutdown requested by user")
                break
            except Exception as e:
                logger.error(f"[SCHEDULER] ❌ Scheduler error: {e}")
                import traceback
                logger.error(f"[SCHEDULER] Traceback:\n{traceback.format_exc()}")
                time.sleep(5)

        # Cleanup
        self.shutdown()

    def _setup_schedule(self):
        """Setup or recreate the schedule with current config"""
        # Clear existing jobs
        schedule.clear()

        # INDEPENDENT PROCESSES:
        # 1. Search cycle - scans and adds to DB
        schedule.every(config.SEARCH_INTERVAL).seconds.do(self.search_cycle)

        # 2. Telegram cycle - sends from DB (INDEPENDENT!)
        # Run every 35 seconds with 60 items per batch (60 items * 0.5s delay = ~30s + API calls)
        schedule.every(35).seconds.do(self.telegram_cycle)

        # 3. Maintenance tasks
        # Use UTC timezone for scheduled tasks (Railway is UTC)
        # 03:00 UTC = 06:00 MSK (Moscow time)
        schedule.every().day.at("03:00", "UTC").do(self.cleanup_old_data)
        schedule.every(2).hours.do(self.refresh_proxies)

        logger.info(f"[SCHEDULER] ⏱  Search cycle: every {config.SEARCH_INTERVAL}s")
        logger.info(f"[SCHEDULER] 📬 Telegram cycle: every 35s (60 items per batch, 2 items/sec)")
        logger.info(f"[SCHEDULER] 🧹 Cleanup: daily at 03:00 UTC (06:00 MSK)")
        logger.info(f"[SCHEDULER] 🔧 Total jobs scheduled: {len(schedule.get_jobs())}")

    def shutdown(self):
        """Shutdown application"""
        logger.info("Shutting down...")

        try:
            send_system_message("MercariSearcher shutting down")
        except:
            pass

        self.shared_state.set('worker_status', 'stopped')
        logger.info("Shutdown complete")

    def run_web_ui(self):
        """Run Flask web UI"""
        from web_ui_plugin.app import app

        logger.info(f"Starting web UI on {config.WEB_UI_HOST}:{config.PORT}")

        self.shared_state.set('web_ui_status', 'running')

        app.run(
            host=config.WEB_UI_HOST,
            port=config.PORT,
            debug=False
        )


def main():
    """Main entry point"""
    # Check command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else 'default'

    app = MercariNotificationApp()

    if mode == 'web':
        # Web UI only mode
        app.run_web_ui()
    elif mode == 'worker':
        # Worker only mode
        app.run_scheduler()
    else:
        # Default: run scheduler
        app.run_scheduler()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nApplication stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        sys.exit(1)
