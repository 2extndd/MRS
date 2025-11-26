#!/usr/bin/env python3
"""
Standalone script to run Mercari search scheduler in infinite loop.
Can be run as either:
1. Single cycle mode (default): python run_search_cycle.py
2. Infinite loop mode: python run_search_cycle.py --loop

Usage:
    python run_search_cycle.py          # Run one cycle and exit
    python run_search_cycle.py --loop   # Run infinite scheduler loop
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

def run_single_cycle():
    """Run a single search cycle and exit"""
    try:
        logger.info("=" * 60)
        logger.info(f"[CYCLE] Starting search cycle at {datetime.now()}")
        logger.info("=" * 60)

        # Import here to avoid loading everything at module level
        from mercari_notifications import MercariNotificationApp

        # Create app instance
        app = MercariNotificationApp()

        logger.info("[CYCLE] Running single search cycle...")

        # Run search cycle (finds new items)
        app.search_cycle()

        logger.info("[CYCLE] Running Telegram notification cycle...")

        # Run Telegram cycle (sends notifications)
        app.telegram_cycle()

        logger.info("[CYCLE] ✅ Search cycle completed successfully")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"[CYCLE] ❌ Error during search cycle: {e}")
        import traceback
        logger.error(f"[CYCLE] Traceback:\n{traceback.format_exc()}")
        return 1

def run_infinite_loop():
    """Run scheduler in infinite loop with automatic restart on crashes"""
    import time
    restart_count = 0
    max_restart_delay = 60

    while True:  # Infinite loop - runs forever
        restart_count += 1
        try:
            logger.info("=" * 60)
            logger.info(f"[SCHEDULER] Starting scheduler loop (attempt #{restart_count})...")
            logger.info("=" * 60)

            from mercari_notifications import MercariNotificationApp
            app = MercariNotificationApp()

            logger.info("[SCHEDULER] ✅ Starting infinite scheduler...")
            app.run_scheduler()  # This should run forever

            # If run_scheduler() exits (shouldn't happen), log and restart
            logger.warning(f"[SCHEDULER] ⚠️ Scheduler loop ended unexpectedly - restarting...")

        except Exception as e:
            logger.error(f"[SCHEDULER] ❌ Scheduler crashed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # Calculate restart delay with exponential backoff
        restart_delay = min(restart_count * 5, max_restart_delay)
        logger.info(f"[SCHEDULER] Restarting in {restart_delay} seconds...")
        time.sleep(restart_delay)

if __name__ == "__main__":
    # Check if --loop flag is provided
    if "--loop" in sys.argv:
        logger.info("[MAIN] Running in INFINITE LOOP mode")
        run_infinite_loop()
    else:
        logger.info("[MAIN] Running in SINGLE CYCLE mode")
        exit_code = run_single_cycle()
        sys.exit(exit_code)
