"""
Main Mercari API wrapper class using mercapi library
"""

import time
import random
import logging
import asyncio
from typing import Optional, Dict, Any, List
from .items import Item, Items
from .exceptions import (
    MercariAPIError,
    MercariConnectionError,
    MercariRateLimitError,
    MercariParseError
)

logger = logging.getLogger(__name__)


class Mercari:
    """
    Mercari API wrapper using mercapi library
    Compatible interface with pyKufarVN
    """

    def __init__(self, proxy: Optional[str] = None, scraper=None):
        """
        Initialize Mercari API wrapper

        Args:
            proxy: Proxy URL (e.g., 'http://proxy:port') - NOT USED (mercapi doesn't support proxies yet)
            scraper: Custom scraper instance (for dependency injection)
        """
        self.proxy = proxy
        self.scraper = scraper
        self.request_count = 0
        self.last_request_time = 0

        # Rate limiting settings
        self.min_delay = 1.5
        self.max_delay = 3.5
        
        # Shared event loop for all async operations
        self._loop = None

        # Initialize mercapi
        if not self.scraper:
            try:
                from mercapi import Mercapi
                # mercapi is async, we'll create instance when needed
                self._mercapi_class = Mercapi
                self._mercapi = None
            except ImportError as e:
                logger.error(f"mercapi library not installed: {e}")
                raise MercariConnectionError("mercapi library required. Install with: pip install mercapi")

        if proxy:
            logger.warning("Proxy support not available with mercapi library")

        logger.info(f"Mercari API initialized (using mercapi library)")

    def _get_mercapi(self):
        """Get or create mercapi instance"""
        if self._mercapi is None:
            self._mercapi = self._mercapi_class()
        return self._mercapi
    
    def _get_or_create_loop(self):
        """Get existing event loop or create new one"""
        if self._loop is None or self._loop.is_closed():
            try:
                # Try to get running loop
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create new one
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _run_async(self, coro):
        """Run async coroutine safely"""
        loop = self._get_or_create_loop()
        
        # Check if loop is already running (e.g., in Flask with async context)
        try:
            if loop.is_running():
                # Create a new loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                # Run in existing loop
                return loop.run_until_complete(coro)
        except Exception as e:
            # Last resort: try asyncio.run with fresh loop
            logger.warning(f"Event loop issue, creating fresh loop: {e}")
            return asyncio.run(coro)

    def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_delay:
            delay = random.uniform(self.min_delay, self.max_delay)
            time.sleep(delay)

        self.last_request_time = time.time()
        self.request_count += 1

    def change_proxy(self, new_proxy: Optional[str] = None):
        """
        Change proxy for scraper

        Args:
            new_proxy: New proxy URL or None to disable

        Note: mercapi doesn't support proxies yet
        """
        self.proxy = new_proxy
        if new_proxy:
            logger.warning("Proxy support not available with mercapi library")

    def test_connection(self) -> bool:
        """
        Test connection to Mercari

        Returns:
            True if connection successful
        """
        try:
            # Try a simple search to test connection
            async def _test():
                m = self._get_mercapi()
                # Search for common keyword
                result = await m.search('test')
                return result is not None

            return self._run_async(_test())
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def search(self, search_url: str, limit: int = 50) -> Items:
        """
        Search for items on Mercari

        Args:
            search_url: Full Mercari search URL or keyword
            limit: Maximum number of items to return

        Returns:
            Items object containing search results

        Raises:
            MercariConnectionError: If connection fails
            MercariParseError: If parsing fails
        """
        try:
            self._rate_limit()

            logger.info(f"Searching Mercari: {search_url[:80]}...")

            # Extract keyword from URL if it's a full URL
            keyword = self._extract_keyword_from_url(search_url)

            # Run async search in sync context with proper event loop handling
            async def _perform_search():
                m = self._get_mercapi()
                results = await m.search(keyword)

                # Convert mercapi results to our Items format
                items_data = []
                item_count = 0

                for item in results.items:
                    if item_count >= limit:
                        break

                    # Get item attributes
                    item_id = getattr(item, 'id_', None)
                    if not item_id:
                        continue

                    # Build item data dict
                    item_dict = {
                        'mercari_id': item_id,
                        'title': getattr(item, 'name', ''),
                        'price': getattr(item, 'price', 0),
                        'currency': 'JPY',
                        'item_url': f"https://jp.mercari.com/item/{item_id}",
                        'image_url': None,
                        'brand': None,
                        'condition': None,
                        'size': None,
                        'shipping_cost': 0,
                        'stock_quantity': 1,
                        'seller_name': None,
                        'seller_rating': None,
                        'location': None,
                        'category': None,
                        'description': ''
                    }

                    # Get best available image
                    # mercapi structure: item might have photos array or thumbnail string
                    photos = getattr(item, 'photos', [])
                    thumbnails = getattr(item, 'thumbnails', [])
                    thumbnail = getattr(item, 'thumbnail', None)
                    
                    # Try to get highest quality image
                    if photos and len(photos) > 0:
                        # photos array - use first photo (usually highest quality)
                        item_dict['image_url'] = photos[0]
                    elif thumbnail:
                        # Single thumbnail string - often higher quality than thumbnails array
                        item_dict['image_url'] = thumbnail
                    elif thumbnails and len(thumbnails) > 0:
                        # thumbnails array - fallback
                        item_dict['image_url'] = thumbnails[0]
                    
                    # Log what we got for debugging
                    if not item_dict['image_url']:
                        logger.debug(f"No image for item {item_id}: photos={bool(photos)}, thumbnail={bool(thumbnail)}, thumbnails={bool(thumbnails)}")

                    items_data.append(item_dict)
                    item_count += 1

                return items_data

            # Execute async search with shared event loop
            items_data = self._run_async(_perform_search())

            # Convert to Items object
            items = Items(items_data)
            logger.info(f"Found {len(items)} items")

            return items

        except MercariConnectionError:
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise MercariAPIError(f"Search error: {e}")

    def _extract_keyword_from_url(self, search_url: str) -> str:
        """
        Extract keyword from Mercari search URL

        Args:
            search_url: Full URL or keyword

        Returns:
            Keyword string
        """
        # If it's not a URL, return as is
        if not search_url.startswith('http'):
            return search_url

        # Parse URL to extract keyword parameter
        from urllib.parse import urlparse, parse_qs

        try:
            parsed = urlparse(search_url)
            params = parse_qs(parsed.query)

            # Get keyword parameter
            keyword = params.get('keyword', [''])[0]

            if keyword:
                return keyword.strip()

            # If no keyword, use empty search (will return popular items)
            logger.warning(f"No keyword found in URL: {search_url}")
            return ""

        except Exception as e:
            logger.error(f"Failed to parse URL: {e}")
            return ""

    def get_item(self, item_url: str) -> Optional[Item]:
        """
        Get detailed information for a specific item

        Args:
            item_url: Full Mercari item URL or item ID

        Returns:
            Item object or None if not found
        """
        try:
            self._rate_limit()

            # Extract item ID from URL
            item_id = item_url
            if '/item/' in item_url:
                item_id = item_url.split('/item/')[-1].split('?')[0]

            logger.info(f"Getting item details: {item_id}")

            # Run async in sync context with shared event loop
            async def _get_item():
                m = self._get_mercapi()
                return await m.item(item_id)

            full_item = self._run_async(_get_item())

            if not full_item:
                return None

            # Convert to our Item format
            item_data = {
                'mercari_id': item_id,
                'title': getattr(full_item, 'name', ''),
                'price': getattr(full_item, 'price', 0),
                'currency': 'JPY',
                'item_url': f"https://jp.mercari.com/item/{item_id}",
                'image_url': None,
                'description': getattr(full_item, 'description', ''),
                'brand': None,
                'condition': None,
                'size': None,
                'shipping_cost': 0,
                'stock_quantity': 1,
                'seller_name': None,
                'seller_rating': None,
                'location': None,
                'category': None
            }

            # Get photos
            if hasattr(full_item, 'photos') and full_item.photos:
                item_data['image_url'] = full_item.photos[0]

            # Item condition
            if hasattr(full_item, 'item_condition') and full_item.item_condition:
                if hasattr(full_item.item_condition, 'name'):
                    item_data['condition'] = full_item.item_condition.name

            # Category
            if hasattr(full_item, 'item_category') and full_item.item_category:
                if hasattr(full_item.item_category, 'name'):
                    item_data['category'] = full_item.item_category.name

            # Seller
            if hasattr(full_item, 'seller') and full_item.seller:
                item_data['seller_name'] = getattr(full_item.seller, 'name', None)
                item_data['seller_rating'] = getattr(full_item.seller, 'rating', None)

            return Item(item_data)

        except Exception as e:
            logger.error(f"Failed to get item: {e}")
            return None

    def build_search_url(self, **params) -> str:
        """
        Build Mercari search URL from parameters

        Args:
            keyword: Search keyword
            category_id: Category ID
            brand: Brand name
            min_price: Minimum price (JPY)
            max_price: Maximum price (JPY)
            condition: Item condition
            size: Item size
            color: Item color
            sort: Sort order (created_desc, price_asc, price_desc)

        Returns:
            Full search URL
        """
        from configuration_values import config
        from urllib.parse import urlencode

        base_url = f"{config.MERCARI_BASE_URL}/search"

        # Build query parameters
        query_params = {}

        if params.get('keyword'):
            query_params['keyword'] = params['keyword']

        if params.get('category_id'):
            query_params['category_id'] = params['category_id']

        if params.get('brand'):
            query_params['brand'] = params['brand']

        if params.get('min_price'):
            query_params['price_min'] = params['min_price']

        if params.get('max_price'):
            query_params['price_max'] = params['max_price']

        if params.get('condition'):
            query_params['item_condition_id'] = params['condition']

        if params.get('size'):
            query_params['size_id'] = params['size']

        if params.get('color'):
            query_params['color_id'] = params['color']

        if params.get('sort'):
            query_params['sort'] = params['sort']
        else:
            query_params['sort'] = 'created_desc'

        # Build URL
        if query_params:
            url = f"{base_url}?{urlencode(query_params)}"
        else:
            url = base_url

        return url

    def get_stats(self) -> Dict[str, Any]:
        """
        Get API usage statistics

        Returns:
            Dictionary with stats
        """
        return {
            'request_count': self.request_count,
            'proxy_enabled': bool(self.proxy),
            'proxy': self.proxy if self.proxy else 'None',
            'min_delay': self.min_delay,
            'max_delay': self.max_delay,
            'library': 'mercapi'
        }

    def __repr__(self):
        return f"<Mercari API (mercapi) (requests: {self.request_count})>"


if __name__ == "__main__":
    # Test API
    logging.basicConfig(level=logging.INFO)

    api = Mercari()

    # Test connection
    print(f"Connection test: {api.test_connection()}")

    # Test search URL building
    search_url = api.build_search_url(
        keyword='Y-3',
        min_price=1000,
        max_price=50000
    )
    print(f"Search URL: {search_url}")

    # Test search
    print("\nTesting search...")
    items = api.search(search_url, limit=5)
    print(f"Found {len(items)} items")
    for item in items:
        print(f"  - {item}")
