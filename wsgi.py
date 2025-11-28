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

    # Auto-create performance indexes on Railway (runs once on startup)
    if os.getenv('RAILWAY_ENVIRONMENT'):
        logger.info("[WSGI] Railway environment detected - creating performance indexes...")
        try:
            from db import get_db
            db = get_db()

            # Only run on PostgreSQL (Railway)
            if db.db_type == 'postgresql':
                logger.info("[INDEXES] Creating performance indexes for items table...")

                indexes = [
                    ("idx_items_found_at", "CREATE INDEX IF NOT EXISTS idx_items_found_at ON items (found_at DESC)"),
                    ("idx_items_mercari_id_pattern", "CREATE INDEX IF NOT EXISTS idx_items_mercari_id_pattern ON items (mercari_id text_pattern_ops)"),
                    ("idx_items_category_id", "CREATE INDEX IF NOT EXISTS idx_items_category_id ON items (category_id) WHERE category_id IS NOT NULL"),
                ]

                for idx_name, sql in indexes:
                    try:
                        db.execute_query(sql)
                        logger.info(f"[INDEXES] ✅ Index created/verified: {idx_name}")
                    except Exception as e:
                        logger.error(f"[INDEXES] ❌ Failed to create {idx_name}: {e}")

                logger.info("[INDEXES] ✅ Performance indexes ready")
            else:
                logger.info("[INDEXES] Skipped - only needed on PostgreSQL")
        except Exception as e:
            logger.error(f"[INDEXES] ❌ Index creation failed: {e}")
            # Don't block startup if index creation fails

    # NOTE: Scheduler is now run via separate worker process in Procfile
    # No longer auto-started in wsgi.py thread (like KS1 architecture)
    logger.info("[WSGI] Scheduler runs in separate worker process (not in wsgi.py)")

except Exception as e:
    logger.error(f"Failed to load WSGI application: {e}")
    raise


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=True)
