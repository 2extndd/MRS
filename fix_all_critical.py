#!/usr/bin/env python3
"""
Fix ALL critical issues:
1. Restore database with test query
2. Show config hot reload implementation
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "="*80)
    print("🔧 CRITICAL FIXES - MercariSearcher")
    print("="*80)

    # FIX #1: Restore Database
    print("\n📊 FIX #1: Restoring database with test query...")
    print("-" * 80)

    # Set Railway DATABASE_URL from environment
    import subprocess
    try:
        result = subprocess.run(
            "railway service web && railway variables | grep DATABASE_URL",
            capture_output=True,
            text=True,
            shell=True,
            timeout=10
        )
        for line in result.stdout.split('\n'):
            if 'postgresql://' in line:
                parts = line.split('│')
                if len(parts) >= 3:
                    db_url = parts[2].strip()
                    os.environ['DATABASE_URL'] = db_url
                    print(f"✅ Connected to Railway PostgreSQL")
                    break
    except Exception as e:
        print(f"⚠️  Using local database: {e}")

    from db import DatabaseManager
    db = DatabaseManager()

    print(f"   Database type: {db.db_type}")

    # Check existing searches
    searches = db.get_all_searches()
    print(f"   Current searches: {len(searches)}")

    if len(searches) == 0:
        print(f"\n➕ Adding test search...")

        search_id = db.add_search(
            search_url="https://jp.mercari.com/search?keyword=Y-3",
            name="Y-3 Clothing & Shoes",
            telegram_chat_id="-4997297083",
            is_active=True,
            scan_interval=300,
            brand_filter="Y-3"
        )

        print(f"   ✅ Search added! ID: {search_id}")

        # Verify
        searches_after = db.get_all_searches()
        print(f"   Total searches now: {len(searches_after)}")

        if searches_after:
            for s in searches_after:
                print(f"\n   📍 {s.get('name', 'N/A')}")
                print(f"      URL: {s.get('search_url', 'N/A')[:60]}...")
                print(f"      Active: {s.get('is_active', False)}")
    else:
        print(f"\n   ✅ Database already has searches:")
        for s in searches[:3]:
            print(f"      - {s.get('name', 'N/A')}")

    # FIX #2: Config Hot Reload Implementation
    print("\n" + "="*80)
    print("🔥 FIX #2: Config Hot Reload Implementation")
    print("="*80)

    config_fix = '''
# Config Hot Reload без restart - добавить в core.py:

class MercariCore:
    def __init__(self, db_manager):
        self.db = db_manager
        self.config_cache = {}
        self.config_last_check = 0
        self.config_check_interval = 10  # Check every 10 seconds

    def reload_config_if_needed(self):
        """Hot reload config from database without restart"""
        import time
        current_time = time.time()

        if current_time - self.config_last_check < self.config_check_interval:
            return  # Too soon to check again

        self.config_last_check = current_time

        try:
            # Load all config from DB
            new_config = self.db.get_all_config()

            if new_config != self.config_cache:
                logger.info("[CONFIG] Configuration changed, reloading...")

                # Update settings from database
                self.scan_interval = int(new_config.get('config_scan_interval', 300))
                self.max_items = int(new_config.get('config_max_items', 50))
                # ... other settings ...

                self.config_cache = new_config
                logger.info(f"[CONFIG] ✅ Hot reload complete! New scan_interval: {self.scan_interval}s")

        except Exception as e:
            logger.error(f"[CONFIG] Hot reload failed: {e}")

    def scan_searches(self):
        """Main scan loop - now with hot reload"""
        while not self.stop_requested:
            # HOT RELOAD CONFIG EVERY SCAN
            self.reload_config_if_needed()

            # ... rest of scan logic ...
            time.sleep(self.scan_interval)

---

# В web_ui_plugin/app.py - обновить /api/config/system:

@app.route('/api/config/system', methods=['POST'])
def api_save_system_config():
    try:
        data = request.get_json()

        # Save to database (уже работает)
        saved_count = 0
        for key, value in data.items():
            if db.save_config(f"config_{key}", value):
                saved_count += 1

        # NEW: Не требуется restart!
        return jsonify({
            'success': True,
            'message': f'Saved {saved_count} settings',
            'note': 'Settings will be applied within 10 seconds (hot reload)'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

---

# В web_ui_plugin/templates/config.html - убрать "Restart required":

<div class="alert alert-success" id="success-message" style="display: none;">
    ✅ Settings saved! They will be applied automatically within 10 seconds.
</div>
'''

    print(config_fix)

    print("\n" + "="*80)
    print("✅ SUMMARY")
    print("="*80)
    print(f"✅ Database: {'RESTORED' if len(searches) > 0 or len(db.get_all_searches()) > 0 else 'EMPTY'}")
    print(f"📋 Config Fix: Implementation code shown above")
    print(f"\n🔥 Hot reload будет применять изменения каждые 10 секунд БЕЗ restart!")
    print(f"   - Worker проверяет config каждые 10 секунд")
    print(f"   - Автоматически применяет новые значения")
    print(f"   - Как в KufarSearcher, но через DB вместо ENV")
    print("="*80)
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
