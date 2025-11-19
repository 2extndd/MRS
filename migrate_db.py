#!/usr/bin/env python3
"""
Database migration script - adds image_data column
Run on Railway: railway run -s web python migrate_db.py
"""
import os
import sys

# Check if running on Railway
if 'RAILWAY_ENVIRONMENT' in os.environ or 'DATABASE_URL' in os.environ:
    print("✅ Running on Railway environment")
else:
    print("⚠️  Not on Railway, will use local DB")

from db import DatabaseManager

def run_migration():
    """Run the migration"""
    print("=" * 60)
    print("🔧 DATABASE MIGRATION: Add image_data column")
    print("=" * 60)

    try:
        # Initialize database
        db = DatabaseManager()
        print(f"📊 Connected to: {db.db_type.upper()}")

        if db.db_type == 'postgresql':
            # PostgreSQL supports IF NOT EXISTS
            print("\n1️⃣  Adding image_data column...")
            db.execute_query("""
                ALTER TABLE items
                ADD COLUMN IF NOT EXISTS image_data TEXT
            """)
            print("   ✅ Column added (or already exists)")

            print("\n2️⃣  Creating index...")
            db.execute_query("""
                CREATE INDEX IF NOT EXISTS idx_items_image_data
                ON items(id)
                WHERE image_data IS NOT NULL
            """)
            print("   ✅ Index created (or already exists)")

            # Commit changes
            db.conn.commit()
            print("\n3️⃣  Committing changes...")
            print("   ✅ Changes committed")

            # Verify
            print("\n4️⃣  Verifying migration...")
            result = db.query("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'items' AND column_name = 'image_data'
            """)

            if result:
                print(f"   ✅ Column verified: {result[0]}")
            else:
                print("   ❌ Could not verify column")
                return False

            # Check if any items already have image_data
            count = db.query("SELECT COUNT(*) as cnt FROM items WHERE image_data IS NOT NULL")
            if count:
                print(f"\n📊 Items with images: {count[0]['cnt']}")

            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            return True

        else:
            print("❌ SQLite not supported for this migration (no IF NOT EXISTS for ALTER)")
            print("   Please use PostgreSQL on Railway")
            return False

    except Exception as e:
        print(f"\n❌ MIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
