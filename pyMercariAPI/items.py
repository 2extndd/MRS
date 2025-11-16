"""
Item and Items classes for Mercari data
"""

from typing import List, Dict, Any, Optional


class Item:
    """Represents a single Mercari item"""

    def __init__(self, data: Dict[str, Any]):
        self.raw_data = data

        # Core fields
        self.id = str(data.get('mercari_id', ''))
        self.title = data.get('title', '')
        self.price = data.get('price', 0)
        self.currency = data.get('currency', 'JPY')
        self.url = data.get('item_url', '')
        self.image_url = data.get('image_url')

        # Additional fields
        self.brand = data.get('brand')
        self.condition = data.get('condition')
        self.size = data.get('size')
        self.shipping_cost = data.get('shipping_cost', 0)
        self.stock_quantity = data.get('stock_quantity', 1)

        # Seller information
        self.seller_name = data.get('seller_name')
        self.seller_rating = data.get('seller_rating')

        # Location and category
        self.location = data.get('location')
        self.category = data.get('category')

        # Description
        self.description = data.get('description', '')

    def __repr__(self):
        return f"<Item {self.id}: {self.title[:30]}... ¥{self.price}>"

    def __str__(self):
        return f"{self.title} - ¥{self.price}"

    @property
    def price_usd(self) -> float:
        """Get price in USD"""
        from configuration_values import config
        return round(self.price * config.USD_CONVERSION_RATE, 2)

    @property
    def total_price(self) -> int:
        """Get total price including shipping"""
        return self.price + (self.shipping_cost or 0)

    @property
    def total_price_usd(self) -> float:
        """Get total price in USD"""
        from configuration_values import config
        return round(self.total_price * config.USD_CONVERSION_RATE, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert item to dictionary"""
        return {
            'mercari_id': self.id,
            'title': self.title,
            'price': self.price,
            'currency': self.currency,
            'item_url': self.url,
            'image_url': self.image_url,
            'brand': self.brand,
            'condition': self.condition,
            'size': self.size,
            'shipping_cost': self.shipping_cost,
            'stock_quantity': self.stock_quantity,
            'seller_name': self.seller_name,
            'seller_rating': self.seller_rating,
            'location': self.location,
            'category': self.category,
            'description': self.description
        }

    def get_display_info(self) -> Dict[str, Any]:
        """Get formatted display information"""
        from configuration_values import config

        info = {
            'title': self.title,
            'price_jpy': f"¥{self.price:,}",
            'price_usd': f"${self.price_usd}",
            'url': self.url,
            'image': self.image_url
        }

        if self.brand:
            info['brand'] = self.brand

        if self.condition:
            info['condition'] = self.condition

        if self.size:
            info['size'] = self.size

        if self.shipping_cost:
            info['shipping'] = f"¥{self.shipping_cost:,}"

        if self.seller_name:
            info['seller'] = self.seller_name

        if self.location:
            info['location'] = self.location

        return info


class Items:
    """Container for multiple Mercari items"""

    def __init__(self, items: Optional[List[Dict[str, Any]]] = None):
        self.items: List[Item] = []

        if items:
            for item_data in items:
                self.add_item(item_data)

    def add_item(self, item_data: Dict[str, Any]):
        """Add item to collection"""
        if isinstance(item_data, Item):
            self.items.append(item_data)
        else:
            self.items.append(Item(item_data))

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def __repr__(self):
        return f"<Items count={len(self.items)}>"

    def filter_by_price(self, min_price: Optional[int] = None,
                       max_price: Optional[int] = None) -> 'Items':
        """Filter items by price range"""
        filtered = Items()

        for item in self.items:
            if min_price and item.price < min_price:
                continue
            if max_price and item.price > max_price:
                continue
            filtered.add_item(item)

        return filtered

    def filter_by_brand(self, brand: str) -> 'Items':
        """Filter items by brand"""
        filtered = Items()

        for item in self.items:
            if item.brand and brand.lower() in item.brand.lower():
                filtered.add_item(item)

        return filtered

    def filter_by_condition(self, condition: str) -> 'Items':
        """Filter items by condition"""
        filtered = Items()

        for item in self.items:
            if item.condition and condition.lower() in item.condition.lower():
                filtered.add_item(item)

        return filtered

    def sort_by_price(self, reverse: bool = False) -> 'Items':
        """Sort items by price"""
        sorted_items = Items()
        sorted_list = sorted(self.items, key=lambda x: x.price, reverse=reverse)

        for item in sorted_list:
            sorted_items.add_item(item)

        return sorted_items

    def to_list(self) -> List[Dict[str, Any]]:
        """Convert to list of dictionaries"""
        return [item.to_dict() for item in self.items]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about items"""
        if not self.items:
            return {
                'count': 0,
                'min_price': 0,
                'max_price': 0,
                'avg_price': 0,
                'total_value': 0
            }

        prices = [item.price for item in self.items]

        return {
            'count': len(self.items),
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': sum(prices) // len(prices),
            'total_value': sum(prices)
        }


if __name__ == "__main__":
    # Test items
    test_data = [
        {
            'mercari_id': '12345',
            'title': 'Nike Air Max',
            'price': 15000,
            'item_url': 'https://jp.mercari.com/item/12345',
            'brand': 'Nike'
        },
        {
            'mercari_id': '67890',
            'title': 'Adidas Shoes',
            'price': 8000,
            'item_url': 'https://jp.mercari.com/item/67890',
            'brand': 'Adidas'
        }
    ]

    items = Items(test_data)
    print(f"Items: {items}")
    print(f"Statistics: {items.get_statistics()}")

    # Test filtering
    nike_items = items.filter_by_brand('Nike')
    print(f"Nike items: {nike_items}")
