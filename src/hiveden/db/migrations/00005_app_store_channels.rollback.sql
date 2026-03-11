-- Rollback app store channels and catalog ids
-- depends: 00005_app_store_channels

-- migrate: apply

DROP INDEX IF EXISTS idx_app_catalog_channel;
DROP INDEX IF EXISTS idx_app_catalog_app_id;

ALTER TABLE app_catalog_entries
    DROP CONSTRAINT IF EXISTS app_catalog_entries_pkey;

UPDATE app_installations
SET app_id = SPLIT_PART(app_id, ':', 2)
WHERE app_id LIKE 'stable:%';

UPDATE app_install_resources
SET app_id = SPLIT_PART(app_id, ':', 2)
WHERE app_id LIKE 'stable:%';

ALTER TABLE app_catalog_entries
    DROP COLUMN IF EXISTS promotion_status,
    DROP COLUMN IF EXISTS origin_channel,
    DROP COLUMN IF EXISTS support_tier,
    DROP COLUMN IF EXISTS risk_level,
    DROP COLUMN IF EXISTS channel_label,
    DROP COLUMN IF EXISTS channel,
    DROP COLUMN IF EXISTS catalog_id;

ALTER TABLE app_catalog_entries
    ADD CONSTRAINT app_catalog_entries_pkey PRIMARY KEY (app_id);
