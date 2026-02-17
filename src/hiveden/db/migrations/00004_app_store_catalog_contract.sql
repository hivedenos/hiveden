-- Extend app store catalog for external catalog contract
-- depends: 00003_app_store

-- migrate: apply

ALTER TABLE app_catalog_entries
    ADD COLUMN IF NOT EXISTS repository_path TEXT,
    ADD COLUMN IF NOT EXISTS icon_url TEXT,
    ADD COLUMN IF NOT EXISTS image_urls TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS source JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS install JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS search JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS dependencies TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMP;
