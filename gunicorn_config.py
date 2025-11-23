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

# wsgi.py handles scheduler startup via threading
# No post_fork needed - simpler and more reliable
