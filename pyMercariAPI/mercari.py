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

            # Extract ALL search parameters from URL (keyword + filters)
            search_params = self._extract_search_params_from_url(search_url)

            # Run async search in sync context with proper event loop handling
            async def _perform_search():
                m = self._get_mercapi()

                # Build mercapi search call with all extracted parameters
                # Only include parameters that are not None/empty
                call_params = {'query': search_params['query']}

                if search_params['price_min'] is not None:
                    call_params['price_min'] = search_params['price_min']

                if search_params['price_max'] is not None:
                    call_params['price_max'] = search_params['price_max']

                if search_params['categories']:
                    call_params['categories'] = search_params['categories']

                if search_params['item_conditions']:
                    call_params['item_conditions'] = search_params['item_conditions']

                # Handle status enum
                if search_params['status']:
                    # Import Status enum from mercapi
                    try:
                        from mercapi.requests.search import SearchRequestData
                        if 'on_sale' in search_params['status']:
                            call_params['status'] = [SearchRequestData.Status.STATUS_ON_SALE]
                    except ImportError:
                        logger.warning("Could not import mercapi Status enum, ignoring status filter")
                
                # IMPORTANT: Set sort order to CREATED_TIME (newest first)
                # By default mercapi sorts by SORT_SCORE (relevance), but we want chronological order
                try:
                    from mercapi.requests.search import SearchRequestData
                    call_params['sort_by'] = SearchRequestData.SortBy.SORT_CREATED_TIME
                    call_params['sort_order'] = SearchRequestData.SortOrder.ORDER_DESC
                    logger.info(f"Sort order: CREATED_TIME DESC (newest first)")
                except ImportError:
                    logger.warning("Could not import mercapi SortBy enum, using default sort")

                logger.info(f"Calling mercapi.search() with params: {call_params}")

                # Call mercapi with extracted parameters
                results = await m.search(**call_params)

                # Log what mercapi returned
                total_from_api = len(results.items) if hasattr(results, 'items') else 0
                logger.info(f"mercapi returned {total_from_api} items, will limit to {limit}")

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
                    # Determine correct URL based on item ID format
                    # Items starting with 'm' are regular items: /item/
                    # Other IDs (like 2JGxdQkWpG38dXwNH9o93g) are shop products: /shops/product/
                    if item_id.startswith('m'):
                        item_url = f"https://jp.mercari.com/item/{item_id}"
                    else:
                        item_url = f"https://jp.mercari.com/shops/product/{item_id}"
                    
                    # Extract category from item - NEED FULL ITEM DATA
                    # Search results don't include item_category, need to fetch full item
                    # NOTE: Shops products return 404 on full_item(), but may have category in search results
                    item_category = None
                    full_item_data = None
                    is_shops_product = not item_id.startswith('m')

                    # Try to get category from search results first (works for both regular and Shops)
                    if hasattr(item, 'item_category') and item.item_category:
                        try:
                            category_obj = item.item_category
                            category_parts = []
                            if hasattr(category_obj, 'root_category_name') and category_obj.root_category_name:
                                category_parts.append(category_obj.root_category_name)
                            if hasattr(category_obj, 'parent_category_name') and category_obj.parent_category_name:
                                category_parts.append(category_obj.parent_category_name)
                            if hasattr(category_obj, 'name') and category_obj.name:
                                category_parts.append(category_obj.name)

                            if category_parts:
                                item_category = ' > '.join(category_parts)
                                logger.debug(f"Item {item_id} category from search: {item_category}")
                        except Exception as e:
                            logger.debug(f"Failed to extract category from search results for {item_id}: {e}")

                    # If category not in search results and not shops product, fetch full item
                    if not item_category and hasattr(item, 'full_item') and not is_shops_product:
                        try:
                            # Call full_item() to get complete category information
                            # Skip for shops products as they return 404
                            full_item_data = await item.full_item()
                            if full_item_data and hasattr(full_item_data, 'item_category') and full_item_data.item_category:
                                category_obj = full_item_data.item_category
                                # Build full category path for blacklist matching
                                # Example: "ベビー・キッズ > キッズシューズ > スニーカー"
                                category_parts = []
                                if hasattr(category_obj, 'root_category_name') and category_obj.root_category_name:
                                    category_parts.append(category_obj.root_category_name)
                                if hasattr(category_obj, 'parent_category_name') and category_obj.parent_category_name:
                                    category_parts.append(category_obj.parent_category_name)
                                if hasattr(category_obj, 'name') and category_obj.name:
                                    category_parts.append(category_obj.name)
                                
                                if category_parts:
                                    item_category = ' > '.join(category_parts)
                                    logger.debug(f"Item {item_id} category from full_item: {item_category}")
                        except Exception as e:
                            logger.debug(f"Failed to get full item data for {item_id}: {e}")

                    # Log if Shops product has no category (for debugging)
                    if is_shops_product and not item_category:
                        logger.debug(f"Item {item_id} is shops product with no category available")

                    # Extract SIZE from search result item or full_item_data
                    item_size = None
                    # Try to extract size from full_item_data if available
                    if full_item_data:
                        item_size = self._extract_size(full_item_data)
                    # Fallback: try to extract from search result item
                    if not item_size:
                        item_size = self._extract_size(item)

                    item_dict = {
                        'mercari_id': item_id,
                        'title': getattr(item, 'name', ''),
                        'price': getattr(item, 'price', 0),
                        'currency': 'JPY',
                        'item_url': item_url,
                        'image_url': None,
                        'brand': None,
                        'condition': None,
                        'size': item_size,
                        'shipping_cost': 0,
                        'stock_quantity': 1,
                        'seller_name': None,
                        'seller_rating': None,
                        'location': None,
                        'category': item_category,
                        'description': ''
                    }

                    # Get HIGH RESOLUTION image
                    # Priority: full_item_data (if available) > search result data
                    photos = []
                    thumbnails = []
                    thumbnail = None
                    
                    # Try to get images from full_item_data first (better quality)
                    if full_item_data:
                        photos = getattr(full_item_data, 'photos', [])
                        thumbnails = getattr(full_item_data, 'thumbnails', [])
                        thumbnail = getattr(full_item_data, 'thumbnail', None)
                    
                    # Fallback to search result data if full_item_data not available
                    if not photos and not thumbnails and not thumbnail:
                        photos = getattr(item, 'photos', [])
                        thumbnails = getattr(item, 'thumbnails', [])
                        thumbnail = getattr(item, 'thumbnail', None)
                    
                    # Try to get any image (priority: photos > thumbnails > thumbnail)
                    base_image = None
                    if photos and len(photos) > 0:
                        base_image = photos[0]
                        logger.debug(f"Item {item_id}: using photos[0]")
                    elif thumbnails and len(thumbnails) > 0:
                        base_image = thumbnails[0]
                        logger.debug(f"Item {item_id}: using thumbnails[0]")
                    elif thumbnail:
                        base_image = thumbnail
                        logger.debug(f"Item {item_id}: using thumbnail")
                    
                    # Convert thumbnail URL to full-size image
                    if base_image:
                        import re
                        full_image = base_image
                        
                        # For shops products: convert /-/small/ to /-/large/
                        if 'mercari-shops-static.com' in full_image:
                            full_image = re.sub(r'/-/small/', '/-/large/', full_image)
                            full_image = re.sub(r'/small/', '/large/', full_image)
                            logger.debug(f"Item {item_id}: converted shops image to large")
                        # For regular items: upgrade resolution
                        elif 'mercdn.net' in full_image or 'mercari' in full_image:
                            full_image = re.sub(r'w_\d+', 'w_1200', full_image)
                            full_image = re.sub(r'h_\d+', 'h_1200', full_image)
                            logger.debug(f"Item {item_id}: upgraded image resolution")
                        
                        item_dict['image_url'] = full_image
                        logger.debug(f"Item {item_id}: final image_url = {full_image[:80]}")
                    else:
                        item_dict['image_url'] = None
                        logger.warning(f"No image found for item {item_id}")

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

    def _extract_search_params_from_url(self, search_url: str) -> Dict[str, Any]:
        """
        Extract ALL search parameters from Mercari search URL

        Args:
            search_url: Full Mercari URL or keyword

        Returns:
            Dictionary with all search parameters for mercapi.search()
        """
        # Default params
        search_params = {
            'query': '',
            'price_min': None,
            'price_max': None,
            'categories': [],
            'item_conditions': [],
            'status': []
        }

        # If it's not a URL, it's just a keyword
        if not search_url.startswith('http'):
            search_params['query'] = search_url
            return search_params

        # Parse URL
        from urllib.parse import urlparse, parse_qs

        try:
            parsed = urlparse(search_url)
            params = parse_qs(parsed.query)

            # Extract keyword
            keyword = params.get('keyword', [''])[0]
            search_params['query'] = keyword.strip()

            # Extract price filters
            if 'price_min' in params:
                try:
                    search_params['price_min'] = int(params['price_min'][0])
                    logger.info(f"Extracted price_min: {search_params['price_min']}")
                except (ValueError, IndexError):
                    pass

            if 'price_max' in params:
                try:
                    search_params['price_max'] = int(params['price_max'][0])
                    logger.info(f"Extracted price_max: {search_params['price_max']}")
                except (ValueError, IndexError):
                    pass

            # Extract category_id (single category)
            if 'category_id' in params:
                try:
                    category_id = int(params['category_id'][0])
                    search_params['categories'] = [category_id]
                    logger.info(f"Extracted category_id: {category_id}")
                except (ValueError, IndexError):
                    pass

            # Extract item condition (status parameter in URL)
            # status=on_sale means only active listings
            if 'status' in params:
                status_value = params['status'][0]
                if status_value == 'on_sale':
                    # mercapi uses Status enum - we'll handle this in search()
                    search_params['status'] = ['on_sale']
                    logger.info(f"Extracted status: on_sale")

            # Extract item_condition if present (condition parameter in URL)
            if 'item_condition_id' in params:
                try:
                    condition_ids = [int(c) for c in params['item_condition_id']]
                    search_params['item_conditions'] = condition_ids
                    logger.info(f"Extracted item_conditions: {condition_ids}")
                except (ValueError, TypeError):
                    pass

            logger.info(f"Extracted search params: keyword='{search_params['query']}', "
                       f"price_min={search_params['price_min']}, "
                       f"price_max={search_params['price_max']}, "
                       f"categories={search_params['categories']}")

        except Exception as e:
            logger.error(f"Failed to parse URL parameters: {e}")
            # Fall back to keyword-only
            search_params['query'] = self._extract_keyword_from_url(search_url)

        return search_params

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
            elif '/shops/product/' in item_url:
                item_id = item_url.split('/shops/product/')[-1].split('?')[0]

            logger.info(f"Getting item details: {item_id}")

            # Run async in sync context with shared event loop
            async def _get_item():
                m = self._get_mercapi()
                return await m.item(item_id)

            full_item = self._run_async(_get_item())

            if not full_item:
                return None

            # Convert to our Item format
            # Determine correct URL based on item ID format
            if item_id.startswith('m'):
                item_url = f"https://jp.mercari.com/item/{item_id}"
            else:
                item_url = f"https://jp.mercari.com/shops/product/{item_id}"
            
            item_data = {
                'mercari_id': item_id,
                'title': getattr(full_item, 'name', ''),
                'price': getattr(full_item, 'price', 0),
                'currency': 'JPY',
                'item_url': item_url,
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

            # Get ORIGINAL FULL SIZE photos (not thumbnails!)
            if hasattr(full_item, 'photos') and full_item.photos:
                # photos already contains full-size /orig/ URLs from mercapi
                item_data['image_url'] = full_item.photos[0]
            elif hasattr(full_item, 'thumbnails') and full_item.thumbnails:
                # Fallback to thumbnails and upgrade to high-res
                import re
                thumbnail = full_item.thumbnails[0]
                # Upgrade thumbnail to high-res
                high_res = re.sub(r'w_\d+', 'w_1200', thumbnail)
                high_res = re.sub(r'h_\d+', 'h_1200', high_res)
                # For shops products: convert small to large
                if '/shops/' in item_url or 'mercari-shops-static.com' in high_res:
                    high_res = re.sub(r'/-/small/', '/-/large/', high_res)
                    high_res = re.sub(r'/small/', '/large/', high_res)
                item_data['image_url'] = high_res
                logger.info(f"Using thumbnail for shops product {item_id}: {high_res[:80]}")
            elif hasattr(full_item, 'thumbnail') and full_item.thumbnail:
                # Last fallback: single thumbnail
                import re
                thumbnail = full_item.thumbnail
                high_res = re.sub(r'w_\d+', 'w_1200', thumbnail)
                high_res = re.sub(r'h_\d+', 'h_1200', high_res)
                if '/shops/' in item_url or 'mercari-shops-static.com' in high_res:
                    high_res = re.sub(r'/-/small/', '/-/large/', high_res)
                    high_res = re.sub(r'/small/', '/large/', high_res)
                item_data['image_url'] = high_res
                logger.info(f"Using single thumbnail for shops product {item_id}: {high_res[:80]}")
            
            # Extract SIZE from description or item attributes
            item_data['size'] = self._extract_size(full_item)

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
                if hasattr(full_item.seller, 'ratings'):
                    ratings = full_item.seller.ratings
                    good = getattr(ratings, 'good', 0)
                    total = getattr(full_item.seller, 'num_ratings', 0)
                    if total > 0:
                        item_data['seller_rating'] = f"{good}/{total}"

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

    def _extract_size(self, item) -> Optional[str]:
        """
        Extract size from item title, description or attributes

        Args:
            item: mercapi item object

        Returns:
            Size string or None
        """
        import re

        # Get both title and description (search results have title but not description)
        title = getattr(item, 'name', '') or getattr(item, 'title', '') or ''
        description = getattr(item, 'description', '') or ''

        # Try title first (available in search results), then description (only in full_item)
        text_sources = [title, description]

        # Common size patterns in Japanese (ordered by priority)
        size_patterns = [
            r'サイズ[:\s]*([A-Z0-9]+)',  # サイズ: XS, サイズ M
            r'size[:\s]*([A-Z0-9]+)',     # size: L, size XL
            r'([0-9]+\.?[0-9]*)\s?cm',   # 80cm, 90.5cm, 27.5cm (shoes)
            r'\b(XS|XXL|XXXL|XL|L|M|S)\b',  # Standalone (must be exact word)
            r'フリーサイズ',  # Japanese "free size"
        ]

        for text in text_sources:
            if not text:
                continue

            for pattern in size_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if pattern == r'フリーサイズ':
                        return 'FREE'
                    size = match.group(1).strip().upper()
                    # Validate size - exclude common words that might match
                    if size and len(size) <= 10:
                        # Exclude if it's part of a brand name or common word
                        if size not in ['IS', 'AS', 'US', 'IN', 'ON', 'OR', 'SO', 'TO']:
                            return size
        
        return None

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
