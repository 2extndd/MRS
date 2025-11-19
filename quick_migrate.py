#!/usr/bin/env python3
import os
import psycopg2

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("❌ DATABASE_URL not found")
    exit(1)

print(f"🔧 Connecting to database...")
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("📊 Adding image_data column...")
cursor.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS image_data TEXT")

print("📊 Creating index...")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_image_data ON items(id) WHERE image_data IS NOT NULL")

conn.commit()
print("✅ Migration completed!")

cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='items' AND column_name='image_data'")
result = cursor.fetchone()
print(f"✅ Verified: {result}")

cursor.close()
conn.close()
