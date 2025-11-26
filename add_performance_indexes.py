#!/usr/bin/env python3
"""
Add performance indexes to items table

This script adds the following indexes:
1. idx_items_found_at - for sorting by found_at DESC
2. idx_items_mercari_id - for filtering by mercari_id pattern
3. idx_items_category_id - for filtering by category_id IS NULL

Run this script ONCE on Railway to optimize database performance.
"""

import sys
import logging
from db import MercariDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def add_indexes():
    """Add performance indexes to items table"""
    db = MercariDatabase()

    logger.info("=" * 60)
    logger.info("[INDEXES] Adding performance indexes to items table...")
    logger.info("=" * 60)

    # Only run on PostgreSQL (Railway)
    if db.db_type != 'postgresql':
        logger.warning("[INDEXES] Skipping - only needed on PostgreSQL (Railway)")
        return

    indexes = [
        # Index for ORDER BY found_at DESC (most important!)
        ("idx_items_found_at", "CREATE INDEX IF NOT EXISTS idx_items_found_at ON items (found_at DESC)"),

        # Index for WHERE mercari_id LIKE 'm%' / NOT LIKE 'm%'
        ("idx_items_mercari_id_pattern", "CREATE INDEX IF NOT EXISTS idx_items_mercari_id_pattern ON items (mercari_id text_pattern_ops)"),

        # Index for WHERE category_id IS NULL
        ("idx_items_category_id", "CREATE INDEX IF NOT EXISTS idx_items_category_id ON items (category_id) WHERE category_id IS NOT NULL"),
    ]

    for idx_name, sql in indexes:
        try:
            logger.info(f"[INDEXES] Creating index: {idx_name}...")
            db.execute_query(sql)
            logger.info(f"[INDEXES] ✅ Index created: {idx_name}")
        except Exception as e:
            logger.error(f"[INDEXES] ❌ Failed to create {idx_name}: {e}")
            # Continue with other indexes

    logger.info("=" * 60)
    logger.info("[INDEXES] ✅ All indexes created successfully!")
    logger.info("=" * 60)

    # Show existing indexes
    logger.info("[INDEXES] Existing indexes on items table:")
    try:
        result = db.execute_query("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'items'
            ORDER BY indexname
        """, fetch=True)

        for row in result:
            logger.info(f"  - {row['indexname']}: {row['indexdef']}")
    except Exception as e:
        logger.error(f"[INDEXES] Failed to list indexes: {e}")

if __name__ == "__main__":
    try:
        add_indexes()
        sys.exit(0)
    except Exception as e:
        logger.error(f"[INDEXES] Script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
