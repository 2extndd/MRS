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
    APP_VERSION = "1.0.0"
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
    PROXY_LIST = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []

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

            if new_config != cls._config_cache:
                logger.info("[CONFIG] Configuration changed, hot reloading...")

                # Update runtime settings from database
                # Check both old and new key names for compatibility
                if 'config_search_interval' in new_config:
                    cls.SEARCH_INTERVAL = int(new_config['config_search_interval'])
                elif 'config_scan_interval' in new_config:
                    cls.SEARCH_INTERVAL = int(new_config['config_scan_interval'])

                if 'config_max_items_per_search' in new_config:
                    cls.MAX_ITEMS_PER_SEARCH = int(new_config['config_max_items_per_search'])
                elif 'config_max_items' in new_config:
                    cls.MAX_ITEMS_PER_SEARCH = int(new_config['config_max_items'])

                if 'config_request_delay' in new_config:
                    cls.REQUEST_DELAY_MIN = float(new_config['config_request_delay'])
                    cls.REQUEST_DELAY_MAX = float(new_config['config_request_delay']) + 2.0

                if 'config_proxy_enabled' in new_config:
                    cls.PROXY_ENABLED = str(new_config['config_proxy_enabled']).lower() == 'true'

                # Telegram settings
                if 'config_telegram_chat_id' in new_config:
                    cls.TELEGRAM_CHAT_ID = str(new_config['config_telegram_chat_id'])
                    logger.info(f"[CONFIG] Updated Telegram Chat ID: {cls.TELEGRAM_CHAT_ID}")

                if 'config_telegram_bot_token' in new_config:
                    cls.TELEGRAM_BOT_TOKEN = str(new_config['config_telegram_bot_token'])

                cls._config_cache = new_config
                logger.info(f"[CONFIG] ✅ Hot reload complete! scan_interval={cls.SEARCH_INTERVAL}s, max_items={cls.MAX_ITEMS_PER_SEARCH}, telegram_chat_id={cls.TELEGRAM_CHAT_ID}")
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
