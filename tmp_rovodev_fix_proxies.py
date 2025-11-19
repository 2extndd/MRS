#!/usr/bin/env python3
"""
Fix proxies in database - add correct proxy list
"""
import sys
sys.path.insert(0, '.')

from db import MercariDB

# Your correct proxy list (115 proxies)
CORRECT_PROXIES = """82.21.62.51:7815:wtllhdak:9vxcxlvhxv1h
82.23.88.20:7776:wtllhdak:9vxcxlvhxv1h
96.62.187.26:7239:wtllhdak:9vxcxlvhxv1h
104.253.199.230:5509:wtllhdak:9vxcxlvhxv1h
159.148.236.107:6313:wtllhdak:9vxcxlvhxv1h
82.21.49.142:7405:wtllhdak:9vxcxlvhxv1h
150