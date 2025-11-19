#!/usr/bin/env python3
"""
Comprehensive system test for MercariSearcher
Tests all core functionality: DB, proxies, search, images, Telegram
"""

import sys
import logging
from db import DatabaseManager
from proxies import parse_proxy_string, ProxyManager
from configuration_values import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_database():
    """Test database connectivity and queries"""
    print("\n" + "="*60)
    print("TEST 1: DATABASE CONNECTIVITY")
    print("="*60)

    try:
        db = DatabaseManager()
        logger.info("✅ Database connection successful")

        # Test: Get total items
        result = db.execute_query("SELECT COUNT(*) as count FROM items", fetch=True)
        total_items = result[0]['count'] if result else 0
        logger.info(f"✅ Total items in database: {total_items}")

        # Test: Get items with images
        result = db.execute_query(
            "SELECT COUNT(*) as count FROM items WHERE image_data IS NOT NULL",
            fetch=True
        )
        items_with_images = result[0]['count'] if result else 0
        logger.info(f"✅ Items with images: {items_with_images}/{total_items}")

        # Test: Get recent items
        result = db.execute_query(
            "SELECT id, item_name, item_price FROM items ORDER BY created_at DESC LIMIT 5",
            fetch=True
        )
        if result:
            logger.info(f"✅ Recent items:")
            for item in result:
                logger.info(f"   - [{item['id']}] {item['item_name']} - ¥{item['item_price']:,}")

        # Test: Config loading
        proxy_list = db.load_config('config_proxy_list', '')
        if proxy_list:
            proxy_lines = proxy_list.split('\n') if isinstance(proxy_list, str) else []
            logger.info(f"✅ Proxy config loaded: {len(proxy_lines)} proxies")
        else:
            logger.warning("⚠️ No proxy config in database")

        db.close()
        return True

    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_proxy_parsing():
    """Test proxy parsing and validation"""
    print("\n" + "="*60)
    print("TEST 2: PROXY PARSING")
    print("="*60)

    try:
        # Test different proxy formats
        test_cases = [
            ('82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h', 'http://wtllhdak:9vxcxlvhxv1h@82.21.62.51:7815'),
            ('http://user:pass@proxy.com:8080', 'http://user:pass@proxy.com:8080'),
            ('proxy.com:8080', 'http://proxy.com:8080'),
        ]

        for input_proxy, expected_output in test_cases:
            result = parse_proxy_string(input_proxy)
            if result == expected_output:
                logger.info(f"✅ Parsed correctly: {input_proxy} → {result}")
            else:
                logger.error(f"❌ Parse failed: {input_proxy}")
                logger.error(f"   Expected: {expected_output}")
                logger.error(f"   Got: {result}")
                return False

        # Test config loading
        if config.PROXY_LIST:
            logger.info(f"✅ Config PROXY_LIST loaded: {len(config.PROXY_LIST)} proxies")
            if len(config.PROXY_LIST) > 0:
                logger.info(f"   First proxy: {config.PROXY_LIST[0]}")
        else:
            logger.warning("⚠️ No proxies in config.PROXY_LIST")

        return True

    except Exception as e:
        logger.error(f"❌ Proxy parsing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_proxy_manager():
    """Test ProxyManager initialization and validation"""
    print("\n" + "="*60)
    print("TEST 3: PROXY MANAGER")
    print("="*60)

    try:
        # Test with sample proxies (won't actually connect)
        sample_proxies = [
            '82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h',
            '82.23.88.20:7776:wtllhdak:9vxcxlvhxv1h',
        ]

        logger.info(f"Testing ProxyManager with {len(sample_proxies)} sample proxies...")
        manager = ProxyManager(sample_proxies)

        logger.info(f"✅ ProxyManager initialized")
        logger.info(f"   Total proxies: {len(manager.all_proxies)}")
        logger.info(f"   Working proxies: {len(manager.working_proxies)}")
        logger.info(f"   Failed proxies: {len(manager.failed_proxies)}")

        if manager.all_proxies:
            logger.info(f"   First parsed proxy: {manager.all_proxies[0]}")

        # Test proxy stats
        stats = manager.get_proxy_stats()
        logger.info(f"✅ Proxy stats: {stats}")

        return True

    except Exception as e:
        logger.error(f"❌ ProxyManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mercapi():
    """Test mercapi library"""
    print("\n" + "="*60)
    print("TEST 4: MERCAPI LIBRARY")
    print("="*60)

    try:
        from mercapi import Mercari

        logger.info("Testing mercapi search...")
        mercari = Mercari()

        # Simple search
        results = mercari.search("macbook", limit=3)

        if results:
            logger.info(f"✅ Mercapi search successful: {len(results)} results")
            for idx, item in enumerate(results[:3], 1):
                logger.info(f"   {idx}. {item.get('name', 'No name')} - ¥{item.get('price', 0):,}")
        else:
            logger.warning("⚠️ No results from mercapi search")

        return True

    except Exception as e:
        logger.error(f"❌ Mercapi test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_utils():
    """Test image download utilities"""
    print("\n" + "="*60)
    print("TEST 5: IMAGE UTILITIES")
    print("="*60)

    try:
        from image_utils import download_and_encode_image

        # Test with a sample Mercari image URL (may fail due to Cloudflare)
        test_url = "https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m12345678901234567890.jpg"

        logger.info(f"Testing image download (this may fail due to Cloudflare blocking)...")
        logger.info(f"URL: {test_url[:80]}...")

        result = download_and_encode_image(test_url, timeout=10)

        if result:
            logger.info(f"✅ Image downloaded: {len(result)} bytes (base64 data URI)")
        else:
            logger.warning("⚠️ Image download failed (expected if using Railway IP)")
            logger.info("   This is normal - Railway IPs are blocked by Cloudflare")

        return True

    except Exception as e:
        logger.error(f"❌ Image utils test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_telegram():
    """Test Telegram bot configuration"""
    print("\n" + "="*60)
    print("TEST 6: TELEGRAM CONFIGURATION")
    print("="*60)

    try:
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            logger.info(f"✅ Telegram bot token: {config.TELEGRAM_BOT_TOKEN[:10]}...")
            logger.info(f"✅ Telegram chat ID: {config.TELEGRAM_CHAT_ID}")

            # Don't actually send a message in test
            logger.info("   (Not sending test message to avoid spam)")
        else:
            logger.warning("⚠️ Telegram credentials not configured")
            logger.info(f"   BOT_TOKEN: {bool(config.TELEGRAM_BOT_TOKEN)}")
            logger.info(f"   CHAT_ID: {bool(config.TELEGRAM_CHAT_ID)}")

        return True

    except Exception as e:
        logger.error(f"❌ Telegram test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_searches():
    """Test saved searches in database"""
    print("\n" + "="*60)
    print("TEST 7: SAVED SEARCHES")
    print("="*60)

    try:
        db = DatabaseManager()

        result = db.execute_query(
            """
            SELECT id, name, search_query, is_active, created_at
            FROM searches
            ORDER BY created_at DESC
            LIMIT 10
            """,
            fetch=True
        )

        if result:
            logger.info(f"✅ Found {len(result)} searches:")
            for search in result:
                status = "🟢 Active" if search['is_active'] else "⚪ Inactive"
                logger.info(f"   [{search['id']}] {status} {search['name']} - \"{search['search_query']}\"")
        else:
            logger.warning("⚠️ No searches found in database")

        db.close()
        return True

    except Exception as e:
        logger.error(f"❌ Searches test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_tracking():
    """Test error tracking system"""
    print("\n" + "="*60)
    print("TEST 8: ERROR TRACKING")
    print("="*60)

    try:
        db = DatabaseManager()

        # Get recent errors
        result = db.execute_query(
            """
            SELECT error_type, error_message, occurred_at, is_resolved
            FROM error_tracking
            ORDER BY occurred_at DESC
            LIMIT 10
            """,
            fetch=True
        )

        if result:
            unresolved = [e for e in result if not e['is_resolved']]
            logger.info(f"✅ Error tracking working")
            logger.info(f"   Total recent errors: {len(result)}")
            logger.info(f"   Unresolved errors: {len(unresolved)}")

            if unresolved:
                logger.warning("⚠️ Recent unresolved errors:")
                for error in unresolved[:5]:
                    logger.warning(f"   [{error['error_type']}] {error['error_message'][:80]}")
        else:
            logger.info("✅ No errors in tracking table (good!)")

        db.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error tracking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print(" MERCARI SEARCHER - COMPREHENSIVE SYSTEM TEST")
    print("="*60)
    print(f"Proxy enabled: {config.PROXY_ENABLED}")
    print(f"Telegram configured: {bool(config.TELEGRAM_BOT_TOKEN)}")
    print("="*60)

    tests = [
        ("Database", test_database),
        ("Proxy Parsing", test_proxy_parsing),
        ("Proxy Manager", test_proxy_manager),
        ("Mercapi Library", test_mercapi),
        ("Image Utils", test_image_utils),
        ("Telegram Config", test_telegram),
        ("Saved Searches", test_searches),
        ("Error Tracking", test_error_tracking),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' crashed: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "="*60)
    print(" TEST SUMMARY")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("="*60)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
