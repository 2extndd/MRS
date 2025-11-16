"""
Main Mercari API wrapper class
"""

import time
import random
import logging
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
    Mercari API wrapper using web scraping
    Compatible interface with pyKufarVN
    """

    def __init__(self, proxy: Optional[str] = None, scraper=None):
        """
        Initialize Mercari API wrapper

        Args:
            proxy: Proxy URL (e.g., 'http://proxy:port')
            scraper: Custom scraper instance (for dependency injection)
        """
        self.proxy = proxy
        self.scraper = scraper
        self.request_count = 0
        self.last_request_time = 0

        # Rate limiting settings
        self.min_delay = 1.5
        self.max_delay = 3.5

        # Initialize scraper if not provided
        if not self.scraper:
            from mercari_scraper import MercariScraper
            self.scraper = MercariScraper(proxy=proxy)

        logger.info(f"Mercari API initialized (proxy: {bool(proxy)})")

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
        """
        self.proxy = new_proxy

        # Reinitialize scraper with new proxy
        from mercari_scraper import MercariScraper
        self.scraper = MercariScraper(proxy=new_proxy)

        logger.info(f"Proxy changed: {bool(new_proxy)}")

    def test_connection(self) -> bool:
        """
        Test connection to Mercari

        Returns:
            True if connection successful
        """
        try:
            from configuration_values import config
            html = self.scraper.get_page(config.MERCARI_BASE_URL)
            return html is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def search(self, search_url: str, limit: int = 50) -> Items:
        """
        Search for items on Mercari

        Args:
            search_url: Full Mercari search URL
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

            items_data = self.scraper.search_items(search_url, limit=limit)

            if items_data is None:
                raise MercariConnectionError("Failed to fetch search results")

            items = Items(items_data)

            logger.info(f"Found {len(items)} items")

            return items

        except MercariConnectionError:
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise MercariAPIError(f"Search error: {e}")

    def get_item(self, item_url: str) -> Optional[Item]:
        """
        Get detailed information for a specific item

        Args:
            item_url: Full Mercari item URL

        Returns:
            Item object or None if not found
        """
        try:
            self._rate_limit()

            logger.info(f"Getting item details: {item_url}")

            item_data = self.scraper.get_item_details(item_url)

            if not item_data:
                return None

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
            'max_delay': self.max_delay
        }

    def __repr__(self):
        return f"<Mercari API (requests: {self.request_count}, proxy: {bool(self.proxy)})>"


if __name__ == "__main__":
    # Test API
    logging.basicConfig(level=logging.INFO)

    api = Mercari()

    # Test connection
    print(f"Connection test: {api.test_connection()}")

    # Test search URL building
    search_url = api.build_search_url(
        keyword='ナイキ',
        min_price=1000,
        max_price=10000
    )
    print(f"Search URL: {search_url}")

    # Test search
    # items = api.search(search_url, limit=5)
    # print(f"Found {len(items)} items")
    # for item in items:
    #     print(f"  - {item}")
