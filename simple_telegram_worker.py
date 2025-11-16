"""
Telegram Worker for MercariSearcher
Sends item notifications via Telegram bot
Adapted from KufarSearcher with USD price display
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, RetryAfter, TimedOut
from telegram.constants import ParseMode
import time

from configuration_values import config
from db import get_db
from shared_state import get_shared_state

logger = logging.getLogger(__name__)


class TelegramWorker:
    """Worker for sending Telegram notifications"""

    def __init__(self):
        """Initialize Telegram worker"""
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.thread_id = config.TELEGRAM_THREAD_ID

        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram bot token and chat ID are required")

        self.bot = Bot(token=self.bot_token)
        self.db = get_db()
        self.shared_state = get_shared_state()

        self.max_retries = 3
        self.retry_delay = 5

        logger.info("TelegramWorker initialized")

    async def send_item_notification(self, item: Dict[str, Any]) -> bool:
        """
        Send notification for single item

        Args:
            item: Item dictionary from database

        Returns:
            True if sent successfully
        """
        try:
            # Format message
            message = self._format_item_message(item)

            # Create inline keyboard
            keyboard = self._create_item_keyboard(item)

            # Send with photo if available
            if item.get('image_url'):
                await self._send_with_photo(
                    message=message,
                    photo_url=item['image_url'],
                    keyboard=keyboard
                )
            else:
                await self._send_message(
                    message=message,
                    keyboard=keyboard
                )

            # Mark as sent in database
            if item.get('id'):
                self.db.mark_item_sent(item['id'])

            # Update stats
            self.shared_state.increment('total_notifications_sent')
            self.shared_state.set('last_telegram_send_time', time.time())

            logger.info(f"Notification sent for item: {item.get('title', 'Unknown')[:50]}")

            return True

        except RetryAfter as e:
            logger.warning(f"Rate limit hit, waiting {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            return False

        except TimedOut:
            logger.warning("Telegram request timed out")
            return False

        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            return False

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def _format_item_message(self, item: Dict[str, Any]) -> str:
        """
        Format item message with USD price conversion

        Args:
            item: Item dictionary

        Returns:
            Formatted message string
        """
        # Title
        title = item.get('title', 'No title')

        # Price in JPY and USD
        price_jpy = item.get('price', 0)
        price_usd = round(price_jpy * config.USD_CONVERSION_RATE, 2)

        # Format price text
        if config.DISPLAY_CURRENCY == 'USD':
            price_text = f"${price_usd} (¥{price_jpy:,})"
        else:
            price_text = f"¥{price_jpy:,} (${price_usd})"

        # Build message
        lines = [
            f"<b>{title}</b>",
            "",
            f"💴 <b>Price:</b> {price_text}"
        ]

        # Brand
        if item.get('brand'):
            lines.append(f"👔 <b>Brand:</b> {item['brand']}")

        # Condition
        if item.get('condition'):
            lines.append(f"✨ <b>Condition:</b> {item['condition']}")

        # Size
        if item.get('size'):
            lines.append(f"📏 <b>Size:</b> {item['size']}")

        # Shipping cost
        if item.get('shipping_cost'):
            shipping_jpy = item['shipping_cost']
            shipping_usd = round(shipping_jpy * config.USD_CONVERSION_RATE, 2)
            lines.append(f"📦 <b>Shipping:</b> ¥{shipping_jpy:,} (${shipping_usd})")

        # Seller
        if item.get('seller_name'):
            seller_text = item['seller_name']
            if item.get('seller_rating'):
                seller_text += f" ({item['seller_rating']}⭐)"
            lines.append(f"👤 <b>Seller:</b> {seller_text}")

        # Location
        if item.get('location'):
            lines.append(f"📍 <b>Location:</b> {item['location']}")

        # Category
        if item.get('category'):
            lines.append(f"🏷 <b>Category:</b> {item['category']}")

        # Search keyword
        if item.get('search_keyword'):
            lines.append(f"🔍 <b>Search:</b> {item['search_keyword']}")

        return "\n".join(lines)

    def _create_item_keyboard(self, item: Dict[str, Any]) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for item

        Args:
            item: Item dictionary

        Returns:
            InlineKeyboardMarkup
        """
        buttons = []

        # View on Mercari button
        if item.get('item_url'):
            buttons.append([
                InlineKeyboardButton(
                    text="🛒 View on Mercari",
                    url=item['item_url']
                )
            ])

        return InlineKeyboardMarkup(buttons)

    async def _send_with_photo(self, message: str, photo_url: str,
                               keyboard: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Send message with photo

        Args:
            message: Message text
            photo_url: Photo URL
            keyboard: Optional inline keyboard

        Returns:
            True if sent successfully
        """
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo_url,
                    caption=message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    message_thread_id=self.thread_id if self.thread_id else None
                )
                return True

            except Exception as e:
                logger.warning(f"Failed to send photo (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    # Fall back to text message
                    logger.info("Falling back to text message")
                    return await self._send_message(message, keyboard)

        return False

    async def _send_message(self, message: str,
                           keyboard: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Send text message

        Args:
            message: Message text
            keyboard: Optional inline keyboard

        Returns:
            True if sent successfully
        """
        for attempt in range(self.max_retries):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                    message_thread_id=self.thread_id if self.thread_id else None
                )
                return True

            except Exception as e:
                logger.warning(f"Failed to send message (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)

        return False

    async def send_system_message(self, message: str) -> bool:
        """
        Send system/status message

        Args:
            message: Message text

        Returns:
            True if sent successfully
        """
        try:
            formatted_message = f"🤖 <b>MercariSearcher</b>\n\n{message}"

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted_message,
                parse_mode=ParseMode.HTML,
                message_thread_id=self.thread_id if self.thread_id else None
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send system message: {e}")
            return False

    async def process_pending_notifications(self) -> Dict[str, int]:
        """
        Process all pending notifications from database

        Returns:
            Dictionary with processing statistics
        """
        logger.info("Processing pending notifications...")

        # Get unsent items
        unsent_items = self.db.get_unsent_items()

        stats = {
            'total': len(unsent_items),
            'sent': 0,
            'failed': 0
        }

        if not unsent_items:
            logger.info("No pending notifications")
            return stats

        logger.info(f"Found {len(unsent_items)} pending notifications")

        for item in unsent_items:
            success = await self.send_item_notification(item)

            if success:
                stats['sent'] += 1
            else:
                stats['failed'] += 1

            # Rate limiting between messages
            await asyncio.sleep(1)

        logger.info(f"Processed {stats['sent']}/{stats['total']} notifications")

        return stats


# Synchronous wrapper functions
def send_notification_for_item(item: Dict[str, Any]) -> bool:
    """
    Synchronous wrapper for sending item notification

    Args:
        item: Item dictionary

    Returns:
        True if sent successfully
    """
    worker = TelegramWorker()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(worker.send_item_notification(item))


def send_notifications(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Synchronous wrapper for sending multiple notifications

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

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    for item in items:
        success = loop.run_until_complete(worker.send_item_notification(item))

        if success:
            stats['sent'] += 1
        else:
            stats['failed'] += 1

        time.sleep(1)  # Rate limiting

    return stats


def process_pending_notifications() -> Dict[str, int]:
    """
    Synchronous wrapper for processing pending notifications

    Returns:
        Dictionary with statistics
    """
    worker = TelegramWorker()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(worker.process_pending_notifications())


def send_system_message(message: str) -> bool:
    """
    Synchronous wrapper for sending system message

    Args:
        message: Message text

    Returns:
        True if sent successfully
    """
    worker = TelegramWorker()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(worker.send_system_message(message))


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
