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

# Moscow timezone (GMT+3 / UTC+3)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

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

        # Validate configuration
        errors = config.validate_config()
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            sys.exit(1)

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
        self.db.add_log_entry('INFO', '[SEARCH_CYCLE] *** FUNCTION CALLED ***', 'search')
        logger.info("\n" + "=" * 60)
        logger.info(f"Starting search cycle at {datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 60)

        try:
            # Perform searches
            results = self.searcher.search_all_queries()

            # Update metrics
            metrics_storage.set_last_search_time()

            # Check for auto-redeploy if configured
            if redeployer:
                redeployer.check_and_redeploy_if_needed()

        except Exception as e:
            logger.error(f"Search cycle error: {e}")
            self.shared_state.add_error(str(e))
            self.db.log_error(str(e), 'search_cycle')
    
    def telegram_cycle(self):
        """Telegram notification cycle - INDEPENDENT from search"""
        self.db.add_log_entry('INFO', '[TELEGRAM_CYCLE] *** FUNCTION CALLED ***', 'telegram')
        logger.info("[TELEGRAM] Processing pending notifications...")

        try:
            # Process 35 items per cycle
            notification_stats = process_pending_notifications(max_items=35)

            if notification_stats['total'] > 0:
                logger.info(f"[TELEGRAM] Sent {notification_stats['sent']}/{notification_stats['total']} notifications")
                if notification_stats['failed'] > 0:
                    logger.warning(f"[TELEGRAM] Failed to send {notification_stats['failed']} notifications")
            else:
                logger.info("[TELEGRAM] No pending notifications")

        except Exception as e:
            logger.error(f"[TELEGRAM] Notification cycle error: {e}")
            logger.error(f"[TELEGRAM] Error details: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"[TELEGRAM] Traceback:\n{traceback.format_exc()}")
            self.shared_state.add_error(str(e))
            self.db.log_error(str(e), 'telegram_cycle')

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

        loop_iteration = 0
        while True:
            try:
                loop_iteration += 1

                # Log first iteration and every 10 seconds
                if loop_iteration == 1:
                    # Debug: Check schedule state
                    from datetime import datetime
                    current_time = datetime.now()
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

                if loop_iteration % 10 == 0:
                    logger.info(f"[SCHEDULER] ⏰ Loop alive! Iteration {loop_iteration}, calling run_pending()...")
                    self.db.add_log_entry('INFO', f'[SCHEDULER] Loop iteration {loop_iteration}', 'scheduler')

                # HOT RELOAD CONFIG EVERY ITERATION
                if config.reload_if_needed():
                    logger.info("[CONFIG] ✅ Configuration reloaded from database")
                    self.db.add_log_entry('INFO', 'Configuration reloaded from database', 'config')

                    # If search interval changed, recreate schedule
                    if config.SEARCH_INTERVAL != last_interval:
                        logger.info(f"[CONFIG] Search interval changed from {last_interval}s to {config.SEARCH_INTERVAL}s, updating schedule...")
                        self.db.add_log_entry('INFO', f"Search interval changed: {last_interval}s → {config.SEARCH_INTERVAL}s", 'config')
                        self._setup_schedule()
                        last_interval = config.SEARCH_INTERVAL

                # Log schedule state BEFORE run_pending
                if loop_iteration % 10 == 0:
                    jobs_before = schedule.get_jobs()
                    self.db.add_log_entry('INFO', f'[SCHEDULER] Before run_pending: {len(jobs_before)} jobs', 'scheduler')

                schedule.run_pending()

                # Log after first run_pending()
                if loop_iteration == 1:
                    logger.info(f"[SCHEDULER] ⏰ First run_pending() completed")
                    self.db.add_log_entry('INFO', '[SCHEDULER] First run_pending() done', 'scheduler')

                # Log every 10 iterations AFTER run_pending()
                if loop_iteration % 10 == 0:
                    from datetime import datetime as dt_check
                    current_time_check = dt_check.now()
                    jobs_after = schedule.get_jobs()
                    next_times = [str(job.next_run) for job in jobs_after]
                    self.db.add_log_entry('INFO', f'[SCHEDULER] After run_pending at {current_time_check}: next_run times = {next_times}', 'scheduler')

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
        # Run every 10 seconds with 35 items per batch
        schedule.every(10).seconds.do(self.telegram_cycle)
        
        # 3. Maintenance tasks
        schedule.every().day.at("03:00").do(self.cleanup_old_data)
        schedule.every(2).hours.do(self.refresh_proxies)

        logger.info(f"[SCHEDULER] ⏱  Search cycle: every {config.SEARCH_INTERVAL}s")
        logger.info(f"[SCHEDULER] 📬 Telegram cycle: every 10s (35 items per batch)")
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
