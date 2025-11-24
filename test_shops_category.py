#!/usr/bin/env python3
"""
Test script to check what attributes Shops items have from mercapi search
"""
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_shops_search():
    """Test searching for Shops items and check their attributes"""
    try:
        from mercapi import Mercapi

        # Initialize mercapi client
        m = Mercapi()

        # Search for "archive" which returns many Shops items
        logger.info("Searching for 'archive'...")
        results = await m.search(query="archive")

        logger.info(f"Found {len(results.items)} items")

        # Check first few items
        for idx, item in enumerate(results.items[:5], 1):
            item_id = getattr(item, 'id_', 'NO_ID')
            item_name = getattr(item, 'name', 'NO_NAME')
            is_shops = not item_id.startswith('m')

            logger.info(f"\n{'='*60}")
            logger.info(f"Item {idx}: {item_id} ({'SHOPS' if is_shops else 'REGULAR'})")
            logger.info(f"  Name: {item_name[:50]}...")

            # Check for category_id attribute
            has_category_id = hasattr(item, 'category_id')
            category_id_value = getattr(item, 'category_id', None)
            logger.info(f"  hasattr(item, 'category_id'): {has_category_id}")
            logger.info(f"  getattr(item, 'category_id', None): {category_id_value}")

            # Check for item_category attribute
            has_item_category = hasattr(item, 'item_category')
            item_category_value = getattr(item, 'item_category', None)
            logger.info(f"  hasattr(item, 'item_category'): {has_item_category}")
            logger.info(f"  getattr(item, 'item_category', None): {item_category_value}")

            # List all attributes that contain 'cat'
            logger.info("  Attributes containing 'cat':")
            for attr in dir(item):
                if 'cat' in attr.lower() and not attr.startswith('_'):
                    value = getattr(item, attr, 'ERROR')
                    logger.info(f"    - {attr}: {value}")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_shops_search())
