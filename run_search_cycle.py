#!/usr/bin/env python3
"""
Standalone script to run a single Mercari search cycle.
Designed to be called by Railway Cron jobs every N minutes.

Usage:
    python run_search_cycle.py
"""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

def main():
    """Run a single search cycle and exit"""
    try:
        logger.info("=" * 60)
        logger.info(f"[CRON] Starting search cycle at {datetime.now()}")
        logger.info("=" * 60)

        # Import here to avoid loading everything at module level
        from mercari_notifications import MercariNotificationApp

        # Create app instance
        app = MercariNotificationApp()

        logger.info("[CRON] Running single search cycle...")

        # Run search cycle (finds new items)
        app.search_cycle()

        logger.info("[CRON] Running Telegram notification cycle...")

        # Run Telegram cycle (sends notifications)
        app.telegram_cycle()

        logger.info("[CRON] ✅ Search cycle completed successfully")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"[CRON] ❌ Error during search cycle: {e}")
        import traceback
        logger.error(f"[CRON] Traceback:\n{traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
