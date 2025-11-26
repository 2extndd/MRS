#!/usr/bin/env python3
"""
Health check script for scheduler - runs every 5 minutes via Railway cron
Checks if scheduler is alive by reading heartbeat from database
If dead for >10 min, logs error (Railway can restart web service based on cron failure)
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dateutil import parser

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Heartbeat timeout threshold
HEARTBEAT_TIMEOUT_MINUTES = 10  # If no heartbeat for 10 minutes, consider scheduler dead

def check_scheduler_health():
    """Check if scheduler is alive by reading heartbeat from database"""
    try:
        logger.info("=" * 60)
        logger.info("[HEALTH CHECK] Checking scheduler health from database...")
        logger.info("=" * 60)

        # Import database
        from db import MercariDatabase
        db = MercariDatabase()

        # Read heartbeat from database
        heartbeat_str = db.load_config('scheduler_heartbeat')

        if not heartbeat_str:
            logger.error("[HEALTH CHECK] ❌ No heartbeat found in database - scheduler never started!")
            return False

        # Parse heartbeat timestamp
        try:
            heartbeat_time = parser.isoparse(heartbeat_str)
        except Exception as parse_error:
            logger.error(f"[HEALTH CHECK] ❌ Failed to parse heartbeat timestamp: {heartbeat_str}")
            logger.error(f"[HEALTH CHECK] Parse error: {parse_error}")
            return False

        # Check if heartbeat is recent
        now = datetime.now(heartbeat_time.tzinfo) if heartbeat_time.tzinfo else datetime.now()
        age = now - heartbeat_time
        age_minutes = age.total_seconds() / 60

        logger.info(f"[HEALTH CHECK] Last heartbeat: {heartbeat_time}")
        logger.info(f"[HEALTH CHECK] Current time: {now}")
        logger.info(f"[HEALTH CHECK] Heartbeat age: {age_minutes:.1f} minutes")

        if age_minutes > HEARTBEAT_TIMEOUT_MINUTES:
            logger.error(f"[HEALTH CHECK] ❌ Scheduler is DEAD! No heartbeat for {age_minutes:.1f} minutes (threshold: {HEARTBEAT_TIMEOUT_MINUTES} min)")
            logger.error("[HEALTH CHECK] ❌ Railway should restart the web service!")
            return False
        else:
            logger.info(f"[HEALTH CHECK] ✅ Scheduler is ALIVE! Last heartbeat {age_minutes:.1f} minutes ago")
            return True

    except Exception as e:
        logger.error(f"[HEALTH CHECK] ❌ Failed to check health: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main health check logic"""
    logger.info("=" * 60)
    logger.info(f"[HEALTH CHECK] Starting health check at {datetime.now()}")
    logger.info("=" * 60)

    is_healthy = check_scheduler_health()

    if not is_healthy:
        logger.error("[HEALTH CHECK] ❌ Scheduler is NOT healthy!")
        logger.error("[HEALTH CHECK] ❌ Exiting with error code 1")
        logger.error("[HEALTH CHECK] ❌ This will be logged in Railway cron job logs")
        logger.info("=" * 60)
        return 1
    else:
        logger.info("[HEALTH CHECK] ✅ Scheduler is healthy, no action needed")
        logger.info("=" * 60)
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
