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
# Note: Scheduler auto-starts via wsgi.py module-level code
# No post_worker_init needed - wsgi.py handles everything
