"""
Core search logic for MercariSearcher
Adapted from KufarSearcher

Implements VS5-style individual scan intervals for each search query
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from pyMercariAPI import Mercari
from db import get_db
from proxies import proxy_rotator
from configuration_values import config
from shared_state import get_shared_state

logger = logging.getLogger(__name__)


class MercariSearcher:
    """Main searcher class for Mercari marketplace"""

    def __init__(self, use_proxy: bool = None):
        """
        Initialize Mercari searcher

        Args:
            use_proxy: Whether to use proxy (None = use config setting)
        """
        self.db = get_db()
        self.shared_state = get_shared_state()

        # Proxy settings
        if use_proxy is None:
            use_proxy = config.PROXY_ENABLED

        self.use_proxy = use_proxy

        # Initialize Mercari API
        self.api = self._init_api()

        # Statistics
        self.total_api_requests = 0
        self.total_items_found = 0
        self.total_errors = 0

        logger.info("MercariSearcher initialized")

    def _init_api(self):
        """Initialize Mercari API with optional proxy"""
        try:
            proxy = None
            if self.use_proxy and proxy_rotator:
                proxy = proxy_rotator.get_proxy()

            api = Mercari(proxy=proxy)

            # Test connection
            if api.test_connection():
                logger.info("Mercari API connection successful")
                self.shared_state.set('db_connected', True)
            else:
                logger.warning("Mercari connection test failed")
                # Try changing proxy
                if self.use_proxy and proxy_rotator:
                    new_proxy = proxy_rotator.get_proxy()
                    api.change_proxy(new_proxy)

            return api

        except Exception as e:
            logger.error(f"Failed to initialize Mercari API: {e}")
            raise

    def search_all_queries(self) -> Dict[str, Any]:
        """
        Main search cycle - scans all ready queries

        Returns:
            Dictionary with scan statistics
        """
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("Starting search cycle")
        logger.info("=" * 60)

        # Log to database
        self.db.add_log_entry('INFO', 'Starting search cycle', 'core')

        # Get searches ready for scanning
        ready_searches = self.db.get_searches_ready_for_scan()

        logger.info(f"Searches ready for scan: {len(ready_searches)}")
        self.db.add_log_entry('INFO', f'Found {len(ready_searches)} searches ready for scan', 'core')

        if not ready_searches:
            logger.info("No searches ready. Waiting for next cycle.")
            return {
                'total_searches': 0,
                'successful_searches': 0,
                'failed_searches': 0,
                'total_items_found': 0,
                'new_items': 0,
                'duration': 0
            }

        # Update shared state
        self.shared_state.update(
            scanner_running=True,
            active_searches=len(ready_searches)
        )

        # Process each search
        results = {
            'total_searches': len(ready_searches),
            'successful_searches': 0,
            'failed_searches': 0,
            'total_items_found': 0,
            'new_items': 0
        }

        for search in ready_searches:
            try:
                # Get query name for better logging
                query_name = search.get('name', search.get('keyword', f"Query ID {search['id']}"))

                logger.info(f"\n{'='*60}")
                logger.info(f"[SCAN] 🔍 Scanning query: {query_name}")
                logger.info(f"[SCAN] Query ID: {search['id']}")
                logger.info(f"[SCAN] Search URL: {search.get('search_url', 'N/A')[:80]}...")
                logger.info(f"{'='*60}")

                self.db.add_log_entry('INFO', f"🔍 Scanning query: {query_name}", 'scanner', f"ID: {search['id']}")

                # Perform search
                items_result = self.search_query(search)

                if items_result['success']:
                    results['successful_searches'] += 1
                    results['total_items_found'] += items_result['items_found']
                    results['new_items'] += items_result['new_items']

                    logger.info(f"[SCAN] ✅ Search completed: {items_result['items_found']} total items from API, {items_result['new_items']} NEW items added to DB")

                    # Log names of new items found
                    if items_result.get('items_data') and len(items_result['items_data']) > 0:
                        logger.info(f"[SCAN] 🆕 NEW ITEMS ADDED ({len(items_result['items_data'])}):")
                        for idx, item in enumerate(items_result['items_data'][:10], 1):  # Log first 10
                            logger.info(f"[SCAN]    {idx}. {item.get('title', 'Unknown')[:60]} - ¥{item.get('price', 0):,}")
                        if len(items_result['items_data']) > 10:
                            logger.info(f"[SCAN]    ... and {len(items_result['items_data']) - 10} more")
                    elif items_result['new_items'] == 0:
                        logger.info(f"[SCAN] ℹ️  No new items (all {items_result['items_found']} items already in database)")

                    self.db.add_log_entry('INFO',
                        f"✅ Found {items_result['items_found']} items ({items_result['new_items']} new) in {query_name}",
                        'search', f"ID: {search['id']}")
                else:
                    results['failed_searches'] += 1
                    error_msg = items_result.get('error', 'Unknown error')
                    logger.warning(f"[SCAN] ❌ Search failed: {error_msg}")
                    self.db.add_log_entry('WARNING', f"Search failed: {error_msg}", 'search', f"ID: {search['id']}, Query: {query_name}")

                # Update search scan time
                self.db.update_search_scan_time(search['id'])

                # Rate limiting between searches
                time.sleep(config.REQUEST_DELAY_MIN)

            except Exception as e:
                logger.error(f"Error processing search {search['id']}: {e}")
                self.db.add_log_entry('ERROR', f"Error processing search: {str(e)}", 'search', f"ID: {search['id']}")
                self.db.log_error(f"Error processing search {search['id']}: {str(e)}", 'search_cycle')
                results['failed_searches'] += 1
                self.total_errors += 1
                self.shared_state.add_error(str(e))

        # Calculate duration
        duration = time.time() - start_time
        results['duration'] = duration

        # Update shared state
        self.shared_state.update_scan_stats(duration, results['new_items'])
        self.shared_state.set('scanner_running', False)

        # Log summary
        logger.info("\n" + "=" * 60)
        logger.info("Search cycle completed")
        logger.info(f"Total searches: {results['total_searches']}")
        logger.info(f"Successful: {results['successful_searches']}")
        logger.info(f"Failed: {results['failed_searches']}")
        logger.info(f"Items found: {results['total_items_found']}")
        logger.info(f"New items: {results['new_items']}")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info("=" * 60)

        return results

    def search_query(self, search: Dict[str, Any], limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Search single query

        Args:
            search: Search dictionary from database
            limit: Max items to fetch (None = use GLOBAL config from Web UI)

        Returns:
            Dictionary with search results
        """
        try:
            search_url = search['search_url']
            search_id = search['id']

            # Use GLOBAL config setting (from Web UI config page)
            if limit is None:
                limit = config.MAX_ITEMS_PER_SEARCH

            logger.info(f"Searching: {search_url[:100]}... (limit: {limit})")

            # Perform search
            items_result = self.api.search(search_url, limit=limit)

            # Increment API request counter (in both memory and database for cross-process visibility)
            self.total_api_requests += 1
            self.shared_state.increment('total_api_requests')
            self.db.increment_api_counter()

            # Extract items list from Items object
            if hasattr(items_result, 'items'):
                items = items_result.items
            else:
                items = items_result if isinstance(items_result, list) else []
            
            # CRITICAL: Ensure we respect limit (mercapi might return more)
            if len(items) > limit:
                logger.warning(f"mercapi returned {len(items)} items but limit is {limit}, truncating")
                items = items[:limit]
            
            items_found = len(items)
            logger.info(f"API returned {items_found} items (limit: {limit})")

            # Process new items
            new_items_data = self._process_new_items(items, search_id)

            # Update search stats
            if new_items_data:
                self.db.update_search_stats(search_id, len(new_items_data))

            return {
                'success': True,
                'items_found': items_found,
                'new_items': len(new_items_data),
                'items_data': new_items_data
            }

        except Exception as e:
            logger.error(f"Search query failed: {e}")
            self.total_errors += 1
            
            # Log to database for tracking
            self.db.log_error(f"Search query failed: {str(e)}", 'search')

            # Try changing proxy on error
            if self.use_proxy and proxy_rotator and '403' in str(e):
                logger.info("Changing proxy due to error")
                new_proxy = proxy_rotator.get_proxy()
                self.api.change_proxy(new_proxy)

            return {
                'success': False,
                'items_found': 0,
                'new_items': 0,
                'error': str(e)
            }

    def _process_new_items(self, items, search_id: int) -> List[Dict[str, Any]]:
        """
        Process items and save new ones to database with HIGH-RESOLUTION images
        Uses new image_handler module for original quality photos

        Args:
            items: Items object from API (list of Item objects)
            search_id: Search ID

        Returns:
            List of new items data
        """
        from image_handler import get_original_image_url, download_and_encode_image
        
        new_items = []
        
        logger.info(f"[PROCESS] 📦 Processing {len(items)} items from API response...")

        for item in items:
            try:
                # Item class has .id attribute
                item_id = item.id
                if not item_id:
                    logger.error(f"❌ Item has no ID, skipping")
                    continue
                
                # Get full item details for size, photos, description
                logger.info(f"[PROCESS] 📦 Getting full details for item: {item_id}")
                
                try:
                    full_item = self.api.get_item(item_id)
                    
                    # Increment API counter
                    self.total_api_requests += 1
                    self.shared_state.increment('total_api_requests')
                    self.db.increment_api_counter()
                    
                    if not full_item:
                        logger.warning(f"⚠️ get_item returned None, using search data")
                        full_item = item
                except Exception as e:
                    logger.warning(f"⚠️ get_item failed: {e}, using search data")
                    full_item = item
                
                # Get mercari_id from Item object
                mercari_id = full_item.id
                if not mercari_id:
                    logger.error(f"❌ Item has no ID, skipping")
                    continue
                
                # Get image URL - Item class has .image_url attribute
                image_url = full_item.image_url
                
                # Convert to high-resolution URL
                if image_url:
                    original_url = get_original_image_url(image_url)
                    logger.info(f"[PROCESS] 📸 Image URL: {original_url[:80]}...")
                    image_url = original_url
                else:
                    logger.warning(f"[PROCESS] ⚠️ No image URL for item {mercari_id}")

                # Download and encode HIGH-RESOLUTION image
                image_data = None
                if image_url:
                    logger.info(f"[PROCESS] 📥 Downloading HIGH-RES image...")
                    image_data = download_and_encode_image(image_url, timeout=20, use_proxy=False)
                    if image_data:
                        logger.info(f"[PROCESS] ✅ HIGH-RES image saved ({len(image_data)/1024:.1f}KB base64)")
                    else:
                        logger.warning(f"[PROCESS] ⚠️ Failed to download image, will add item without image data")

                # Log item info
                logger.info(f"[PROCESS] 📋 Item info:")
                logger.info(f"[PROCESS]    Title: {full_item.title[:60]}")
                logger.info(f"[PROCESS]    Price: ¥{full_item.price:,}")
                logger.info(f"[PROCESS]    Size: {full_item.size or 'N/A'}")
                logger.info(f"[PROCESS]    Brand: {full_item.brand or 'N/A'}")
                logger.info(f"[PROCESS]    Image: {'✅ HIGH-RES' if image_data else '⚠️ URL only'}")

                # Add to database
                db_item_id = self.db.add_item(
                    mercari_id=mercari_id,
                    search_id=search_id,
                    title=full_item.title,
                    price=full_item.price,
                    currency=full_item.currency,
                    brand=full_item.brand,
                    condition=full_item.condition,
                    size=full_item.size,
                    shipping_cost=full_item.shipping_cost,
                    stock_quantity=full_item.stock_quantity,
                    item_url=full_item.url,
                    image_url=image_url,
                    seller_name=full_item.seller_name,
                    seller_rating=full_item.seller_rating,
                    location=full_item.location,
                    description=full_item.description,
                    category=full_item.category,
                    image_data=image_data
                )

                # If item was added (new), add to list
                if db_item_id:
                    item_dict = full_item.to_dict()
                    item_dict['db_id'] = db_item_id
                    item_dict['image_data'] = image_data  # Include for notifications
                    new_items.append(item_dict)
                    self.total_items_found += 1
                    logger.info(f"[PROCESS] ✅ NEW item added to DB (ID: {db_item_id})")
                else:
                    logger.debug(f"[PROCESS] ⏭️  Item already exists in DB: {mercari_id}")

            except Exception as e:
                item_id_str = item_id if 'item_id' in locals() else 'unknown'
                logger.error(f"[PROCESS] ❌ Failed to process item {item_id_str}: {e}")
                self.db.log_error(f"Failed to process item {item_id_str}: {str(e)}", 'item_processing')
                import traceback
                logger.error(traceback.format_exc())
                continue

        if new_items:
            logger.info(f"[PROCESS] ✅ Successfully saved {len(new_items)} NEW items with HIGH-RES images")
        else:
            logger.info(f"[PROCESS] ℹ️  No new items (all already in database)")

        return new_items

    def validate_search_url(self, search_url: str) -> Dict[str, Any]:
        """
        Validate and parse Mercari search URL

        Args:
            search_url: Mercari search URL

        Returns:
            Dictionary with parsed parameters
        """
        from urllib.parse import urlparse, parse_qs

        try:
            parsed = urlparse(search_url)

            if 'mercari.com' not in parsed.netloc:
                return {
                    'valid': False,
                    'error': 'Not a Mercari URL'
                }

            # Parse query parameters
            params = parse_qs(parsed.query)

            result = {
                'valid': True,
                'keyword': params.get('keyword', [None])[0],
                'category_id': params.get('category_id', [None])[0],
                'brand': params.get('brand', [None])[0],
                'min_price': params.get('price_min', [None])[0],
                'max_price': params.get('price_max', [None])[0],
                'condition': params.get('item_condition_id', [None])[0],
                'size': params.get('size_id', [None])[0],
                'color': params.get('color_id', [None])[0],
                'sort_order': params.get('sort', ['created_desc'])[0]
            }

            return result

        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }

    def get_searcher_status(self) -> Dict[str, Any]:
        """
        Get searcher status and statistics

        Returns:
            Dictionary with status info
        """
        return {
            'total_api_requests': self.total_api_requests,
            'total_items_found': self.total_items_found,
            'total_errors': self.total_errors,
            'proxy_enabled': self.use_proxy,
            'current_proxy': self.api.proxy if hasattr(self.api, 'proxy') else None,
            'api_stats': self.api.get_stats() if hasattr(self.api, 'get_stats') else {}
        }


def validate_search_url(search_url: str) -> Dict[str, Any]:
    """
    Standalone function to validate search URL

    Args:
        search_url: Mercari search URL

    Returns:
        Dictionary with validation result
    """
    searcher = MercariSearcher(use_proxy=False)
    return searcher.validate_search_url(search_url)


if __name__ == "__main__":
    # Test searcher
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test URL validation
    test_url = "https://jp.mercari.com/search?keyword=ナイキ&price_min=1000&price_max=10000"
    result = validate_search_url(test_url)
    print(f"\nURL Validation Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Test searcher
    # searcher = MercariSearcher()
    # print(f"\nSearcher Status:")
    # status = searcher.get_searcher_status()
    # for key, value in status.items():
    #     print(f"  {key}: {value}")
