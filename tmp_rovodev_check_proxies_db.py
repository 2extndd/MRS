#!/usr/bin/env python3
"""Check what's stored in the database for proxies"""
import sys
sys.path.insert(0, '.')

from db import MercariDB

db = MercariDB()

# Get proxy settings from DB
proxy_enabled = db.get_config_
