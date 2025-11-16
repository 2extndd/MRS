"""
Mercari.jp Web Scraper
Adapted from KufarSearcher kufar_scraper.py

Since Mercari.jp doesn't have a public API, this scraper extracts data
from HTML and JavaScript state objects embedded in the page.
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
from configuration_values import config

logger = logging.getLogger(__name__)


class MercariScraper:
    """Scraper for Mercari.jp marketplace"""

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.session = requests.Session()
        self.ua = UserAgent()
        self.setup_session()

    def setup_session(self):
        """Setup session with headers and proxy"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        if self.proxy:
            self.session.proxies.update({
                'http': self.proxy,
                'https': self.proxy
            })

    def get_page(self, url):
        """Fetch page content"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch page {url}: {e}")
            return None

    def extract_initial_state(self, html):
        """
        Extract __INITIAL_STATE__ from Mercari's Next.js app
        Mercari uses React/Next.js and stores data in window.__INITIAL_STATE__
        """
        try:
            # Find script tag containing __INITIAL_STATE__
            soup = BeautifulSoup(html, 'lxml')
            scripts = soup.find_all('script')

            for script in scripts:
                if script.string and '__INITIAL_STATE__' in script.string:
                    # Extract JSON object
                    match = re.search(r'__INITIAL_STATE__\s*=\s*({.+?});', script.string, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        return json.loads(json_str)

            logger.warning("Could not find __INITIAL_STATE__ in page")
            return None

        except Exception as e:
            logger.error(f"Failed to extract initial state: {e}")
            return None

    def search_items(self, search_url, limit=50):
        """
        Search for items on Mercari.jp
        Returns list of item dictionaries
        """
        html = self.get_page(search_url)
        if not html:
            return []

        # Try to extract from __INITIAL_STATE__
        initial_state = self.extract_initial_state(html)
        if initial_state:
            items = self.parse_search_results_from_state(initial_state, limit)
            if items:
                return items

        # Fallback to HTML parsing
        logger.info("Falling back to HTML parsing")
        return self.parse_search_results_from_html(html, limit)

    def parse_search_results_from_state(self, state, limit=50):
        """Parse search results from __INITIAL_STATE__"""
        try:
            items = []

            # Navigate state object structure
            # Structure varies, but typically: state.search.results or state.items
            search_data = state.get('search', {})
            results = search_data.get('results', [])

            if not results:
                # Try alternative paths
                results = state.get('items', [])
                if not results:
                    results = state.get('searchResults', {}).get('data', [])

            for item_data in results[:limit]:
                item = self.parse_item_from_state_object(item_data)
                if item:
                    items.append(item)

            logger.info(f"Extracted {len(items)} items from state object")
            return items

        except Exception as e:
            logger.error(f"Failed to parse state object: {e}")
            return []

    def parse_item_from_state_object(self, item_data):
        """Parse individual item from state object"""
        try:
            item_id = item_data.get('id')
            if not item_id:
                return None

            item = {
                'mercari_id': str(item_id),
                'title': item_data.get('name', ''),
                'price': item_data.get('price', 0),
                'currency': 'JPY',
                'item_url': f"{config.MERCARI_BASE_URL}/item/{item_id}",
                'image_url': self.extract_image_url(item_data),
                'brand': item_data.get('brand', {}).get('name') if isinstance(item_data.get('brand'), dict) else item_data.get('brand'),
                'condition': item_data.get('itemCondition', {}).get('name') if isinstance(item_data.get('itemCondition'), dict) else item_data.get('condition'),
                'seller_name': item_data.get('seller', {}).get('name') if isinstance(item_data.get('seller'), dict) else None,
                'seller_rating': item_data.get('seller', {}).get('rating') if isinstance(item_data.get('seller'), dict) else None,
                'stock_quantity': item_data.get('stock', 1),
                'shipping_cost': item_data.get('shippingCost', 0),
                'size': item_data.get('size'),
                'location': item_data.get('region', {}).get('name') if isinstance(item_data.get('region'), dict) else item_data.get('location'),
                'category': item_data.get('category', {}).get('name') if isinstance(item_data.get('category'), dict) else None,
                'description': item_data.get('description', '')[:500]  # Limit description
            }

            return item

        except Exception as e:
            logger.error(f"Failed to parse item object: {e}")
            return None

    def extract_image_url(self, item_data):
        """Extract primary image URL from item data"""
        try:
            # Try different image field names
            if 'thumbnails' in item_data and item_data['thumbnails']:
                return item_data['thumbnails'][0]

            if 'photos' in item_data and item_data['photos']:
                return item_data['photos'][0].get('url') if isinstance(item_data['photos'][0], dict) else item_data['photos'][0]

            if 'image' in item_data:
                return item_data['image'].get('url') if isinstance(item_data['image'], dict) else item_data['image']

            if 'imageUrl' in item_data:
                return item_data['imageUrl']

            return None

        except Exception as e:
            logger.error(f"Failed to extract image URL: {e}")
            return None

    def parse_search_results_from_html(self, html, limit=50):
        """Fallback HTML parsing for search results"""
        try:
            soup = BeautifulSoup(html, 'lxml')
            items = []

            # Find item cards (adjust selector based on actual Mercari HTML structure)
            item_cards = soup.find_all('div', class_=re.compile(r'(item-card|product-card|search-result-item)'), limit=limit)

            if not item_cards:
                # Try alternative selectors
                item_cards = soup.find_all('li', {'data-testid': re.compile(r'item.*')}, limit=limit)

            for card in item_cards:
                item = self.parse_item_card_from_html(card)
                if item:
                    items.append(item)

            logger.info(f"Extracted {len(items)} items from HTML")
            return items

        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return []

    def parse_item_card_from_html(self, card):
        """Parse item card from HTML"""
        try:
            # Extract item ID from link
            link = card.find('a', href=re.compile(r'/item/'))
            if not link:
                return None

            item_url = link.get('href')
            if not item_url.startswith('http'):
                item_url = config.MERCARI_BASE_URL + item_url

            # Extract ID from URL
            id_match = re.search(r'/item/([a-zA-Z0-9]+)', item_url)
            if not id_match:
                return None

            mercari_id = id_match.group(1)

            # Extract title
            title_elem = card.find(['h3', 'h2', 'div'], class_=re.compile(r'(title|name)'))
            title = title_elem.get_text(strip=True) if title_elem else 'No title'

            # Extract price
            price_elem = card.find(['span', 'div'], class_=re.compile(r'price'))
            price_text = price_elem.get_text(strip=True) if price_elem else '0'
            price = self.extract_price_from_text(price_text)

            # Extract image
            img = card.find('img')
            image_url = img.get('src') or img.get('data-src') if img else None

            item = {
                'mercari_id': mercari_id,
                'title': title,
                'price': price,
                'currency': 'JPY',
                'item_url': item_url,
                'image_url': image_url,
                'brand': None,
                'condition': None,
                'seller_name': None,
                'seller_rating': None,
                'stock_quantity': 1,
                'shipping_cost': 0,
                'size': None,
                'location': None,
                'category': None,
                'description': ''
            }

            return item

        except Exception as e:
            logger.error(f"Failed to parse item card: {e}")
            return None

    def extract_price_from_text(self, text):
        """Extract numeric price from text like '¥1,500' or '1500円'"""
        try:
            # Remove currency symbols and commas
            clean_text = re.sub(r'[¥,円]', '', text)
            # Extract number
            match = re.search(r'\d+', clean_text)
            if match:
                return int(match.group())
            return 0
        except:
            return 0

    def get_item_details(self, item_url):
        """
        Get detailed information for a specific item
        Returns item dict with full details
        """
        html = self.get_page(item_url)
        if not html:
            return None

        # Try to extract from __INITIAL_STATE__
        initial_state = self.extract_initial_state(html)
        if initial_state:
            item = self.parse_item_details_from_state(initial_state)
            if item:
                return item

        # Fallback to HTML parsing
        return self.parse_item_details_from_html(html, item_url)

    def parse_item_details_from_state(self, state):
        """Parse item details from __INITIAL_STATE__"""
        try:
            # Navigate state to find item data
            item_data = state.get('item', {})

            if not item_data:
                # Try alternative paths
                item_data = state.get('itemDetail', {})

            if not item_data:
                return None

            return self.parse_item_from_state_object(item_data)

        except Exception as e:
            logger.error(f"Failed to parse item details from state: {e}")
            return None

    def parse_item_details_from_html(self, html, item_url):
        """Parse item details from HTML"""
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract item ID from URL
            id_match = re.search(r'/item/([a-zA-Z0-9]+)', item_url)
            mercari_id = id_match.group(1) if id_match else None

            if not mercari_id:
                return None

            # Extract title
            title_elem = soup.find('h1') or soup.find(['h2', 'h3'])
            title = title_elem.get_text(strip=True) if title_elem else 'No title'

            # Extract price
            price_elem = soup.find(['span', 'div'], class_=re.compile(r'price'))
            price_text = price_elem.get_text(strip=True) if price_elem else '0'
            price = self.extract_price_from_text(price_text)

            # Extract description
            desc_elem = soup.find(['div', 'p'], class_=re.compile(r'(description|detail)'))
            description = desc_elem.get_text(strip=True) if desc_elem else ''

            # Extract image
            img = soup.find('img', class_=re.compile(r'(item-image|product-image)'))
            if not img:
                img = soup.find('img', src=re.compile(r'(item|product)'))
            image_url = img.get('src') or img.get('data-src') if img else None

            item = {
                'mercari_id': mercari_id,
                'title': title,
                'price': price,
                'currency': 'JPY',
                'item_url': item_url,
                'image_url': image_url,
                'description': description[:500],
                'brand': None,
                'condition': None,
                'seller_name': None,
                'seller_rating': None,
                'stock_quantity': 1,
                'shipping_cost': 0,
                'size': None,
                'location': None,
                'category': None
            }

            return item

        except Exception as e:
            logger.error(f"Failed to parse item details from HTML: {e}")
            return None

    def extract_size_from_text(self, text):
        """
        Extract clothing size from Japanese or international text
        Supports: XS, S, M, L, XL, XXL, FREE, and Japanese equivalents
        """
        if not text:
            return None

        text_upper = text.upper()

        # Check international sizes
        for size, variants in config.SIZE_MAPPINGS.items():
            for variant in variants:
                if variant.upper() in text_upper:
                    return size

        # Check numeric sizes (e.g., 38, 40, 42 for EU sizes)
        size_match = re.search(r'\b([3-5][0-9])\b', text)
        if size_match:
            return size_match.group(1)

        return None


class Item:
    """Item data class compatible with pyMercariAPI"""

    def __init__(self, data):
        self.id = data.get('mercari_id')
        self.title = data.get('title')
        self.price = data.get('price')
        self.currency = data.get('currency', 'JPY')
        self.url = data.get('item_url')
        self.image_url = data.get('image_url')
        self.brand = data.get('brand')
        self.condition = data.get('condition')
        self.seller_name = data.get('seller_name')
        self.seller_rating = data.get('seller_rating')
        self.stock_quantity = data.get('stock_quantity', 1)
        self.shipping_cost = data.get('shipping_cost', 0)
        self.size = data.get('size')
        self.location = data.get('location')
        self.category = data.get('category')
        self.description = data.get('description', '')

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'mercari_id': self.id,
            'title': self.title,
            'price': self.price,
            'currency': self.currency,
            'item_url': self.url,
            'image_url': self.image_url,
            'brand': self.brand,
            'condition': self.condition,
            'seller_name': self.seller_name,
            'seller_rating': self.seller_rating,
            'stock_quantity': self.stock_quantity,
            'shipping_cost': self.shipping_cost,
            'size': self.size,
            'location': self.location,
            'category': self.category,
            'description': self.description
        }


if __name__ == "__main__":
    # Test scraper
    logging.basicConfig(level=logging.INFO)

    scraper = MercariScraper()

    # Test search
    print("Testing search...")
    search_url = "https://jp.mercari.com/search?keyword=ナイキ"  # Nike
    items = scraper.search_items(search_url, limit=5)

    print(f"\nFound {len(items)} items:")
    for item in items:
        print(f"- {item['title'][:50]} - ¥{item['price']}")
