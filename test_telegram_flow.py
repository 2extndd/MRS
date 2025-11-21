#!/usr/bin/env python3
"""
Diagnostic script to test complete Telegram notification flow
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db
from configuration_values import config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("=" * 80)
    print("TELEGRAM NOTIFICATION FLOW DIAGNOSTIC")
    print("=" * 80)

    db = get_db()

    # STEP 1: Check Telegram config
    print("\n📋 STEP 1: Checking Telegram Configuration")
    print("-" * 80)

    # Force reload from DB
    config.reload_if_needed()

    bot_token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    thread_id = config.TELEGRAM_THREAD_ID

    print(f"BOT_TOKEN: {'✅ SET' if bot_token else '❌ NOT SET'} (length: {len(bot_token) if bot_token else 0})")
    print(f"CHAT_ID: {'✅ SET' if chat_id else '❌ NOT SET'} ({chat_id if chat_id else 'None'})")
    print(f"THREAD_ID: {'✅ SET' if thread_id else '⚠️  NOT SET (optional)'} ({thread_id if thread_id else 'None'})")

    if not bot_token or not chat_id:
        print("\n❌ ERROR: Bot token or chat ID not configured!")
        print("Please set them in Web UI → Config")
        return

    # STEP 2: Check unsent items
    print("\n📦 STEP 2: Checking Unsent Items in Database")
    print("-" * 80)

    unsent_items = db.get_unsent_items(limit=100)
    print(f"Total unsent items: {len(unsent_items)}")

    if len(unsent_items) == 0:
        print("⚠️  No unsent items found. Adding test items or checking if all items already sent.")

        # Check total items
        all_items = db.execute_query("SELECT COUNT(*) as count FROM items", fetch=True)
        total_items = all_items[0]['count'] if all_items else 0

        sent_items = db.execute_query("SELECT COUNT(*) as count FROM items WHERE is_sent = %s", (True,), fetch=True)
        total_sent = sent_items[0]['count'] if sent_items else 0

        print(f"Total items in DB: {total_items}")
        print(f"Already sent: {total_sent}")
        print(f"Pending: {total_items - total_sent}")

        if total_items == 0:
            print("\n⚠️  No items in database at all! Run a search first.")
            return
        elif total_items == total_sent:
            print("\n✅ All items already sent to Telegram!")
            return
    else:
        print("\n📋 First 5 unsent items:")
        for i, item in enumerate(unsent_items[:5]):
            print(f"\n  {i+1}. {item.get('title', 'No title')[:60]}")
            print(f"     ID: {item.get('id')}")
            print(f"     Mercari ID: {item.get('mercari_id')}")
            print(f"     Price: ¥{item.get('price')}")
            print(f"     Found at: {item.get('found_at')}")
            print(f"     Search keyword: {item.get('search_keyword', 'N/A')}")
            print(f"     Thread ID: {item.get('search_thread_id', 'N/A')}")
            print(f"     Has image: {'✅' if item.get('image_url') else '❌'}")

    # STEP 3: Test TelegramWorker initialization
    print("\n🤖 STEP 3: Testing TelegramWorker Initialization")
    print("-" * 80)

    try:
        from simple_telegram_worker import TelegramWorker
        worker = TelegramWorker()
        print("✅ TelegramWorker initialized successfully")
        print(f"   Base URL: {worker.base_url[:50]}...")
        print(f"   Chat ID: {worker.chat_id}")
        print(f"   Thread ID: {worker.thread_id}")
    except Exception as e:
        print(f"❌ Failed to initialize TelegramWorker: {e}")
        import traceback
        traceback.print_exc()
        return

    # STEP 4: Test sending one notification
    print("\n📤 STEP 4: Testing Send Notification (DRY RUN)")
    print("-" * 80)

    if len(unsent_items) > 0:
        test_item = unsent_items[0]
        print(f"Testing with item: {test_item.get('title', 'No title')[:60]}")
        print(f"Item ID: {test_item.get('id')}")
        print(f"Mercari ID: {test_item.get('mercari_id')}")

        # Format message (without sending)
        try:
            message = worker._format_item_message(test_item)
            print("\n📝 Formatted message:")
            print("-" * 40)
            print(message)
            print("-" * 40)
        except Exception as e:
            print(f"❌ Failed to format message: {e}")
            import traceback
            traceback.print_exc()

        # Check image URL
        image_url = test_item.get('image_url')
        if image_url:
            print(f"\n🖼️  Image URL: {image_url[:80]}...")
            try:
                from image_handler import get_original_image_url
                high_res_url = get_original_image_url(image_url)
                print(f"   High-res URL: {high_res_url[:80]}...")
            except Exception as e:
                print(f"   ⚠️  Error getting high-res URL: {e}")
        else:
            print("\n⚠️  No image URL for this item")

    # STEP 5: Check scheduler status
    print("\n⏰ STEP 5: Checking Scheduler Configuration")
    print("-" * 80)

    search_interval = config.SEARCH_INTERVAL
    print(f"Search cycle interval: {search_interval} seconds")
    print(f"Telegram cycle interval: 10 seconds (hardcoded)")

    # STEP 6: Test actual send (optional - ask user)
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

    if len(unsent_items) > 0:
        print(f"\n✅ Found {len(unsent_items)} unsent items ready to send")
        print("✅ Telegram configuration is valid")
        print("\nNext steps:")
        print("1. Check Railway logs for '[TELEGRAM] Processing pending notifications...'")
        print("2. Check for any errors in logs")
        print("3. Verify telegram_cycle is being called every 10 seconds")

        response = input("\n⚠️  Do you want to test sending ONE notification to Telegram? (yes/no): ")
        if response.lower() == 'yes':
            print("\n📤 Sending test notification...")
            try:
                success = worker.send_item_notification(test_item)
                if success:
                    print("✅ Notification sent successfully!")
                    print("   Check your Telegram to verify")
                else:
                    print("❌ Failed to send notification (check logs above)")
            except Exception as e:
                print(f"❌ Error sending notification: {e}")
                import traceback
                traceback.print_exc()
    else:
        print("\n⚠️  No unsent items to send")
        print("Either all items are sent, or no items found yet")

if __name__ == "__main__":
    main()
