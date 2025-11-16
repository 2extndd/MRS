"""
Metrics storage for MercariSearcher
Adapted from KufarSearcher
"""

import os
import json
import logging
from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MetricsStorage:
    """Persistent metrics storage with PostgreSQL and JSON fallback"""

    def __init__(self):
        self.lock = Lock()
        self.use_database = self._should_use_database()

        if self.use_database:
            from db import get_db
            self.db = get_db()
            logger.info("MetricsStorage using database backend")
        else:
            self.metrics_file = "metrics.json"
            self._init_json_storage()
            logger.info(f"MetricsStorage using JSON file: {self.metrics_file}")

    def _should_use_database(self) -> bool:
        """Determine if database should be used for metrics"""
        # Use database if PostgreSQL is available
        database_url = os.getenv('DATABASE_URL')
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None

        return bool(database_url and 'postgresql' in database_url) or is_railway

    def _init_json_storage(self):
        """Initialize JSON file storage"""
        if not os.path.exists(self.metrics_file):
            initial_data = {
                'app_start_time': datetime.now().isoformat(),
                'total_api_requests': 0,
                'total_items_found': 0,
                'last_search_time': None
            }
            with open(self.metrics_file, 'w') as f:
                json.dump(initial_data, f, indent=2)

    def _get_from_db(self, key: str) -> Optional[str]:
        """Get metric from database"""
        try:
            return self.db.get_setting(key)
        except Exception as e:
            logger.error(f"Failed to get metric from database: {e}")
            return None

    def _set_in_db(self, key: str, value: Any):
        """Set metric in database"""
        try:
            self.db.set_setting(key, str(value))
        except Exception as e:
            logger.error(f"Failed to set metric in database: {e}")

    def _get_from_json(self, key: str) -> Optional[Any]:
        """Get metric from JSON file"""
        try:
            with open(self.metrics_file, 'r') as f:
                data = json.load(f)
            return data.get(key)
        except Exception as e:
            logger.error(f"Failed to get metric from JSON: {e}")
            return None

    def _set_in_json(self, key: str, value: Any):
        """Set metric in JSON file"""
        try:
            with open(self.metrics_file, 'r') as f:
                data = json.load(f)

            data[key] = value

            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to set metric in JSON: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get metric value

        Args:
            key: Metric key
            default: Default value if not found

        Returns:
            Metric value or default
        """
        with self.lock:
            if self.use_database:
                value = self._get_from_db(key)
            else:
                value = self._get_from_json(key)

            return value if value is not None else default

    def set(self, key: str, value: Any):
        """
        Set metric value

        Args:
            key: Metric key
            value: Metric value
        """
        with self.lock:
            if self.use_database:
                self._set_in_db(key, value)
            else:
                self._set_in_json(key, value)

    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment numeric metric

        Args:
            key: Metric key
            amount: Amount to increment

        Returns:
            New value
        """
        with self.lock:
            current = self.get(key, 0)

            # Convert to int if string
            if isinstance(current, str):
                try:
                    current = int(current)
                except ValueError:
                    current = 0

            new_value = current + amount
            self.set(key, new_value)
            return new_value

    def increment_api_requests(self) -> int:
        """Increment API request counter"""
        return self.increment('total_api_requests')

    def increment_items_found(self, count: int = 1) -> int:
        """Increment items found counter"""
        return self.increment('total_items_found', count)

    def set_last_search_time(self, timestamp: Optional[str] = None):
        """Set last search timestamp"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        self.set('last_search_time', timestamp)

    def get_app_start_time(self) -> Optional[str]:
        """Get application start time"""
        return self.get('app_start_time')

    def get_total_api_requests(self) -> int:
        """Get total API requests"""
        value = self.get('total_api_requests', 0)
        return int(value) if value else 0

    def get_total_items_found(self) -> int:
        """Get total items found"""
        value = self.get('total_items_found', 0)
        return int(value) if value else 0

    def get_last_search_time(self) -> Optional[str]:
        """Get last search time"""
        return self.get('last_search_time')

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            'app_start_time': self.get_app_start_time(),
            'total_api_requests': self.get_total_api_requests(),
            'total_items_found': self.get_total_items_found(),
            'last_search_time': self.get_last_search_time(),
        }

    def reset_stats(self):
        """Reset all statistics"""
        with self.lock:
            self.set('total_api_requests', 0)
            self.set('total_items_found', 0)
            self.set('last_search_time', None)
            logger.info("Metrics reset")


# Global metrics storage instance
metrics_storage = MetricsStorage()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Metrics Storage Test ===")

    # Test metrics
    metrics_storage.increment_api_requests()
    metrics_storage.increment_api_requests()
    metrics_storage.increment_items_found(5)
    metrics_storage.set_last_search_time()

    print("\nAll Stats:")
    stats = metrics_storage.get_all_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
