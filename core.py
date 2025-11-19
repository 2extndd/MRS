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

                    logger.info(f"[SCAN] ✅ Search completed: {items_result['items_found']} total items, {items_result['new_items']} NEW items")

                    # Log names of new items found
                    if items_result.get('items_data'):
                        logger.info(f"[SCAN] 📦 New items found:")
                        for idx, item in enumerate(items_result['items_data'][:10], 1):  # Log first 10
                            logger.info(f"[SCAN]    {idx}. {item.get('title', 'Unknown')} - ¥{item.get('price', 0)}")
                        if len(items_result['items_data']) > 10:
                            logger.info(f"[SCAN]    ... and {len(items_result['items_data']) - 10} more")

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
            limit: Max items to fetch (None = use config)

        Returns:
            Dictionary with search results
        """
        try:
            search_url = search['search_url']
            search_id = search['id']

            if limit is None:
                limit = config.MAX_ITEMS_PER_SEARCH

            logger.info(f"Searching: {search_url[:100]}...")

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
        Process items and save new ones to database
        Gets FULL item details (size, original photos) for each item

        Args:
            items: Items object from API
            search_id: Search ID

        Returns:
            List of new items data
        """
        new_items = []

        for item in items:
            try:
                # Get item ID (mercapi uses id_, our Item class uses id)
                item_id = getattr(item, 'id_', None) or getattr(item, 'id', None)
                if not item_id:
                    logger.error(f"❌ Item has no ID, skipping")
                    continue
                
                # STRATEGY: Try to get high-res photos WITHOUT slow get_item() calls
                # 1. Use search data as base (fast)
                # 2. Upgrade photo URL to high-res via manipulation
                # 3. Only call get_item() if URL manipulation fails
                full_item = item
                needs_get_item = False
                
                # Try to get high-res photo URL from search data
                search_photo = getattr(item, 'image_url', None) or getattr(item, 'image', None)
                if search_photo:
                    import re
                    # Try URL manipulation to get /orig/ or /large/
                    if 'mercari-shops-static.com' in search_photo:
                        # Mercari Shops: small → large
                        search_photo = re.sub(r'/-/small/', '/-/large/', search_photo)
                        logger.info(f"   📸 Mercari Shops: upgraded to /large/")
                    elif 'mercdn.net' in search_photo:
                        # Regular Mercari: upgrade to /orig/ (ORIGINAL quality, no resize)
                        if '/thumb/' in search_photo or 'w_' in search_photo or '/c/' in search_photo:
                            # Remove all size params and use /orig/
                            search_photo = re.sub(r'/thumb/[^/]+/', '/item/detail/orig/photos/', search_photo)
                            search_photo = re.sub(r'/c/w=\d+/[^/]+/', '/item/detail/orig/photos/', search_photo)
                            search_photo = re.sub(r'\?w=\d+.*$', '', search_photo)  # Remove query params
                            search_photo = re.sub(r'w_\d+', 'orig', search_photo)  # Replace w_240 with orig
                            # Ensure proper path structure
                            if '/item/detail/orig/photos/' not in search_photo:
                                # Fallback: just replace path segments
                                search_photo = search_photo.replace('/thumb/', '/item/detail/orig/photos/')
                                search_photo = search_photo.replace('/c/', '/item/detail/orig/photos/')
                            logger.info(f"   📸 URL upgraded to /orig/ (original quality)")
                        elif '/orig/' in search_photo:
                            logger.info(f"   📸 Already /orig/ quality")
                        else:
                            needs_get_item = True  # Unknown format, need get_item
                    else:
                        needs_get_item = True  # Unknown domain
                    
                    # Update item's image_url
                    if hasattr(item, 'image_url'):
                        item.image_url = search_photo
                else:
                    needs_get_item = True  # No photo in search, need get_item
                
                # Only call get_item() if URL manipulation didn't work
                if needs_get_item:
                    try:
                        logger.info(f"📦 Calling get_item() for full details: {item_id}")
                        full_item_result = self.api.get_item(item_id)
                        
                        # Increment API counter
                        self.total_api_requests += 1
                        self.shared_state.increment('total_api_requests')
                        self.db.increment_api_counter()
                        
                        if full_item_result:
                            full_item = full_item_result
                            logger.info(f"✅ Got full details via get_item()")
                        else:
                            logger.warning(f"⚠️ get_item returned None, using upgraded search data")
                    except Exception as e:
                        logger.warning(f"⚠️ get_item failed: {e}, using upgraded search data")
                else:
                    logger.info(f"✅ Using upgraded search data (no get_item needed)")
                
                # Get mercari_id from full_item (mercapi uses id_, our Item uses id)
                mercari_id = getattr(full_item, 'id_', None) or getattr(full_item, 'id', None)
                if not mercari_id:
                    logger.error(f"❌ Full item has no ID, skipping")
                    continue
                
                # Convert to dict
                item_dict = full_item.to_dict()

                # Image URL is already ORIGINAL from get_item() (mercapi photos field)
                image_url = full_item.image_url
                
                # Ensure it's original/high quality
                if image_url:
                    import re
                    
                    # For Mercari Shops items: replace /small/ with /large/ (best available)
                    if 'mercari-shops-static.com' in image_url:
                        image_url = re.sub(r'/-/small/', '/-/large/', image_url)
                        logger.info(f"   Mercari Shops: using /large/ quality")
                    
                    # For regular Mercari items: ensure /orig/
                    elif '/orig/' not in image_url:
                        image_url = re.sub(r'/thumb/', '/orig/', image_url)
                        image_url = re.sub(r'w_\d+', 'w_1200', image_url)
                        image_url = re.sub(r'h_\d+', 'h_1200', image_url)
                
                logger.info(f"   Size: {full_item.size or 'N/A'}")
                logger.info(f"   Photo: {'ORIGINAL' if '/orig/' in (image_url or '') else 'thumbnail'}")
                
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
                    category=full_item.category
                )

                # If item was added (new), add to list
                if db_item_id:
                    item_dict['db_id'] = db_item_id
                    new_items.append(item_dict)
                    self.total_items_found += 1
                    logger.info(f"✅ NEW item added to DB: {full_item.title[:50]}")
                else:
                    logger.info(f"⏭️ Item already exists: {mercari_id}")

            except Exception as e:
                item_id_str = item_id if 'item_id' in locals() else 'unknown'
                logger.error(f"Failed to process item {item_id_str}: {e}")
                # Log to database for tracking
                self.db.log_error(f"Failed to process item {item_id_str}: {str(e)}", 'item_processing')
                import traceback
                logger.error(traceback.format_exc())
                continue

        if new_items:
            logger.info(f"Saved {len(new_items)} new items to database")

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
