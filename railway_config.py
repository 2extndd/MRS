"""
Railway configuration for MercariSearcher
Adapted from KufarSearcher
"""

import os
from typing import Dict, Any


def is_railway_environment() -> bool:
    """Check if running on Railway"""
    return os.getenv('RAILWAY_ENVIRONMENT') is not None


def get_database_url() -> str:
    """Get database URL with Railway compatibility"""
    database_url = os.getenv('DATABASE_URL')

    if database_url:
        # Railway fix: convert postgres:// to postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return database_url or 'sqlite:///mercari_scanner.db'


def get_port() -> int:
    """Get port from environment"""
    return int(os.getenv('PORT', 5000))


# Railway settings
RAILWAY_SETTINGS = {
    'host': '0.0.0.0',
    'port': get_port(),
    'database_url': get_database_url(),
    'is_railway': is_railway_environment(),
    'log_to_stdout': True,
    'workers': int(os.getenv('WEB_CONCURRENCY', 1)),
    'worker_timeout': int(os.getenv('WORKER_TIMEOUT', 30)),
    'max_connections': int(os.getenv('DB_MAX_CONNECTIONS', 20)),
    'debug': os.getenv('DEBUG', 'false').lower() == 'true',

    # Railway metadata
    'environment_name': os.getenv('RAILWAY_ENVIRONMENT_NAME'),
    'service_name': os.getenv('RAILWAY_SERVICE_NAME'),
    'deployment_id': os.getenv('RAILWAY_DEPLOYMENT_ID'),
    'project_id': os.getenv('RAILWAY_PROJECT_ID'),
    'service_id': os.getenv('RAILWAY_SERVICE_ID'),
}


# Environment variables documentation
REQUIRED_ENV_VARS = {
    'TELEGRAM_BOT_TOKEN': 'Telegram bot token for notifications',
    'TELEGRAM_CHAT_ID': 'Telegram chat ID to send notifications to',
}

OPTIONAL_ENV_VARS = {
    'DATABASE_URL': 'PostgreSQL database URL (provided by Railway)',
    'PORT': 'Web server port (provided by Railway)',
    'TELEGRAM_THREAD_ID': 'Telegram thread ID for topic-based chats',
    'SEARCH_INTERVAL': 'Default search interval in seconds (default: 300)',
    'MAX_ITEMS_PER_SEARCH': 'Maximum items to fetch per search (default: 50)',
    'REQUEST_DELAY_MIN': 'Minimum delay between requests (default: 1.5)',
    'REQUEST_DELAY_MAX': 'Maximum delay between requests (default: 3.5)',
    'PROXY_ENABLED': 'Enable proxy usage (default: false)',
    'PROXY_LIST': 'Comma-separated proxy URLs',
    'RAILWAY_TOKEN': 'Railway API token for auto-redeploy',
    'RAILWAY_PROJECT_ID': 'Railway project ID',
    'RAILWAY_SERVICE_ID': 'Railway service ID',
    'MAX_ERRORS_BEFORE_REDEPLOY': 'Error threshold for auto-redeploy (default: 5)',
    'USD_CONVERSION_RATE': 'JPY to USD conversion rate (default: 0.0067)',
    'DISPLAY_CURRENCY': 'Display currency USD or JPY (default: USD)',
}


def validate_environment() -> Dict[str, Any]:
    """
    Validate environment variables

    Returns:
        Dictionary with validation results
    """
    results = {
        'valid': True,
        'missing_required': [],
        'missing_optional': [],
        'warnings': []
    }

    # Check required variables
    for var, description in REQUIRED_ENV_VARS.items():
        if not os.getenv(var):
            results['missing_required'].append(var)
            results['valid'] = False

    # Check optional but recommended variables
    for var in ['DATABASE_URL', 'RAILWAY_TOKEN']:
        if not os.getenv(var) and is_railway_environment():
            results['warnings'].append(f"{var} not set (recommended for Railway)")

    # Check Railway auto-redeploy configuration
    if is_railway_environment():
        railway_vars = ['RAILWAY_TOKEN', 'RAILWAY_PROJECT_ID', 'RAILWAY_SERVICE_ID']
        if not all(os.getenv(var) for var in railway_vars):
            results['warnings'].append("Railway auto-redeploy not fully configured")

    return results


def print_environment_status():
    """Print environment configuration status"""
    print("\n" + "=" * 60)
    print("RAILWAY ENVIRONMENT STATUS")
    print("=" * 60)

    print(f"\nRunning on Railway: {is_railway_environment()}")

    if is_railway_environment():
        print(f"Environment: {RAILWAY_SETTINGS['environment_name']}")
        print(f"Service: {RAILWAY_SETTINGS['service_name']}")
        print(f"Deployment ID: {RAILWAY_SETTINGS['deployment_id']}")

    print(f"\nDatabase: {'PostgreSQL' if 'postgresql' in get_database_url() else 'SQLite'}")
    print(f"Port: {get_port()}")

    # Validate environment
    validation = validate_environment()

    print("\nEnvironment Validation:")
    if validation['valid']:
        print("✅ All required variables set")
    else:
        print("❌ Missing required variables:")
        for var in validation['missing_required']:
            print(f"   - {var}: {REQUIRED_ENV_VARS[var]}")

    if validation['warnings']:
        print("\n⚠️  Warnings:")
        for warning in validation['warnings']:
            print(f"   - {warning}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    print_environment_status()

    print("\nRailway Settings:")
    for key, value in RAILWAY_SETTINGS.items():
        if 'token' not in key.lower():  # Don't print sensitive values
            print(f"  {key}: {value}")
