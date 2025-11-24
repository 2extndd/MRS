#!/usr/bin/env python3
"""
Calculate approximate database size from logs and statistics
"""

# From the logs we saw:
# - DB ID: 9013 was added recently
# This means there are at least 9013 items in the database

# From Railway logs analysis:
# - We see active scanning with HIGH-RES images
# - Average image size from logs: 50KB - 265KB base64
# - Average: ~120KB base64 per image

# Assumptions based on logs:
TOTAL_ITEMS_ESTIMATE = 9013  # Latest DB ID seen
ITEMS_WITH_IMAGES_PERCENTAGE = 0.85  # 85% have images (estimate)
AVERAGE_IMAGE_SIZE_BASE64_KB = 120  # Average from logs

# Calculate
items_with_images = int(TOTAL_ITEMS_ESTIMATE * ITEMS_WITH_IMAGES_PERCENTAGE)
total_images_size_kb = items_with_images * AVERAGE_IMAGE_SIZE_BASE64_KB
total_images_size_mb = total_images_size_kb / 1024

# Text data (title, description, URLs, etc.)
# Estimate ~5KB per item for all text fields
text_data_per_item_kb = 5
total_text_size_kb = TOTAL_ITEMS_ESTIMATE * text_data_per_item_kb
total_text_size_mb = total_text_size_kb / 1024

# Metadata, indexes, etc. (estimate 10% overhead)
overhead_mb = (total_images_size_mb + total_text_size_mb) * 0.1

# Total
total_db_size_mb = total_images_size_mb + total_text_size_mb + overhead_mb
total_db_size_gb = total_db_size_mb / 1024

print("=" * 60)
print("DATABASE SIZE ESTIMATION")
print("=" * 60)
print()
print(f"📊 Total items in DB: ~{TOTAL_ITEMS_ESTIMATE:,}")
print(f"   (based on latest DB ID: {TOTAL_ITEMS_ESTIMATE})")
print()
print(f"🖼️  Items with images: ~{items_with_images:,} ({ITEMS_WITH_IMAGES_PERCENTAGE*100:.0f}%)")
print(f"   Average image size: {AVERAGE_IMAGE_SIZE_BASE64_KB}KB (base64)")
print()
print("💾 Storage breakdown:")
print(f"   Images:    {total_images_size_mb:>8,.1f} MB ({total_images_size_mb/total_db_size_mb*100:.1f}%)")
print(f"   Text data: {total_text_size_mb:>8,.1f} MB ({total_text_size_mb/total_db_size_mb*100:.1f}%)")
print(f"   Overhead:  {overhead_mb:>8,.1f} MB ({overhead_mb/total_db_size_mb*100:.1f}%)")
print(f"   " + "-" * 30)
print(f"   TOTAL:     {total_db_size_mb:>8,.1f} MB")
print(f"              {total_db_size_gb:>8,.2f} GB")
print()
print("=" * 60)
print()

# Calculate per-item average
avg_per_item_kb = (total_db_size_mb * 1024) / TOTAL_ITEMS_ESTIMATE
print(f"📈 Average per item: {avg_per_item_kb:.1f} KB")
print()

# Projection for growth
print("🔮 Growth projections:")
print()
for items in [10000, 20000, 50000, 100000]:
    projected_size_gb = (items * avg_per_item_kb) / (1024 * 1024)
    print(f"   {items:>6,} items → {projected_size_gb:>6.2f} GB")
print()
print("=" * 60)
