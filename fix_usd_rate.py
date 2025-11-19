#!/usr/bin/env python3
"""
Emergency fix for USD conversion rate
Run this to set USD_CONVERSION_RATE = 0.0067 in database
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from db import get_db

def main():
    print("=" * 60)
    print("USD Conversion Rate - Emergency Fix")
    print("=" * 60)

    db = get_db()

    # Check current value
    current_value = db.load_config('config_usd_conversion_rate')
    print(f"\n📊 Current value: {current_value}")

    # Set to 0.0067
    db.save_config('config_usd_conversion_rate', 0.0067)
    print(f"✅ Set config_usd_conversion_rate = 0.0067")

    # Verify
    new_value = db.load_config('config_usd_conversion_rate')
    print(f"✅ Verified new value: {new_value}")

    # Show all config
    all_config = db.get_all_config()
    print(f"\n📋 All config keys:")
    for key, value in all_config.items():
        if 'config_' in key:
            print(f"   {key}: {value}")

    print("\n" + "=" * 60)
    print("✅ DONE! Reload the web page to see changes.")
    print("=" * 60)

if __name__ == "__main__":
    main()
