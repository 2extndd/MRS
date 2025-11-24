"""
Core search logic for MercariSearcher
Adapted from KufarSearcher

Implements VS5-style individual scan intervals for each search query
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import concurrent.futures

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

        # Process each search - PARALLEL execution for speed
        results = {
            'total_searches': len(ready_searches),
            'successful_searches': 0,
            'failed_searches': 0,
            'total_items_found': 0,
            'new_items': 0
        }

        # Define worker function for thread pool
        def process_single_search(search):
            """Process a single search in a thread - each thread has its own API instance"""
            try:
                # Get query name for better logging
                query_name = search.get('name', search.get('keyword', f"Query ID {search['id']}"))

                logger.info(f"\n{'='*60}")
                logger.info(f"[SCAN] 🔍 Scanning query: {query_name}")
                logger.info(f"[SCAN] Query ID: {search['id']}")
                logger.info(f"[SCAN] Search URL: {search.get('search_url', 'N/A')[:80]}...")
                logger.info(f"{'='*60}")

                # Each thread uses the shared DB instance (psycopg2 handles connections thread-safe)
                self.db.add_log_entry('INFO', f"🔍 Scanning query: {query_name}", 'scanner', f"ID: {search['id']}")

                # CRITICAL: Create separate API instance for this thread
                # Cannot share async objects between threads!
                thread_api = self._init_api()
                
                # Perform search with thread-local API
                items_result = self.search_query(search, api_instance=thread_api)

                # Update search scan time
                self.db.update_search_scan_time(search['id'])

                if items_result['success']:
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
                    
                    return {
                        'success': True,
                        'items_found': items_result['items_found'],
                        'new_items': items_result['new_items'],
                        'search_id': search['id']
                    }
                else:
                    error_msg = items_result.get('error', 'Unknown error')
                    logger.warning(f"[SCAN] ❌ Search failed: {error_msg}")
                    self.db.add_log_entry('WARNING', f"Search failed: {error_msg}", 'search', f"ID: {search['id']}, Query: {query_name}")
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'search_id': search['id']
                    }

            except Exception as e:
                logger.error(f"Error processing search {search['id']}: {e}")
                self.db.add_log_entry('ERROR', f"Error processing search: {str(e)}", 'search', f"ID: {search['id']}")
                self.db.log_error(f"Error processing search {search['id']}: {str(e)}", 'search_cycle')
                self.shared_state.add_error(str(e))
                
                return {
                    'success': False,
                    'error': str(e),
                    'search_id': search['id']
                }

        # Execute searches in parallel using thread pool
        # Dynamic max_workers: scale up to 20 based on ready searches
        # Safe limit to avoid rate limiting and resource issues
        MAX_PARALLEL_SEARCHES = 20  # Maximum safe parallel searches
        max_workers = min(len(ready_searches), MAX_PARALLEL_SEARCHES)
        
        logger.info(f"[PARALLEL] Processing {len(ready_searches)} searches with {max_workers} parallel threads")
        
        if len(ready_searches) > max_workers:
            batches = (len(ready_searches) + max_workers - 1) // max_workers  # Round up
            logger.info(f"[PARALLEL] Note: {len(ready_searches)} searches will be processed in {batches} batches ({max_workers} per batch)")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all searches
            future_to_search = {executor.submit(process_single_search, search): search for search in ready_searches}
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_search):
                search = future_to_search[future]
                try:
                    result = future.result()
                    
                    if result['success']:
                        results['successful_searches'] += 1
                        results['total_items_found'] += result.get('items_found', 0)
                        results['new_items'] += result.get('new_items', 0)
                    else:
                        results['failed_searches'] += 1
                        self.total_errors += 1
                        
                except Exception as e:
                    logger.error(f"Thread exception for search {search['id']}: {e}")
                    results['failed_searches'] += 1
                    self.total_errors += 1

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

    def search_query(self, search: Dict[str, Any], limit: Optional[int] = None, api_instance=None) -> Dict[str, Any]:
        """
        Search single query

        Args:
            search: Search dictionary from database
            limit: Max items to fetch (None = use GLOBAL config from Web UI)
            api_instance: Optional API instance (for thread-safe parallel execution)

        Returns:
            Dictionary with search results
        """
        try:
            search_url = search['search_url']
            search_id = search['id']

            # Use GLOBAL config setting (from Web UI config page)
            if limit is None:
                limit = config.MAX_ITEMS_PER_SEARCH
            
            # SPECIAL CASE: First scan after DB clear
            # If this search has 0 items in database, load more items to populate
            items_count_query = "SELECT COUNT(*) as count FROM items WHERE search_id = %s"
            result = self.db.execute_query(items_count_query, (search_id,), fetch=True)
            items_in_db = result[0]['count'] if result else 0
            
            if items_in_db == 0:
                # First scan - load more items to populate database
                original_limit = limit
                limit = min(50, config.MAX_ITEMS_PER_SEARCH * 10)  # Up to 50 items on first scan
                logger.info(f"[FIRST SCAN] This search has 0 items in DB, increasing limit: {original_limit} → {limit}")

            logger.info(f"Searching: {search_url[:100]}... (limit: {limit})")

            # Use thread-local API instance if provided, otherwise use self.api
            api = api_instance if api_instance else self.api
            
            # Perform search
            items_result = api.search(search_url, limit=limit)

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

            # Count new items
            new_items_count = len(new_items_data) if new_items_data else 0
            
            # IMPORTANT: Log immediately after counting
            logger.info(f"[SEARCH] 📊 RESULT: API returned {items_found} items, added {new_items_count} NEW items to database")

            # Update search stats
            if new_items_data:
                self.db.update_search_stats(search_id, len(new_items_data))

            return {
                'success': True,
                'items_found': items_found,
                'new_items': new_items_count,
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
                
                # OPTIMIZATION: Skip get_item() call - we already have enough data from search
                # get_item() adds 1-2 seconds per item and we don't need all details
                # Using search data directly is much faster
                full_item = item
                logger.debug(f"[PROCESS] Using search data for item: {item_id} (faster)")
                
                # Get mercari_id from Item object
                mercari_id = full_item.id
                if not mercari_id:
                    logger.error(f"❌ Item has no ID, skipping")
                    continue
                
                # GLOBAL CATEGORY FILTER: Check if item's category is blacklisted
                # OPTIMIZATION: Do this BEFORE downloading images to save time
                item_category = getattr(full_item, 'category', None)

                # DEBUG: Log category for EVERY item (especially Shops!)
                is_shops_item = not mercari_id.startswith('m')
                logger.info(f"[FILTER] {'[SHOPS]' if is_shops_item else '[REGULAR]'} Item {mercari_id}: category = '{item_category}'")

                item_rejected = False
                if item_category and config.CATEGORY_BLACKLIST:
                    # Check if category matches any blacklisted category
                    for blacklisted_cat in config.CATEGORY_BLACKLIST:
                        if blacklisted_cat in item_category:
                            logger.info(f"[FILTER] 🚫 Item rejected: category '{item_category}' is blacklisted")
                            logger.info(f"[FILTER]    Title: {full_item.title[:60]}")
                            logger.info(f"[FILTER]    Matched blacklist: '{blacklisted_cat}'")
                            item_rejected = True

                            # Log to database
                            try:
                                self.db.add_log_entry('INFO', f'[FILTER] 🚫 Rejected {mercari_id}: {item_category} (matched: {blacklisted_cat})', 'filter')
                            except:
                                pass

                            break  # Stop checking other blacklist entries

                # Skip this item if it was rejected (saves ~3-4 seconds per filtered item)
                if item_rejected:
                    continue
                            
                # If we reach here, item passed the category filter
                
                # Get image URL - Item class has .image_url attribute
                image_url = full_item.image_url
                
                # Convert to high-resolution URL
                if image_url:
                    original_url = get_original_image_url(image_url)
                    logger.info(f"[PROCESS] 📸 Image URL: {original_url[:80]}...")
                    image_url = original_url
                    logger.debug(f"[PROCESS] DEBUG: image_url after conversion = {image_url[:100] if image_url else 'NONE'}")
                else:
                    logger.warning(f"[PROCESS] ⚠️ No image URL for item {mercari_id}")

                # Download and encode HIGH-RESOLUTION image
                image_data = None
                logger.debug(f"[PROCESS] DEBUG: Checking image_url = {image_url[:100] if image_url else 'NONE'}, bool={bool(image_url)}")
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

                # Build correct item URL based on ID format
                if mercari_id.startswith('m'):
                    correct_item_url = f"https://jp.mercari.com/item/{mercari_id}"
                else:
                    correct_item_url = f"https://jp.mercari.com/shops/product/{mercari_id}"
                
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
                    item_url=correct_item_url,
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
                    # Convert to dict - check if it's our Item class or raw mercapi object
                    if hasattr(full_item, 'to_dict'):
                        item_dict = full_item.to_dict()
                    else:
                        # Raw mercapi object - create dict manually
                        item_dict = {
                            'mercari_id': mercari_id,
                            'title': full_item.title,
                            'price': full_item.price,
                            'currency': full_item.currency,
                            'item_url': correct_item_url,
                            'image_url': image_url,
                            'brand': full_item.brand,
                            'condition': full_item.condition,
                            'size': full_item.size,
                            'shipping_cost': full_item.shipping_cost,
                            'stock_quantity': full_item.stock_quantity,
                            'seller_name': full_item.seller_name,
                            'seller_rating': full_item.seller_rating,
                            'location': full_item.location,
                            'category': full_item.category,
                            'description': full_item.description
                        }
                    
                    item_dict['db_id'] = db_item_id
                    item_dict['image_data'] = image_data  # Include for notifications
                    new_items.append(item_dict)
                    self.total_items_found += 1
                    
                    # Log new item with title and price
                    item_title = full_item.title[:60] if hasattr(full_item, 'title') else 'Unknown'
                    item_price = full_item.price if hasattr(full_item, 'price') else 0
                    logger.info(f"[PROCESS] ✅ NEW ITEM ADDED: \"{item_title}\" - ¥{item_price:,} (DB ID: {db_item_id})")
                    self.db.add_log_entry('INFO', f"🆕 NEW: {item_title} - ¥{item_price:,}", 'new_item', f"ID: {mercari_id}")
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
