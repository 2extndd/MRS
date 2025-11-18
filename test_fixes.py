#!/usr/bin/env python3
"""
Test script to verify fixes for MercariSearcher
Tests:
1. mercapi search (fixed duplicate code issue)
2. thread_id handling in Telegram notifications
3. Database logging
"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyMercariAPI import Mercari
from db import get_db
from simple_telegram_worker import TelegramWorker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_mercari_search():
    """Test Mercari search functionality"""
    print("\n" + "="*80)
    print("TEST 1: Mercari Search (Fixed duplicate code issue)")
    print("="*80)
    
    try:
        api = Mercari()
        
        # Test with simple keyword
        test_keyword = "Nike"
        logger.info(f"Testing search with keyword: {test_keyword}")
        
        items = api.search(test_keyword, limit=5)
        
        logger.info(f"✅ Search successful! Found {len(items)} items")
        
        if len(items) > 0:
            logger.info("First item:")
            logger.info(f"  Title: {items[0].title}")
            logger.info(f"  Price: ¥{items[0].price}")
            logger.info(f"  URL: {items[0].url}")
            return True
        else:
            logger.warning("No items found, but search completed without errors")
            return True
            
    except Exception as e:
        logger.error(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_logging():
    """Test database logging functionality"""
    print("\n" + "="*80)
    print("TEST 2: Database Logging")
    print("="*80)
    
    try:
        db = get_db()
        
        # Test log entry
        logger.info("Testing log entry...")
        db.add_log_entry('INFO', 'Test log from test_fixes.py', 'test', 'Testing logging functionality')
        
        # Retrieve recent logs
        logs = db.get_logs(limit=5)
        
        if logs:
            logger.info(f"✅ Successfully retrieved {len(logs)} log entries")
            logger.info("Most recent log:")
            logger.info(f"  Level: {logs[0].get('level')}")
            logger.info(f"  Message: {logs[0].get('message')}")
            return True
        else:
            logger.warning("No logs found in database")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thread_id_handling():
    """Test thread_id handling in get_unsent_items"""
    print("\n" + "="*80)
    print("TEST 3: Thread ID Handling")
    print("="*80)
    
    try:
        db = get_db()
        
        # Get unsent items (should now include search_thread_id)
        logger.info("Testing get_unsent_items with thread_id...")
        unsent_items = db.get_unsent_items()
        
        logger.info(f"✅ Successfully retrieved {len(unsent_items)} unsent items")
        
        if unsent_items:
            first_item = unsent_items[0]
            logger.info("First unsent item:")
            logger.info(f"  Title: {first_item.get('title', 'N/A')}")
            logger.info(f"  Search keyword: {first_item.get('search_keyword', 'N/A')}")
            logger.info(f"  Thread ID: {first_item.get('search_thread_id', 'None')}")
            
            # Check if thread_id field is present
            if 'search_thread_id' in first_item:
                logger.info("✅ thread_id field is present in query result")
                return True
            else:
                logger.error("❌ thread_id field is MISSING from query result")
                return False
        else:
            logger.info("No unsent items found (this is OK if all items are already sent)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Thread ID test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 MERCARI SEARCHER - FIX VERIFICATION TESTS")
    print("="*80)
    
    results = {
        'mercari_search': test_mercari_search(),
        'database_logging': test_database_logging(),
        'thread_id_handling': test_thread_id_handling()
    }
    
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Please review errors above")
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
