#!/usr/bin/env python3
"""
Run database migration to add image_data column
"""
import sys
from db import DatabaseManager

def main():
    print("🔧 Running database migration...")

    # Initialize database
    db = DatabaseManager()

    try:
        # Add image_data column if not exists
        print("Adding image_data column to items table...")
        db.execute_query("""
            ALTER TABLE items ADD COLUMN IF NOT EXISTS image_data TEXT
        """)

        # Create index for faster retrieval
        print("Creating index on image_data...")
        db.execute_query("""
            CREATE INDEX IF NOT EXISTS idx_items_image_data
            ON items(id) WHERE image_data IS NOT NULL
        """)

        # Commit changes
        db.conn.commit()

        # Verify column exists
        result = db.query("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'items' AND column_name = 'image_data'
        """)

        if result:
            print(f"✅ Migration successful! Column: {result[0]}")
        else:
            print("⚠️ Could not verify column (might be SQLite)")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
