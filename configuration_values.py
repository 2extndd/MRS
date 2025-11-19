"""
Configuration values for MercariSearcher (MRS)
Adapted from KufarSearcher for Mercari.jp marketplace
"""

import os
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for Mercari Scanner with hot reload support"""

    # Application Info
    APP_NAME = "MercariSearcher"
    APP_VERSION = "1.0.1"  # Force Worker restart to reload proxy config
    APP_DESCRIPTION = "Automated Mercari.jp item monitoring with Telegram notifications"

    # Mercari Settings
    MERCARI_BASE_URL = "https://jp.mercari.com"
    MERCARI_API_URL = "https://api.mercari.jp/v2"
    MERCARI_SEARCH_URL = f"{MERCARI_BASE_URL}/search"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "mercari_scanner.db")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_THREAD_ID = os.getenv("TELEGRAM_THREAD_ID")  # For topics/threads

    # Search Settings (defaults, can be overridden in DB)
    SEARCH_INTERVAL = int(os.getenv("SEARCH_INTERVAL", "300"))  # 5 minutes
    MAX_ITEMS_PER_SEARCH = int(os.getenv("MAX_ITEMS_PER_SEARCH", "50"))

    # Rate Limiting
    REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "1.5"))
    REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "3.5"))

    # Proxy Settings
    PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true"
    # Support both newline and comma-separated proxies
    PROXY_LIST = [p.strip() for p in os.getenv("PROXY_LIST", "").replace('\n', ',').split(",") if p.strip()] if os.getenv("PROXY_LIST") else []

    # Railway Auto-Redeploy
    RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN")
    RAILWAY_PROJECT_ID = os.getenv("RAILWAY_PROJECT_ID")
    RAILWAY_SERVICE_ID = os.getenv("RAILWAY_SERVICE_ID")
    MAX_ERRORS_BEFORE_REDEPLOY = int(os.getenv("MAX_ERRORS_BEFORE_REDEPLOY", "5"))

    # Web UI
    PORT = int(os.getenv("PORT", "5000"))
    WEB_UI_HOST = os.getenv("WEB_UI_HOST", "0.0.0.0")
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "mercari_scanner.log")

    # Hot reload state
    _config_cache = {}
    _last_reload_time = 0
    _reload_interval = 10  # Check every 10 seconds

    # Currency Settings
    DEFAULT_CURRENCY = "JPY"
    CURRENCY_SYMBOL = "¥"
    USD_CONVERSION_RATE = float(os.getenv("USD_CONVERSION_RATE", "0.0067"))  # JPY to USD
    DISPLAY_CURRENCY = os.getenv("DISPLAY_CURRENCY", "USD")  # USD or JPY

    # Japanese Text Processing
    ENCODING = "utf-8"

    # Mercari-specific
    MERCARI_CATEGORIES = {
        "3088": "Men's Fashion",
        "3089": "Women's Fashion",
        "3090": "Kids Fashion",
        "3091": "Electronics",
        "3092": "Home & Living",
        "3093": "Entertainment",
        "3094": "Toys & Hobbies",
        "3095": "Sports & Outdoors",
        "3096": "Handmade",
        "3097": "Beauty & Health",
        "3098": "Other"
    }

    # Size Mappings (Japanese to International)
    SIZE_MAPPINGS = {
        "XS": ["XS", "エックスエス"],
        "S": ["S", "エス", "小"],
        "M": ["M", "エム", "中"],
        "L": ["L", "エル", "大"],
        "XL": ["XL", "エックスエル", "特大"],
        "XXL": ["XXL", "2XL", "エックスエックスエル"],
        "FREE": ["FREE", "フリー", "F"]
    }

    @classmethod
    def get_display_price(cls, jpy_price):
        """Convert JPY price to display currency"""
        if cls.DISPLAY_CURRENCY == "USD":
            return round(jpy_price * cls.USD_CONVERSION_RATE, 2)
        return jpy_price

    @classmethod
    def get_currency_symbol(cls):
        """Get currency symbol for display"""
        if cls.DISPLAY_CURRENCY == "USD":
            return "$"
        return cls.CURRENCY_SYMBOL

    @classmethod
    def reload_if_needed(cls):
        """Hot reload config from database if enough time has passed"""
        current_time = time.time()

        if current_time - cls._last_reload_time < cls._reload_interval:
            return False  # Too soon to check again

        cls._last_reload_time = current_time

        try:
            # Import here to avoid circular dependency
            from db import get_db

            db = get_db()
            new_config = db.get_all_config()

            # Compare only config values, not metadata like updated_at
            # Filter to only config_ keys
            config_keys = [k for k in new_config.keys() if k.startswith('config_')]
            
            # Check if config actually changed by comparing with cached DB values
            config_changed = False
            if cls._config_cache is None:
                config_changed = True  # First load
                cls._config_cache = {}  # Initialize empty cache
            else:
                # Compare ONLY config_ keys from database
                for key in config_keys:
                    old_val = cls._config_cache.get(key)
                    new_val = new_config.get(key)
                    if old_val != new_val:
                        config_changed = True
                        break
            
            if config_changed:
                logger.info(f"[CONFIG] Configuration changed, hot reloading... Keys in DB: {config_keys}")

                # Update runtime settings from database
                # Check both old and new key names for compatibility
                if 'config_search_interval' in new_config:
                    old_val = cls.SEARCH_INTERVAL
                    new_val = int(new_config['config_search_interval'])
                    if old_val != new_val:
                        cls.SEARCH_INTERVAL = new_val
                        logger.info(f"[config] Search interval changed: {old_val}s → {cls.SEARCH_INTERVAL}s")
                    else:
                        cls.SEARCH_INTERVAL = new_val  # Update anyway but don't log
                elif 'config_scan_interval' in new_config:
                    old_val = cls.SEARCH_INTERVAL
                    new_val = int(new_config['config_scan_interval'])
                    if old_val != new_val:
                        cls.SEARCH_INTERVAL = new_val
                        logger.info(f"[config] Search interval changed: {old_val}s → {cls.SEARCH_INTERVAL}s")

                if 'config_max_items_per_search' in new_config:
                    old_val = cls.MAX_ITEMS_PER_SEARCH
                    new_val = int(new_config['config_max_items_per_search'])
                    if old_val != new_val:
                        cls.MAX_ITEMS_PER_SEARCH = new_val
                        logger.info(f"[config] Max items per search changed: {old_val} → {cls.MAX_ITEMS_PER_SEARCH}")
                    else:
                        cls.MAX_ITEMS_PER_SEARCH = new_val  # Update anyway but don't log
                elif 'config_max_items' in new_config:
                    old_val = cls.MAX_ITEMS_PER_SEARCH
                    new_val = int(new_config['config_max_items'])
                    if old_val != new_val:
                        cls.MAX_ITEMS_PER_SEARCH = new_val
                        logger.info(f"[config] Max items per search changed: {old_val} → {cls.MAX_ITEMS_PER_SEARCH}")

                if 'config_request_delay' in new_config:
                    cls.REQUEST_DELAY_MIN = float(new_config['config_request_delay'])
                    cls.REQUEST_DELAY_MAX = float(new_config['config_request_delay']) + 2.0
                    logger.info(f"[CONFIG] REQUEST_DELAY: {cls.REQUEST_DELAY_MIN}-{cls.REQUEST_DELAY_MAX}s")

                # Proxy settings (hot reload with proxy_manager reinit)
                proxy_config_changed = False

                if 'config_proxy_enabled' in new_config:
                    old_enabled = cls.PROXY_ENABLED
                    cls.PROXY_ENABLED = str(new_config['config_proxy_enabled']).lower() == 'true'
                    logger.info(f"[CONFIG] PROXY_ENABLED: {old_enabled} → {cls.PROXY_ENABLED}")
                    if old_enabled != cls.PROXY_ENABLED:
                        proxy_config_changed = True

                if 'config_proxy_list' in new_config:
                    old_count = len(cls.PROXY_LIST)
                    proxy_str = str(new_config['config_proxy_list'])
                    # Parse proxies from newline-separated string
                    cls.PROXY_LIST = [p.strip() for p in proxy_str.replace('\n', ',').split(",") if p.strip()]
                    new_count = len(cls.PROXY_LIST)
                    logger.info(f"[CONFIG] PROXY_LIST: {old_count} → {new_count} proxies")
                    if old_count != new_count:
                        proxy_config_changed = True

                # Reinitialize proxy_manager if proxy config changed
                if proxy_config_changed:
                    logger.warning(f"[CONFIG] ⚠️  Proxy configuration changed! Reinitializing proxy system...")
                    try:
                        # Import here to avoid circular dependency
                        import proxies

                        if cls.PROXY_ENABLED and cls.PROXY_LIST:
                            logger.info(f"[CONFIG] 🔄 Initializing proxy system with {len(cls.PROXY_LIST)} proxies...")
                            proxies.proxy_manager = proxies.ProxyManager(cls.PROXY_LIST)

                            if proxies.proxy_manager.working_proxies:
                                proxies.proxy_rotator = proxies.ProxyRotator(proxies.proxy_manager)
                                stats = proxies.proxy_manager.get_proxy_stats()
                                logger.info(f"[CONFIG] ✅ Proxy system initialized: {stats['working']} working, {stats['failed']} failed")

                                # Log to Web UI
                                try:
                                    from db import get_db
                                    db = get_db()
                                    db.add_log_entry('INFO',
                                        f"Proxy system initialized: {stats['working']} working, {stats['failed']} failed (tested against CDN)",
                                        'proxy')
                                except Exception as e:
                                    logger.error(f"Failed to log proxy init to DB: {e}")
                            else:
                                logger.warning(f"[CONFIG] ⚠️  No working proxies found after validation")
                                proxies.proxy_rotator = None

                                # Log to Web UI
                                try:
                                    from db import get_db
                                    db = get_db()
                                    db.add_log_entry('WARNING',
                                        f"No working proxies found after validation (tested {len(cls.PROXY_LIST)} proxies)",
                                        'proxy')
                                except Exception as e:
                                    logger.error(f"Failed to log proxy warning to DB: {e}")
                        else:
                            logger.info(f"[CONFIG] Proxy system disabled")
                            proxies.proxy_manager = None
                            proxies.proxy_rotator = None
                    except Exception as e:
                        logger.error(f"[CONFIG] ❌ Failed to reinitialize proxy system: {e}")

                # Telegram settings (hot reload)
                if 'config_telegram_bot_token' in new_config:
                    old_val = cls.TELEGRAM_BOT_TOKEN
                    new_val = str(new_config['config_telegram_bot_token'])
                    if new_val and new_val != 'None':
                        cls.TELEGRAM_BOT_TOKEN = new_val
                        logger.info(f"[CONFIG] ✅ TELEGRAM_BOT_TOKEN updated (length: {len(new_val)})")
                        if not old_val:
                            logger.warning(f"[CONFIG] ⚠️  Bot token was NOT set before, now configured!")

                if 'config_telegram_chat_id' in new_config:
                    old_val = cls.TELEGRAM_CHAT_ID
                    new_val = str(new_config['config_telegram_chat_id'])
                    if new_val and new_val != 'None':
                        cls.TELEGRAM_CHAT_ID = new_val
                        logger.info(f"[CONFIG] ✅ TELEGRAM_CHAT_ID: {cls.TELEGRAM_CHAT_ID}")
                        if not old_val:
                            logger.warning(f"[CONFIG] ⚠️  Chat ID was NOT set before, now configured!")

                # USD conversion rate
                if 'config_usd_conversion_rate' in new_config:
                    old_val = cls.USD_CONVERSION_RATE
                    cls.USD_CONVERSION_RATE = float(new_config['config_usd_conversion_rate'])
                    logger.info(f"[CONFIG] USD_CONVERSION_RATE: {old_val} → {cls.USD_CONVERSION_RATE}")

                cls._config_cache = new_config
                logger.info(f"[CONFIG] ✅ Hot reload complete! search_interval={cls.SEARCH_INTERVAL}s, max_items={cls.MAX_ITEMS_PER_SEARCH}")
                return True

        except Exception as e:
            logger.error(f"[CONFIG] Hot reload failed: {e}")

        return False

    @classmethod
    def validate_config(cls):
        """Validate required configuration"""
        errors = []

        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required")

        return errors


# Global config instance
config = Config()


def get_config():
    """Get global config instance"""
    return config


if __name__ == "__main__":
    # Validate configuration
    errors = config.validate_config()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuration is valid")
        print(f"App: {config.APP_NAME} v{config.APP_VERSION}")
        print(f"Mercari URL: {config.MERCARI_BASE_URL}")
        print(f"Display Currency: {config.DISPLAY_CURRENCY}")
