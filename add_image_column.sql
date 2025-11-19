-- Migration: Add image_data column to items table
-- This stores base64-encoded images to bypass Cloudflare blocking

ALTER TABLE items ADD COLUMN IF NOT EXISTS image_data TEXT;

-- Add index for faster retrieval
CREATE INDEX IF NOT EXISTS idx_items_image_data ON items(id) WHERE image_data IS NOT NULL;

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'items' AND column_name = 'image_data';
