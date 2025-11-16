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

# Tokyo timezone
TOKYO_TZ = pytz.timezone('Asia/Tokyo')

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

    def search_and_notify(self):
        """Main search cycle with notifications"""
        logger.info("\n" + "=" * 60)
        logger.info(f"Starting search cycle at {datetime.now(TOKYO_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 60)

        try:
            # Perform searches
            results = self.searcher.search_all_queries()

            # Process notifications for new items
            if results['new_items'] > 0:
                logger.info(f"Processing {results['new_items']} new items for notifications...")
                notification_stats = process_pending_notifications()
                logger.info(f"Notifications: {notification_stats['sent']}/{notification_stats['total']} sent")

            # Update metrics
            metrics_storage.set_last_search_time()

            # Check for auto-redeploy if configured
            if redeployer:
                redeployer.check_and_redeploy_if_needed()

        except Exception as e:
            logger.error(f"Search cycle error: {e}")
            self.shared_state.add_error(str(e))
            self.db.log_error(str(e), 'search_cycle')

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
        logger.info(f"Search cycle will run every 60 seconds")
        logger.info(f"Individual queries use their own scan intervals")
        logger.info("=" * 60 + "\n")

        # Schedule tasks
        schedule.every(60).seconds.do(self.search_and_notify)
        schedule.every().day.at("03:00").do(self.cleanup_old_data)
        schedule.every(2).hours.do(self.refresh_proxies)

        # Send startup notification
        try:
            send_system_message(
                f"MercariSearcher started\n"
                f"Version: {config.APP_VERSION}\n"
                f"Environment: {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}\n"
                f"Active searches: {len(self.db.get_active_searches())}"
            )
        except Exception as e:
            logger.warning(f"Failed to send startup notification: {e}")

        # Run scheduler loop
        logger.info("Scheduler is running. Press Ctrl+C to stop.")

        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\nShutdown requested by user")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(5)

        # Cleanup
        self.shutdown()

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
