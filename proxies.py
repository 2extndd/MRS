"""
Proxy management for MercariSearcher
Copied from KufarSearcher with Mercari URL adaptation
"""

import requests
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from configuration_values import config

logger = logging.getLogger(__name__)


class ProxyManager:
    """Manages proxy validation and rotation"""

    def __init__(self, proxies: List[str]):
        """
        Initialize proxy manager

        Args:
            proxies: List of proxy URLs
        """
        self.all_proxies = proxies
        self.working_proxies = []
        self.failed_proxies = []
        self.last_validation_time = 0
        self.validation_interval = 3600  # 1 hour

        if proxies:
            logger.info(f"ProxyManager initialized with {len(proxies)} proxies")
            self.validate_proxies()
        else:
            logger.info("ProxyManager initialized with no proxies")

    def validate_proxies(self, max_workers: int = 10):
        """
        Validate all proxies in parallel

        Args:
            max_workers: Maximum parallel workers
        """
        if not self.all_proxies:
            return

        logger.info(f"Validating {len(self.all_proxies)} proxies...")

        working = []
        failed = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {
                executor.submit(self._test_proxy, proxy): proxy
                for proxy in self.all_proxies
            }

            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    is_working = future.result()
                    if is_working:
                        working.append(proxy)
                    else:
                        failed.append(proxy)
                except Exception as e:
                    logger.error(f"Proxy validation error for {proxy}: {e}")
                    failed.append(proxy)

        self.working_proxies = working
        self.failed_proxies = failed
        self.last_validation_time = time.time()

        logger.info(f"Proxy validation complete: {len(working)} working, {len(failed)} failed")

    def _test_proxy(self, proxy: str, timeout: int = 10) -> bool:
        """
        Test single proxy

        Args:
            proxy: Proxy URL
            timeout: Request timeout

        Returns:
            True if proxy works
        """
        try:
            proxies = {
                'http': proxy,
                'https': proxy
            }

            # Test against Mercari.jp
            response = requests.get(
                config.MERCARI_BASE_URL,
                proxies=proxies,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            )

            return response.status_code == 200

        except Exception as e:
            logger.debug(f"Proxy {proxy} failed: {e}")
            return False

    def get_proxy(self, random_choice: bool = False) -> Optional[str]:
        """
        Get working proxy

        Args:
            random_choice: Use random selection instead of rotation

        Returns:
            Proxy URL or None
        """
        # Revalidate if needed
        if time.time() - self.last_validation_time > self.validation_interval:
            self.revalidate_failed_proxies()

        if not self.working_proxies:
            logger.warning("No working proxies available")
            return None

        if random_choice:
            import random
            return random.choice(self.working_proxies)
        else:
            # Rotate: move first to end
            proxy = self.working_proxies.pop(0)
            self.working_proxies.append(proxy)
            return proxy

    def mark_proxy_failed(self, proxy: str):
        """
        Mark proxy as failed

        Args:
            proxy: Proxy URL
        """
        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            self.failed_proxies.append(proxy)
            logger.info(f"Proxy marked as failed: {proxy}")

    def revalidate_failed_proxies(self):
        """Re-test failed proxies and move working ones back"""
        if not self.failed_proxies:
            return

        logger.info(f"Re-testing {len(self.failed_proxies)} failed proxies...")

        recovered = []
        still_failed = []

        for proxy in self.failed_proxies:
            if self._test_proxy(proxy):
                recovered.append(proxy)
                self.working_proxies.append(proxy)
            else:
                still_failed.append(proxy)

        self.failed_proxies = still_failed
        self.last_validation_time = time.time()

        if recovered:
            logger.info(f"Recovered {len(recovered)} proxies")

    def get_proxy_stats(self) -> Dict:
        """Get proxy statistics"""
        return {
            'total': len(self.all_proxies),
            'working': len(self.working_proxies),
            'failed': len(self.failed_proxies),
            'last_validation': self.last_validation_time
        }


class ProxyRotator:
    """Simple proxy rotator for requests"""

    def __init__(self, proxy_manager: ProxyManager, rotation_count: int = 100):
        """
        Initialize proxy rotator

        Args:
            proxy_manager: ProxyManager instance
            rotation_count: Rotate proxy after N requests
        """
        self.proxy_manager = proxy_manager
        self.rotation_count = rotation_count
        self.current_proxy = None
        self.request_count = 0

        # Get initial proxy
        if self.proxy_manager.working_proxies:
            self.current_proxy = self.proxy_manager.get_proxy()

    def get_proxy(self) -> Optional[Dict]:
        """
        Get current proxy for requests

        Returns:
            Proxy dict for requests library or None
        """
        # Rotate if needed
        if self.request_count >= self.rotation_count:
            self.current_proxy = self.proxy_manager.get_proxy()
            self.request_count = 0

        self.request_count += 1

        if self.current_proxy:
            return {
                'http': self.current_proxy,
                'https': self.current_proxy
            }
        return None

    def mark_current_failed(self):
        """Mark current proxy as failed and get new one"""
        if self.current_proxy:
            self.proxy_manager.mark_proxy_failed(self.current_proxy)
            self.current_proxy = self.proxy_manager.get_proxy()
            self.request_count = 0


# Initialize global proxy manager
proxy_manager = None
proxy_rotator = None

if config.PROXY_ENABLED and config.PROXY_LIST:
    logger.info("Initializing proxy system...")
    proxy_manager = ProxyManager(config.PROXY_LIST)

    if proxy_manager.working_proxies:
        proxy_rotator = ProxyRotator(proxy_manager)
        logger.info("Proxy rotator initialized")
    else:
        logger.warning("No working proxies found")
else:
    logger.info("Proxy system disabled")


if __name__ == "__main__":
    # Test proxy manager
    logging.basicConfig(level=logging.INFO)

    test_proxies = [
        'http://proxy1.example.com:8080',
        'http://proxy2.example.com:8080',
    ]

    manager = ProxyManager(test_proxies)
    print(f"\nProxy Stats: {manager.get_proxy_stats()}")

    if manager.working_proxies:
        print(f"First working proxy: {manager.get_proxy()}")
