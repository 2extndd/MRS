"""
Gunicorn configuration for MercariSearcher
Simple config - scheduler runs via wsgi.py
"""

import os

# Bind address - use PORT from environment (Railway sets this dynamically)
port = int(os.getenv('PORT', 8080))
bind = f"0.0.0.0:{port}"

# Worker configuration
workers = 1  # Single worker to avoid multiple scheduler instances
timeout = 600  # 10 minutes - long timeout for background scheduler thread
graceful_timeout = 30  # Graceful shutdown timeout
loglevel = "info"

# Worker lifecycle hooks
def post_worker_init(worker):
    """Import and call post_worker_init from wsgi.py"""
    from wsgi import post_worker_init as wsgi_post_worker_init
    wsgi_post_worker_init(worker)
