"""
Database Manager for MercariSearcher (MRS)
Adapted from KufarSearcher for Mercari.jp marketplace

Supports both PostgreSQL (Railway) and SQLite (local development)
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import pytz
from configuration_values import config

# Moscow timezone (GMT+3 / UTC+3)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_time():
    """Get current time in Moscow timezone (GMT+3)"""
    return datetime.now(MOSCOW_TZ)


class DatabaseManager:
    """Database manager supporting PostgreSQL and SQLite"""

    def __init__(self):
        self.db_type = None
        self.conn = None
        self.init_database()

    def init_database(self):
        """Initialize database connection and create tables"""
        database_url = config.DATABASE_URL

        # Detect Railway environment
        is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None

        try:
            if database_url and database_url.startswith('postgres'):
                # PostgreSQL (Railway)
                self.db_type = 'postgresql'
                self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
                print(f"[DB] Connected to PostgreSQL")
            else:
                # SQLite (local)
                self.db_type = 'sqlite'
                db_path = config.SQLITE_DB_PATH
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                print(f"[DB] Connected to SQLite: {db_path}")

            self.create_tables()

        except Exception as e:
            print(f"[DB ERROR] Failed to connect: {e}")
            if is_railway:
                # Fallback to in-memory SQLite on Railway
                print("[DB] Using in-memory SQLite as fallback")
                self.db_type = 'sqlite'
                self.conn = sqlite3.connect(':memory:', check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self.create_tables()
            else:
                raise

    def create_tables(self):
        """Create database tables"""
        # Searches table with Mercari-specific fields
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS searches (
                id SERIAL PRIMARY KEY,
                search_url TEXT NOT NULL,
                name TEXT,
                thread_id TEXT,
                keyword TEXT,
                min_price INTEGER,
                max_price INTEGER,
                category_id TEXT,
                brand TEXT,
                condition TEXT,
                size TEXT,
                color TEXT,
                shipping_payer TEXT,
                item_status TEXT,
                sort_order TEXT DEFAULT 'created_desc',
                scan_interval INTEGER DEFAULT 300,
                scan_limit INTEGER DEFAULT 50,
                is_active BOOLEAN DEFAULT TRUE,
                notify_on_price_drop BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scanned_at TIMESTAMP,
                total_scans INTEGER DEFAULT 0,
                items_found INTEGER DEFAULT 0
            )
        """)

        # Migrate existing searches table if it doesn't have name/thread_id
        # PostgreSQL supports IF NOT EXISTS, SQLite does not
        if self.db_type == 'postgresql':
            try:
                self.execute_query("""
                    ALTER TABLE searches ADD COLUMN IF NOT EXISTS name TEXT
                """)
            except:
                pass

            try:
                self.execute_query("""
                    ALTER TABLE searches ADD COLUMN IF NOT EXISTS thread_id TEXT
                """)
            except:
                pass
            
            try:
                self.execute_query("""
                    ALTER TABLE searches ADD COLUMN IF NOT EXISTS scan_limit INTEGER DEFAULT 50
                """)
            except:
                pass
        else:
            # SQLite - check if columns exist first
            try:
                cursor = self.conn.cursor()
                cursor.execute("PRAGMA table_info(searches)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'name' not in columns:
                    print("[DB] Adding 'name' column to searches table")
                    self.execute_query("ALTER TABLE searches ADD COLUMN name TEXT")
                
                if 'thread_id' not in columns:
                    print("[DB] Adding 'thread_id' column to searches table")
                    self.execute_query("ALTER TABLE searches ADD COLUMN thread_id TEXT")
                
                if 'scan_limit' not in columns:
                    print("[DB] Adding 'scan_limit' column to searches table")
                    self.execute_query("ALTER TABLE searches ADD COLUMN scan_limit INTEGER DEFAULT 50")
            except Exception as e:
                print(f"[DB] Migration warning: {e}")

        # Items table with Mercari-specific fields
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                mercari_id TEXT UNIQUE NOT NULL,
                search_id INTEGER,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                currency TEXT DEFAULT 'JPY',
                brand TEXT,
                condition TEXT,
                size TEXT,
                shipping_cost INTEGER,
                stock_quantity INTEGER DEFAULT 1,
                item_url TEXT NOT NULL,
                image_url TEXT,
                image_data TEXT,
                seller_name TEXT,
                seller_rating REAL,
                location TEXT,
                description TEXT,
                category TEXT,
                is_sent BOOLEAN DEFAULT FALSE,
                sent_at TIMESTAMP,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
            )
        """)
        
        # Migrate existing items table to add image_data column if not exists
        if self.db_type == 'sqlite':
            try:
                cursor = self.conn.cursor()
                cursor.execute("PRAGMA table_info(items)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'image_data' not in columns:
                    print("[DB] Adding 'image_data' column to items table")
                    self.execute_query("ALTER TABLE items ADD COLUMN image_data TEXT")
            except Exception as e:
                print(f"[DB] Migration warning (image_data): {e}")
        else:
            # PostgreSQL
            try:
                self.execute_query("""
                    ALTER TABLE items ADD COLUMN IF NOT EXISTS image_data TEXT
                """)
            except:
                pass

        # Price history table for tracking price changes
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
            )
        """)

        # Settings table
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Error tracking table
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS error_tracking (
                id SERIAL PRIMARY KEY,
                error_message TEXT,
                error_type TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_resolved BOOLEAN DEFAULT FALSE
            )
        """)

        # Logs table
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Key-value store for configuration
        self.execute_query("""
            CREATE TABLE IF NOT EXISTS key_value_store (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        print("[DB] Tables created successfully")

        # Initialize USD conversion rate if not set
        self._ensure_default_config()

    def _ensure_default_config(self):
        """Ensure default configuration values are set"""
        try:
            # Check if USD_CONVERSION_RATE is set
            usd_rate = self.load_config('config_usd_conversion_rate')
            if usd_rate is None or usd_rate == 0:
                # Set default value
                self.save_config('config_usd_conversion_rate', 0.0067)
                print("[DB] ✅ Initialized config_usd_conversion_rate = 0.0067")
        except Exception as e:
            print(f"[DB] Warning: Could not initialize default config: {e}")

    def execute_query(self, query, params=None, fetch=False):
        """Execute SQL query with proper parameter binding"""
        try:
            # Convert PostgreSQL placeholders to SQLite if needed
            if self.db_type == 'sqlite' and params:
                query = query.replace('%s', '?')
                query = query.replace('SERIAL', 'INTEGER')
                query = query.replace('BOOLEAN', 'INTEGER')
                query = query.replace('TIMESTAMP', 'TEXT')

            cursor = self.conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if fetch:
                # Both PostgreSQL (with RealDictCursor) and SQLite (with Row factory) return dict-like objects
                results = cursor.fetchall()
                if self.db_type == 'sqlite':
                    # Convert sqlite3.Row to dict
                    return [dict(row) for row in results]
                else:
                    # PostgreSQL with RealDictCursor already returns dict-like objects
                    return results

            self.conn.commit()
            return cursor

        except Exception as e:
            print(f"[DB ERROR] Query failed: {e}")
            print(f"[DB ERROR] Query: {query}")
            self.conn.rollback()
            raise

    # ==================== SEARCHES ====================

    def add_search(self, search_url, **kwargs):
        """Add new search query"""
        if self.db_type == 'postgresql':
            query = """
                INSERT INTO searches
                (search_url, name, thread_id, keyword, min_price, max_price, category_id, brand,
                 condition, size, color, shipping_payer, item_status, sort_order,
                 scan_interval, scan_limit, notify_on_price_drop)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
        else:
            query = """
                INSERT INTO searches
                (search_url, name, thread_id, keyword, min_price, max_price, category_id, brand,
                 condition, size, color, shipping_payer, item_status, sort_order,
                 scan_interval, scan_limit, notify_on_price_drop)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

        params = (
            search_url,
            kwargs.get('name'),
            kwargs.get('thread_id'),
            kwargs.get('keyword'),
            kwargs.get('min_price'),
            kwargs.get('max_price'),
            kwargs.get('category_id'),
            kwargs.get('brand'),
            kwargs.get('condition'),
            kwargs.get('size'),
            kwargs.get('color'),
            kwargs.get('shipping_payer'),
            kwargs.get('item_status'),
            kwargs.get('sort_order', 'created_desc'),
            kwargs.get('scan_interval', 300),
            kwargs.get('scan_limit', 50),
            kwargs.get('notify_on_price_drop', False)
        )

        if self.db_type == 'postgresql':
            result = self.execute_query(query, params, fetch=True)
            search_id = result[0]['id'] if result else None
        else:
            self.execute_query(query, params)
            search_id = self.conn.cursor().lastrowid

        search_name = kwargs.get('name') or kwargs.get('keyword', 'No name')
        print(f"[DB] ✅ Search added: {search_name} (ID: {search_id})")
        return search_id

    def get_all_searches(self):
        """Get all searches"""
        query = "SELECT * FROM searches ORDER BY created_at DESC"
        return self.execute_query(query, fetch=True)

    def get_active_searches(self):
        """Get active searches"""
        query = "SELECT * FROM searches WHERE is_active = %s ORDER BY created_at DESC"
        return self.execute_query(query, (True,), fetch=True)

    def get_searches_ready_for_scan(self):
        """Get searches that are ready to be scanned based on their interval"""
        current_time = get_moscow_time()

        query = """
            SELECT * FROM searches
            WHERE is_active = %s
            AND (last_scanned_at IS NULL
                 OR last_scanned_at < %s)
            ORDER BY last_scanned_at ASC NULLS FIRST
        """

        # Get all active searches and filter by interval
        all_searches = self.execute_query(
            "SELECT * FROM searches WHERE is_active = %s",
            (True,),
            fetch=True
        )

        ready_searches = []
        for search in all_searches:
            if search['last_scanned_at'] is None:
                ready_searches.append(search)
            else:
                # Parse timestamp
                if isinstance(search['last_scanned_at'], str):
                    last_scan = datetime.fromisoformat(search['last_scanned_at'].replace('Z', '+00:00'))
                else:
                    last_scan = search['last_scanned_at']

                # Make timezone aware
                if last_scan.tzinfo is None:
                    last_scan = MOSCOW_TZ.localize(last_scan)

                interval = search.get('scan_interval', 300)
                next_scan = last_scan + timedelta(seconds=interval)

                if current_time >= next_scan:
                    ready_searches.append(search)

        return ready_searches

    def update_search_scan_time(self, search_id):
        """Update last scanned time for search"""
        query = """
            UPDATE searches
            SET last_scanned_at = %s, total_scans = total_scans + 1
            WHERE id = %s
        """
        self.execute_query(query, (get_moscow_time(), search_id))

    def update_search_stats(self, search_id, items_found):
        """Update search statistics"""
        query = """
            UPDATE searches
            SET items_found = items_found + %s
            WHERE id = %s
        """
        self.execute_query(query, (items_found, search_id))

    def toggle_search_active(self, search_id):
        """Toggle search active status"""
        query = "SELECT is_active FROM searches WHERE id = %s"
        result = self.execute_query(query, (search_id,), fetch=True)

        if result:
            new_status = not result[0]['is_active']
            query = "UPDATE searches SET is_active = %s WHERE id = %s"
            self.execute_query(query, (new_status, search_id))
            return new_status
        return None

    def get_search_by_id(self, search_id):
        """Get single search by ID"""
        query = "SELECT * FROM searches WHERE id = %s"
        result = self.execute_query(query, (search_id,), fetch=True)
        return result[0] if result else None

    def update_search(self, search_id, **kwargs):
        """Update search query"""
        updates = []
        params = []

        if 'search_url' in kwargs:
            updates.append("search_url = %s")
            params.append(kwargs['search_url'])

        if 'name' in kwargs:
            updates.append("name = %s")
            params.append(kwargs['name'])

        if 'thread_id' in kwargs:
            updates.append("thread_id = %s")
            params.append(kwargs['thread_id'])

        if 'keyword' in kwargs:
            updates.append("keyword = %s")
            params.append(kwargs['keyword'])
        
        if 'scan_limit' in kwargs:
            updates.append("scan_limit = %s")
            params.append(kwargs['scan_limit'])
        
        if 'scan_interval' in kwargs:
            updates.append("scan_interval = %s")
            params.append(kwargs['scan_interval'])

        if not updates:
            return

        params.append(search_id)
        query = f"UPDATE searches SET {', '.join(updates)} WHERE id = %s"
        self.execute_query(query, tuple(params))
        print(f"[DB] Search {search_id} updated")

    def delete_search(self, search_id):
        """Delete search"""
        query = "DELETE FROM searches WHERE id = %s"
        self.execute_query(query, (search_id,))
        print(f"[DB] Search {search_id} deleted")

    # ==================== ITEMS ====================

    def add_item(self, mercari_id, search_id, **kwargs):
        """Add new item if not exists"""
        # Check if item already exists
        check_query = "SELECT id FROM items WHERE mercari_id = %s"
        existing = self.execute_query(check_query, (mercari_id,), fetch=True)

        if existing:
            print(f"[DB] Item {mercari_id} already exists")
            return None

        # PostgreSQL: use RETURNING id
        if self.db_type == 'postgresql':
            query = """
                INSERT INTO items
                (mercari_id, search_id, title, price, currency, brand, condition,
                 size, shipping_cost, stock_quantity, item_url, image_url, image_data,
                 seller_name, seller_rating, location, description, category, found_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
        else:
            # SQLite: no RETURNING
            query = """
                INSERT INTO items
                (mercari_id, search_id, title, price, currency, brand, condition,
                 size, shipping_cost, stock_quantity, item_url, image_url, image_data,
                 seller_name, seller_rating, location, description, category, found_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        
        params = (
            mercari_id,
            search_id,
            kwargs.get('title'),
            kwargs.get('price'),
            kwargs.get('currency', 'JPY'),
            kwargs.get('brand'),
            kwargs.get('condition'),
            kwargs.get('size'),
            kwargs.get('shipping_cost'),
            kwargs.get('stock_quantity', 1),
            kwargs.get('item_url'),
            kwargs.get('image_url'),
            kwargs.get('image_data'),  # Base64-encoded image
            kwargs.get('seller_name'),
            kwargs.get('seller_rating'),
            kwargs.get('location'),
            kwargs.get('description'),
            kwargs.get('category'),
            get_moscow_time()
        )

        # Get inserted item ID
        if self.db_type == 'postgresql':
            result = self.execute_query(query, params, fetch=True)
            item_id = result[0]['id'] if result else None
        else:
            cursor = self.execute_query(query, params)
            item_id = cursor.lastrowid

        # Add initial price to price_history
        if item_id and kwargs.get('price'):
            self.add_price_history(item_id, kwargs.get('price'))

        print(f"[DB] Item added: {kwargs.get('title', 'No title')} (ID: {item_id})")
        return item_id

    def get_unsent_items(self, limit=100):
        """Get items that haven't been sent to Telegram"""
        query = """
            SELECT i.*, s.keyword as search_keyword, s.thread_id as search_thread_id
            FROM items i
            LEFT JOIN searches s ON i.search_id = s.id
            WHERE i.is_sent = %s
            ORDER BY i.found_at ASC
            LIMIT %s
        """
        return self.execute_query(query, (False, limit), fetch=True)

    def mark_item_sent(self, item_id):
        """Mark item as sent"""
        query = "UPDATE items SET is_sent = %s, sent_at = %s WHERE id = %s"
        self.execute_query(query, (True, get_moscow_time(), item_id))

    def get_all_items(self, limit=100, offset=0):
        """Get recent items - FAST: without heavy image_data column"""
        query = """
            SELECT 
                i.id, i.mercari_id, i.search_id, i.title, i.price, i.currency,
                i.brand, i.condition, i.size, i.shipping_cost, i.stock_quantity,
                i.item_url, i.image_url, 
                i.seller_name, i.seller_rating, i.location, i.description, i.category,
                i.is_sent, i.sent_at, i.found_at,
                s.keyword as search_keyword
            FROM items i
            LEFT JOIN searches s ON i.search_id = s.id
            ORDER BY i.found_at DESC
            LIMIT %s OFFSET %s
        """
        return self.execute_query(query, (limit, offset), fetch=True)

    def get_item_by_mercari_id(self, mercari_id):
        """Get item by Mercari ID"""
        query = "SELECT * FROM items WHERE mercari_id = %s"
        result = self.execute_query(query, (mercari_id,), fetch=True)
        return result[0] if result else None

    # ==================== PRICE HISTORY ====================

    def add_price_history(self, item_id, price):
        """Add price record to history"""
        query = """
            INSERT INTO price_history (item_id, price)
            VALUES (%s, %s)
        """
        self.execute_query(query, (item_id, price))

    def get_price_history(self, item_id):
        """Get price history for item"""
        query = """
            SELECT * FROM price_history
            WHERE item_id = %s
            ORDER BY recorded_at DESC
        """
        return self.execute_query(query, (item_id,), fetch=True)

    def check_price_drop(self, mercari_id, current_price):
        """Check if price has dropped for item"""
        item = self.get_item_by_mercari_id(mercari_id)
        if not item:
            return False, None

        history = self.get_price_history(item['id'])
        if len(history) < 2:
            return False, None

        previous_price = history[1]['price']  # Second most recent

        if current_price < previous_price:
            return True, previous_price

        return False, None

    # ==================== SETTINGS ====================

    def get_setting(self, key, default=None):
        """Get setting value"""
        query = "SELECT value FROM settings WHERE key = %s"
        result = self.execute_query(query, (key,), fetch=True)

        if result:
            return result[0]['value']
        return default

    def set_setting(self, key, value):
        """Set setting value"""
        # Try to update first
        query = "UPDATE settings SET value = %s, updated_at = %s WHERE key = %s"
        cursor = self.execute_query(query, (value, get_moscow_time(), key))

        # If no rows affected, insert
        if cursor.rowcount == 0:
            query = "INSERT INTO settings (key, value) VALUES (%s, %s)"
            self.execute_query(query, (key, value))

    # ==================== ERROR TRACKING ====================

    def log_error(self, error_message, error_type='general'):
        """Log error to database"""
        query = """
            INSERT INTO error_tracking (error_message, error_type)
            VALUES (%s, %s)
        """
        self.execute_query(query, (error_message, error_type))

    def get_recent_errors(self, limit=10):
        """Get recent errors"""
        query = """
            SELECT * FROM error_tracking
            ORDER BY occurred_at DESC
            LIMIT %s
        """
        return self.execute_query(query, (limit,), fetch=True)

    def get_unresolved_error_count(self):
        """Get count of unresolved errors"""
        query = "SELECT COUNT(*) as count FROM error_tracking WHERE is_resolved = %s"
        result = self.execute_query(query, (False,), fetch=True)
        return result[0]['count'] if result else 0

    def clear_old_errors(self, days=7):
        """Clear errors older than specified days"""
        cutoff = get_moscow_time() - timedelta(days=days)
        query = "DELETE FROM error_tracking WHERE occurred_at < %s"
        self.execute_query(query, (cutoff,))

    # ==================== LOGS ====================

    def add_log(self, level, message):
        """Add log entry"""
        query = "INSERT INTO logs (level, message) VALUES (%s, %s)"
        self.execute_query(query, (level, message))

    def add_log_entry(self, level: str, message: str, source: str = None, details: str = None):
        """Add log entry with source and details (KufarSearch compatible)"""
        # Combine source and details into message if provided
        full_message = message
        if source:
            full_message = f"[{source}] {message}"
        if details:
            full_message = f"{full_message} - {details}"

        query = "INSERT INTO logs (level, message, timestamp) VALUES (%s, %s, %s)"
        self.execute_query(query, (level, full_message, get_moscow_time()))

    def get_logs(self, limit=100, level=None):
        """Get recent logs - FAST with smaller default limit"""
        # Limit to max 500 logs to avoid performance issues
        limit = min(limit, 500)
        
        if level:
            query = """
                SELECT * FROM logs
                WHERE level = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """
            return self.execute_query(query, (level, limit), fetch=True)
        else:
            query = "SELECT * FROM logs ORDER BY timestamp DESC LIMIT %s"
            return self.execute_query(query, (limit,), fetch=True)

    def clear_old_logs(self, days=7):
        """Clear logs older than specified days"""
        cutoff = get_moscow_time() - timedelta(days=days)
        query = "DELETE FROM logs WHERE timestamp < %s"
        self.execute_query(query, (cutoff,))

    # ==================== CLEANUP ====================

    def cleanup_old_data(self):
        """Clean up old data"""
        # Delete old logs (7 days)
        self.clear_old_logs(7)

        # Delete old errors (7 days)
        self.clear_old_errors(7)

        # Delete sent items older than 30 days
        cutoff = get_moscow_time() - timedelta(days=30)
        query = "DELETE FROM items WHERE is_sent = %s AND sent_at < %s"
        self.execute_query(query, (True, cutoff))

        print("[DB] Old data cleaned up")

    # ==================== STATISTICS ====================

    def get_statistics(self):
        """Get database statistics"""
        stats = {}

        # Total searches
        result = self.execute_query("SELECT COUNT(*) as count FROM searches", fetch=True)
        stats['total_searches'] = result[0]['count'] if result else 0

        # Active searches
        result = self.execute_query("SELECT COUNT(*) as count FROM searches WHERE is_active = %s", (True,), fetch=True)
        stats['active_searches'] = result[0]['count'] if result else 0

        # Total items
        result = self.execute_query("SELECT COUNT(*) as count FROM items", fetch=True)
        stats['total_items'] = result[0]['count'] if result else 0

        # Unsent items
        result = self.execute_query("SELECT COUNT(*) as count FROM items WHERE is_sent = %s", (False,), fetch=True)
        stats['unsent_items'] = result[0]['count'] if result else 0

        # Total errors
        result = self.execute_query("SELECT COUNT(*) as count FROM error_tracking WHERE is_resolved = %s", (False,), fetch=True)
        stats['unresolved_errors'] = result[0]['count'] if result else 0

        return stats

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("[DB] Connection closed")

    # ==================== CONFIG MANAGEMENT ====================

    def save_config(self, key, value):
        """Save configuration value to database"""
        import json
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            if self.db_type == 'sqlite':
                # SQLite: INSERT OR REPLACE (no need for 3 parameters)
                query = """
                    INSERT OR REPLACE INTO key_value_store (key, value, updated_at)
                    VALUES (?, ?, datetime('now'))
                """
                self.execute_query(query, (key, value_str))
            else:
                # PostgreSQL: INSERT ... ON CONFLICT
                query = """
                    INSERT INTO key_value_store (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP
                """
                self.execute_query(query, (key, value_str, value_str))
            print(f"[DB] Config saved: {key}")
            return True
        except Exception as e:
            print(f"[DB ERROR] Failed to save config {key}: {e}")
            return False

    def load_config(self, key, default=None):
        """Load configuration value from database"""
        import json
        try:
            query = "SELECT value FROM key_value_store WHERE key = %s"
            result = self.execute_query(query, (key,), fetch=True)
            if result and len(result) > 0:
                value_str = result[0]['value']
                try:
                    return json.loads(value_str)
                except:
                    return value_str
            return default
        except Exception as e:
            print(f"[DB ERROR] Failed to load config {key}: {e}")
            return default

    def get_all_config(self):
        """Get all configuration values"""
        import json
        try:
            query = "SELECT key, value FROM key_value_store"
            results = self.execute_query(query, fetch=True)
            config_dict = {}
            for row in results:
                try:
                    config_dict[row['key']] = json.loads(row['value'])
                except:
                    config_dict[row['key']] = row['value']
            return config_dict
        except Exception as e:
            print(f"[DB ERROR] Failed to load all config: {e}")
            return {}

    def increment_api_counter(self):
        """Increment API request counter in database (for cross-process visibility)"""
        try:
            # Get current value
            current = self.load_config('api_request_count', 0)
            if isinstance(current, str):
                current = int(current) if current.isdigit() else 0

            # Increment and save
            new_value = current + 1
            self.save_config('api_request_count', new_value)
            return new_value
        except Exception as e:
            print(f"[DB ERROR] Failed to increment API counter: {e}")
            return 0

    def get_api_counter(self):
        """Get current API request count from database"""
        try:
            count = self.load_config('api_request_count', 0)
            if isinstance(count, str):
                return int(count) if count.isdigit() else 0
            return int(count) if count else 0
        except Exception as e:
            print(f"[DB ERROR] Failed to get API counter: {e}")
            return 0


# Global database instance
_db_manager = None


def get_db():
    """Get global database instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


if __name__ == "__main__":
    # Test database
    db = get_db()
    print("\n=== Database Statistics ===")
    stats = db.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
