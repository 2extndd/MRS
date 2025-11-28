"""
Telegram Worker for MercariSearcher
Sends item notifications via Telegram bot using direct HTTP requests
Adapted from KufarSearcher with USD price display
"""

import logging
import requests
from typing import List, Dict, Any, Optional
import time

from configuration_values import config
from db import get_db
from shared_state import get_shared_state

logger = logging.getLogger(__name__)


class TelegramWorker:
    """Worker for sending Telegram notifications"""

    def __init__(self):
        """Initialize Telegram worker"""
        # Try to get from config (which hot-reloads from DB)
        # Force reload to get latest values from DB
        config.reload_if_needed()

        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.thread_id = config.TELEGRAM_THREAD_ID

        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram bot token and chat ID are required. Please set them in Web UI → Config")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.db = get_db()
        self.shared_state = get_shared_state()

        self.max_retries = 3
        self.retry_delay = 5

        logger.info("TelegramWorker initialized")

    def send_item_notification(self, item: Dict[str, Any]) -> bool:
        """
        Send notification for single item

        Args:
            item: Item dictionary from database

        Returns:
            True if sent successfully
        """
        item_id = None
        try:
            item_title = item.get('title', 'Unknown')[:40]
            item_id = item.get('id', 'NO_ID')
            logger.info(f"[TW] Sending notification for: {item_title}...")

            # Get thread_id from item's search or use global default
            thread_id = item.get('search_thread_id') or self.thread_id
            logger.debug(f"[TW] Using thread_id: {thread_id}")

            # Format message
            message = self._format_item_message(item)
            logger.debug(f"[TW] Message formatted ({len(message)} chars)")

            # Create inline keyboard
            keyboard = self._create_item_keyboard(item)

            # Get HIGH RESOLUTION photo for Telegram
            image_url = item.get('image_url')
            if image_url:
                try:
                    from image_handler import get_original_image_url
                    # Convert to highest quality available
                    image_url = get_original_image_url(image_url)
                    logger.debug(f"[TW] High-res image URL: {image_url[:80]}...")
                except Exception as img_error:
                    logger.warning(f"[TW] ⚠️  Error converting image URL: {img_error}, using original")
                    # Continue with original image_url

            # Send with photo if available
            if image_url:
                success = self._send_with_photo(
                    message=message,
                    photo_url=image_url,
                    keyboard=keyboard,
                    thread_id=thread_id
                )
            else:
                success = self._send_message(
                    message=message,
                    keyboard=keyboard,
                    thread_id=thread_id
                )

            if success:
                # NOTE: Item is already marked as sent in get_unsent_items() to prevent race conditions
                # We just update sent_at timestamp here
                item_id = item.get('id')
                if item_id:
                    try:
                        # Update sent_at timestamp (is_sent already True from get_unsent_items)
                        from db import get_moscow_time
                        query = "UPDATE items SET sent_at = %s WHERE id = %s"
                        self.db.execute_query(query, (get_moscow_time(), item_id))
                        logger.info(f"[TW] ✅ Updated sent_at for item {item_id}")
                    except Exception as db_error:
                        logger.warning(f"[TW] ⚠️  Failed to update sent_at for item {item_id}: {db_error}")
                        # Not critical - item was already marked as sent in get_unsent_items()
                else:
                    logger.error(f"[TW] ❌ CRITICAL: Item has no ID! Item: {item.get('title', 'Unknown')[:50]}")
                    logger.error(f"[TW] Item keys: {list(item.keys())}")
                    self.db.add_log_entry('ERROR', f'[TW.send] Item has no ID!', 'telegram')

                # Update stats
                try:
                    self.shared_state.increment('total_notifications_sent')
                    self.shared_state.set('last_telegram_send_time', time.time())
                except Exception as stats_error:
                    logger.warning(f"[TW] ⚠️  Failed to update stats: {stats_error}")

                logger.info(f"[TW] Notification sent for item: {item.get('title', 'Unknown')[:50]}")
            else:
                # If send FAILED, mark item as NOT sent so it will be retried
                item_id = item.get('id')
                if item_id:
                    try:
                        query = "UPDATE items SET is_sent = %s WHERE id = %s"
                        self.db.execute_query(query, (False, item_id))
                        logger.warning(f"[TW] ⚠️  Marked item {item_id} as unsent for retry")
                    except Exception as db_error:
                        logger.error(f"[TW] ❌ Failed to mark item {item_id} as unsent: {db_error}")
                        self.db.add_log_entry('ERROR', f'[TW.send] DB error {item_id}: {str(db_error)[:100]}', 'telegram')

            return success

        except Exception as e:
            logger.error(f"[TW] ❌ Failed to send notification for item {item_id}: {e}")
            import traceback
            logger.error(f"[TW] Traceback:\n{traceback.format_exc()}")
            self.db.add_log_entry('ERROR', f'[TW.send] Exception {item_id}: {str(e)[:100]}', 'telegram')
            # Log error to database
            try:
                self.db.log_error(f"Failed to send Telegram notification for item {item_id}: {str(e)}", 'telegram')
            except:
                pass  # Don't crash if DB logging fails
            return False

    def _format_item_message(self, item: Dict[str, Any]) -> str:
        """
        Format item message with USD price conversion - MINIMAL FORMAT

        Args:
            item: Item dictionary

        Returns:
            Formatted message string
        """
        # Title
        title = item.get('title', 'No title')

        # Price in JPY and USD
        price_jpy = item.get('price', 0)
        
        # Check if USD conversion rate is set
        usd_rate = config.USD_CONVERSION_RATE
        if usd_rate == 0 or usd_rate is None:
            logger.warning(f"USD_CONVERSION_RATE is {usd_rate}, using default 0.0067")
            usd_rate = 0.0067
        
        price_usd = round(price_jpy * usd_rate, 2)
        logger.debug(f"Price conversion: ¥{price_jpy} × {usd_rate} = ${price_usd}")

        # Build message - MINIMAL FORMAT
        lines = [
            f"<b>{title}</b>",
            "",
            f"💶: ${price_usd} (¥{price_jpy:,})"
        ]

        # Size (if available)
        if item.get('size'):
            lines.append(f"📏 Size: {item['size']}")

        # Search keyword
        if item.get('search_keyword'):
            lines.append(f"🔍: {item['search_keyword']}")

        return "\n".join(lines)

    def _create_item_keyboard(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create inline keyboard for item

        Args:
            item: Item dictionary

        Returns:
            Keyboard dictionary in Telegram API format
        """
        if not item.get('item_url'):
            return None

        return {
            "inline_keyboard": [
                [
                    {
                        "text": "🛒 View on Mercari",
                        "url": item['item_url']
                    }
                ]
            ]
        }

    def _send_with_photo(self, message: str, photo_url: str,
                         keyboard: Optional[Dict[str, Any]] = None,
                         thread_id: Optional[str] = None) -> bool:
        """
        Send message with photo

        Args:
            message: Message text
            photo_url: Photo URL
            keyboard: Optional inline keyboard
            thread_id: Optional thread ID for topic-based chats

        Returns:
            True if sent successfully
        """
        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}/sendPhoto"

                payload = {
                    "chat_id": self.chat_id,
                    "photo": photo_url,
                    "caption": message,
                    "parse_mode": "HTML"
                }

                if keyboard:
                    payload["reply_markup"] = keyboard

                # Use provided thread_id or fall back to instance thread_id
                if thread_id or self.thread_id:
                    payload["message_thread_id"] = thread_id or self.thread_id

                logger.info(f"[TW] Sending photo to Telegram (attempt {attempt+1}/{self.max_retries})...")
                response = requests.post(url, json=payload, timeout=30)

                if response.status_code == 200:
                    logger.info("[TW] ✅ Photo sent successfully")
                    return True
                else:
                    error_detail = f"Status {response.status_code}: {response.text[:150]}"
                    logger.warning(f"[TW] Telegram API returned {error_detail}")
                    self.db.add_log_entry('WARNING', f'[TW._send_photo] {error_detail}', 'telegram')

                    # If thread not found, try without thread_id
                    if response.status_code == 400 and "thread not found" in response.text:
                        if "message_thread_id" in payload:
                            logger.info("[TW] Thread not found, retrying without thread_id...")
                            payload.pop("message_thread_id")
                            response = requests.post(url, json=payload, timeout=30)
                            if response.status_code == 200:
                                logger.info("[TW] ✅ Photo sent successfully (without thread)")
                                return True

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.json().get('parameters', {}).get('retry_after', self.retry_delay)
                    logger.warning(f"Rate limit hit, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                logger.warning(f"Failed to send photo (attempt {attempt + 1}/{self.max_retries}): {response.status_code} - {response.text[:200]}")
                # Log to database on final attempt
                if attempt == self.max_retries - 1:
                    self.db.log_error(f"Failed to send photo after {self.max_retries} attempts: {response.status_code}", 'telegram_photo')

            except Exception as e:
                logger.warning(f"Failed to send photo (attempt {attempt + 1}/{self.max_retries}): {e}")
                # Log to database on final attempt
                if attempt == self.max_retries - 1:
                    self.db.log_error(f"Failed to send photo: {str(e)}", 'telegram_photo')

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
            else:
                # Fall back to text message
                logger.info("Falling back to text message")
                return self._send_message(message, keyboard, thread_id)

        return False

    def _send_message(self, message: str,
                      keyboard: Optional[Dict[str, Any]] = None,
                      thread_id: Optional[str] = None) -> bool:
        """
        Send text message

        Args:
            message: Message text
            keyboard: Optional inline keyboard
            thread_id: Optional thread ID for topic-based chats

        Returns:
            True if sent successfully
        """
        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}/sendMessage"

                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }

                if keyboard:
                    payload["reply_markup"] = keyboard

                # Use provided thread_id or fall back to instance thread_id
                if thread_id or self.thread_id:
                    payload["message_thread_id"] = thread_id or self.thread_id

                response = requests.post(url, json=payload, timeout=30)

                if response.status_code == 200:
                    return True

                # If thread not found, try without thread_id
                if response.status_code == 400 and "thread not found" in response.text:
                    if "message_thread_id" in payload:
                        logger.info("[TW] Thread not found, retrying without thread_id...")
                        payload.pop("message_thread_id")
                        response = requests.post(url, json=payload, timeout=30)
                        if response.status_code == 200:
                            logger.info("[TW] ✅ Message sent successfully (without thread)")
                            return True

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.json().get('parameters', {}).get('retry_after', self.retry_delay)
                    logger.warning(f"Rate limit hit, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                logger.warning(f"Failed to send message (attempt {attempt + 1}/{self.max_retries}): {response.status_code} - {response.text[:200]}")

            except Exception as e:
                logger.warning(f"Failed to send message (attempt {attempt + 1}/{self.max_retries}): {e}")

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        return False

    def send_system_message(self, message: str) -> bool:
        """
        Send system/status message

        Args:
            message: Message text

        Returns:
            True if sent successfully
        """
        try:
            formatted_message = f"🤖 <b>MercariSearcher</b>\n\n{message}"

            url = f"{self.base_url}/sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": formatted_message,
                "parse_mode": "HTML"
            }

            if self.thread_id:
                payload["message_thread_id"] = self.thread_id

            response = requests.post(url, json=payload, timeout=30)

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Failed to send system message: {e}")
            return False

    def process_pending_notifications(self, max_items: int = 35) -> Dict[str, int]:
        """
        Process pending notifications from database - LIMITED to avoid blocking

        Args:
            max_items: Maximum items to process per cycle (default 35)

        Returns:
            Dictionary with processing statistics
        """
        logger.info(f"[TW] Processing pending notifications (max {max_items})...")

        stats = {
            'total': 0,
            'sent': 0,
            'failed': 0,
            'errors': []
        }

        try:
            # Get unsent items - LIMITED
            unsent_items = self.db.get_unsent_items(limit=max_items)

            stats['total'] = len(unsent_items)

            if not unsent_items:
                logger.info("[TW] No pending notifications (all items sent or no items in DB)")
                return stats

            logger.info(f"[TW] Found {len(unsent_items)} unsent items, processing...")

            for index, item in enumerate(unsent_items):
                try:
                    item_id = item.get('id', 'UNKNOWN')
                    item_title = item.get('title', 'No title')[:40]
                    logger.info(f"[TW] Processing item {index+1}/{len(unsent_items)}: ID={item_id}")

                    success = self.send_item_notification(item)

                    if success:
                        stats['sent'] += 1
                    else:
                        stats['failed'] += 1
                        error_msg = f"Failed to send item {item_id}: {item_title}"
                        stats['errors'].append(error_msg)
                        logger.warning(f"[TW] ❌ {error_msg}")

                    # Rate limiting between messages (0.5s = 2 items/sec)
                    time.sleep(0.5)

                except Exception as item_error:
                    stats['failed'] += 1
                    error_msg = f"Exception processing item {item.get('id', 'UNKNOWN')}: {str(item_error)[:100]}"
                    stats['errors'].append(error_msg)
                    logger.error(f"[TW] ❌ {error_msg}")
                    self.db.add_log_entry('ERROR', f'[TW.process] {error_msg}', 'telegram')
                    # Continue with next item instead of crashing
                    continue

            logger.info(f"[TW] ✅ Processed {stats['sent']}/{stats['total']} notifications")
            if stats['failed'] > 0:
                logger.warning(f"[TW] ⚠️  Failed: {stats['failed']}")
                for error in stats['errors'][:5]:  # Log first 5 errors
                    logger.warning(f"[TW]    - {error}")

        except Exception as e:
            error_msg = f"CRITICAL ERROR in process_pending_notifications: {str(e)}"
            logger.error(f"[TW] ❌ {error_msg}")
            import traceback
            logger.error(f"[TW] Traceback:\n{traceback.format_exc()}")
            self.db.add_log_entry('ERROR', f'[TW.process] CRITICAL: {error_msg[:200]}', 'telegram')
            stats['errors'].append(error_msg)

        return stats


# Synchronous wrapper functions
def send_notification_for_item(item: Dict[str, Any]) -> bool:
    """
    Send notification for single item

    Args:
        item: Item dictionary

    Returns:
        True if sent successfully
    """
    worker = TelegramWorker()
    return worker.send_item_notification(item)


def send_notifications(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Send multiple notifications

    Args:
        items: List of item dictionaries

    Returns:
        Dictionary with statistics
    """
    worker = TelegramWorker()

    stats = {
        'total': len(items),
        'sent': 0,
        'failed': 0
    }

    for item in items:
        success = worker.send_item_notification(item)

        if success:
            stats['sent'] += 1
        else:
            stats['failed'] += 1

        time.sleep(1)  # Rate limiting

    return stats


def process_pending_notifications(max_items: int = 35) -> Dict[str, int]:
    """
    Process pending notifications from database

    Args:
        max_items: Maximum items to process per cycle (default 35)

    Returns:
        Dictionary with statistics
    """
    try:
        logger.info("[TW] Creating TelegramWorker instance...")
        worker = TelegramWorker()
        logger.info("[TW] TelegramWorker created successfully")
        result = worker.process_pending_notifications(max_items=max_items)
        # Only log if there were items to send
        if result.get('total', 0) > 0:
            logger.info(f"[TW] Sent {result['sent']}/{result['total']} items")
        return result
    except Exception as e:
        logger.error(f"[TW] Failed to create TelegramWorker: {e}")
        import traceback
        error_msg = f"[TW] Failed: {e}\n{traceback.format_exc()}"
        logger.error(f"[TW] Traceback:\n{traceback.format_exc()}")
        from db import get_db
        get_db().add_log_entry('ERROR', error_msg[:500], 'telegram')
        return {'total': 0, 'sent': 0, 'failed': 0}


def send_system_message(message: str) -> bool:
    """
    Send system message

    Args:
        message: Message text

    Returns:
        True if sent successfully
    """
    worker = TelegramWorker()
    return worker.send_system_message(message)


if __name__ == "__main__":
    # Test Telegram worker
    logging.basicConfig(level=logging.INFO)

    # Test item
    test_item = {
        'id': 1,
        'title': 'Nike Air Max 90 - White/Black',
        'price': 15000,
        'brand': 'Nike',
        'condition': 'Used - Good',
        'size': 'US 10',
        'shipping_cost': 700,
        'seller_name': 'TestSeller',
        'seller_rating': 4.8,
        'location': 'Tokyo',
        'category': 'Shoes',
        'item_url': 'https://jp.mercari.com/item/test123',
        'image_url': 'https://static.mercdn.net/item/detail/orig/photos/test.jpg',
        'search_keyword': 'Nike Air Max'
    }

    print("Test message format:")
    worker = TelegramWorker()
    message = worker._format_item_message(test_item)
    print(message)

    # Uncomment to actually send test notification
    # result = send_notification_for_item(test_item)
    # print(f"\nSent: {result}")
