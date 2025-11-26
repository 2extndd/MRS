-- Performance indexes for items table
-- Run this ONCE on Railway PostgreSQL

-- Index for ORDER BY found_at DESC (most important!)
CREATE INDEX IF NOT EXISTS idx_items_found_at ON items (found_at DESC);

-- Index for WHERE mercari_id LIKE 'm%' / NOT LIKE 'm%'
CREATE INDEX IF NOT EXISTS idx_items_mercari_id_pattern ON items (mercari_id text_pattern_ops);

-- Index for WHERE category_id IS NULL
CREATE INDEX IF NOT EXISTS idx_items_category_id ON items (category_id) WHERE category_id IS NOT NULL;

-- Show all indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'items'
ORDER BY indexname;
