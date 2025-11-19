#!/usr/bin/env python3
"""
Railway Deployment Test Script
Run this on Railway to verify the bot is working correctly
Usage: python3 railway_test_deployment.py
"""

import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("\n" + "="*80)
print(" RAILWAY DEPLOYMENT TEST")
print("="*80 + "\n")


def test_environment():
    """Test 1: Check environment configuration"""
    print("\n" + "="*80)
    print("TEST 1: Environment Configuration")
    print("="*80 + "\n")
    
    import os
    
    required_vars = [
        'DATABASE_URL',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID',
    ]
    
    optional_vars = [
        'TELEGRAM_THREAD_ID',
        'PROXY_ENABLED',
    ]
    
    all_ok = True
    
    print("Required Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive data
            if 'TOKEN' in var or 'URL' in var:
                display = value[:20] + "..." if len(value) > 20 else value
            else:
                display = value
            print(f"  ✅ {var}: {display}")
        else:
            print(f"  ❌ {var}: NOT SET")
            all_ok = False
    
    print("\nOptional Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚠️  {var}: Not set (using default)")
    
    return all_ok


def test_database():
    """Test 2: Database connection"""
    print("\n" + "="*80)
    print("TEST 2: Database Connection")
    print("="*80 + "\n")
    
    try:
        from db import get_db
        
        db = get_db()
        print("✅ Database connection initialized")
        
        # Test query
        searches = db.get_active_searches()
        print(f"✅ Active searches: {len(searches)}")
        
        if searches:
            for search in searches[:3]:
                print(f"   - {search.get('name', 'Unknown')} (ID: {search['id']})")
        
        # Check items
        import psycopg2
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items")
        count = cursor.fetchone()[0]
        print(f"✅ Total items in database: {count}")
        
        # Check items with images
        cursor.execute("SELECT COUNT(*) FROM items WHERE image_data IS NOT NULL")
        image_count = cursor.fetchone()[0]
        print(f"✅ Items with high-res images: {image_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mercapi():
    """Test 3: mercapi library"""
    print("\n" + "="*80)
    print("TEST 3: mercapi Library")
    print("="*80 + "\n")
    
    try:
        import asyncio
        from mercapi import Mercapi
        
        print("✅ mercapi imported successfully")
        
        # Test simple search
        async def test_search():
            api = Mercapi()
            results = await api.search(query="test")
            return len(results.items)
        
        count = asyncio.run(test_search())
        print(f"✅ Search test successful: found {count} items")
        
        return True
        
    except Exception as e:
        print(f"❌ mercapi test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_handler():
    """Test 4: Image download"""
    print("\n" + "="*80)
    print("TEST 4: Image Handler")
    print("="*80 + "\n")
    
    try:
        from image_handler import get_original_image_url, download_and_encode_image
        
        # Test URL conversion
        test_url = "https://static.mercdn.net/c!/w=240,f=webp/thumb/photos/m18043642062_1.jpg"
        high_res = get_original_image_url(test_url)
        
        print(f"✅ URL conversion working")
        print(f"   Input:  {test_url[:60]}...")
        print(f"   Output: {high_res[:60]}...")
        
        if '/orig/' in high_res or 'w_1200' in high_res:
            print(f"✅ URL converted to high-resolution format")
        else:
            print(f"⚠️  URL may not be high-resolution")
        
        # Test download (quick test with small image)
        print(f"\n📥 Testing image download...")
        image_data = download_and_encode_image(high_res, timeout=10, use_proxy=False)
        
        if image_data:
            size_kb = len(image_data) / 1024
            print(f"✅ Image download successful: {size_kb:.1f}KB base64")
            return True
        else:
            print(f"❌ Image download failed")
            return False
        
    except Exception as e:
        print(f"❌ Image handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_telegram():
    """Test 5: Telegram connection"""
    print("\n" + "="*80)
    print("TEST 5: Telegram Connection")
    print("="*80 + "\n")
    
    try:
        from simple_telegram_worker import send_system_message
        
        message = (
            f"🧪 Deployment Test\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Status: Testing bot deployment"
        )
        
        success = send_system_message(message)
        
        if success:
            print(f"✅ Telegram message sent successfully")
            return True
        else:
            print(f"❌ Telegram message failed")
            return False
        
    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bot_cycle():
    """Test 6: Full bot cycle"""
    print("\n" + "="*80)
    print("TEST 6: Full Bot Search Cycle")
    print("="*80 + "\n")
    
    try:
        from core import MercariSearcher
        
        searcher = MercariSearcher(use_proxy=False)
        print("✅ MercariSearcher initialized")
        
        # Run one search cycle
        print("\n🔍 Running search cycle...")
        results = searcher.search_all_queries()
        
        print(f"\n📊 Search Results:")
        print(f"   Total searches: {results['total_searches']}")
        print(f"   Successful: {results['successful_searches']}")
        print(f"   Failed: {results['failed_searches']}")
        print(f"   Items found: {results['total_items_found']}")
        print(f"   New items: {results['new_items']}")
        print(f"   Duration: {results['duration']:.2f}s")
        
        if results['successful_searches'] > 0:
            print(f"\n✅ Bot search cycle working!")
            return True
        else:
            print(f"\n⚠️  No searches were successful")
            return False
        
    except Exception as e:
        print(f"❌ Bot cycle test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print(f"\n🚀 Starting deployment tests...\n")
    
    tests = [
        ("Environment", test_environment),
        ("Database", test_database),
        ("mercapi", test_mercapi),
        ("Image Handler", test_image_handler),
        ("Telegram", test_telegram),
        ("Bot Cycle", test_bot_cycle),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print(" TEST SUMMARY")
    print("="*80 + "\n")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    passed_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    print(f"\n📊 Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! Bot is ready!")
        return 0
    elif passed_count >= total_count - 1:
        print("\n⚠️  Almost ready - check failed tests")
        return 1
    else:
        print("\n❌ Multiple tests failed - check configuration")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Tests crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
