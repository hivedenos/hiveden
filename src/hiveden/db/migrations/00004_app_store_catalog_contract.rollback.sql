-- Rollback app store catalog contract columns
-- depends: 00004_app_store_catalog_contract

-- migrate: apply

ALTER TABLE app_catalog_entries
    DROP COLUMN IF EXISTS source_updated_at,
    DROP COLUMN IF EXISTS dependencies,
    DROP COLUMN IF EXISTS search,
    DROP COLUMN IF EXISTS install,
    DROP COLUMN IF EXISTS source,
    DROP COLUMN IF EXISTS image_urls,
    DROP COLUMN IF EXISTS icon_url,
    DROP COLUMN IF EXISTS repository_path;
