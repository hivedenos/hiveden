-- Add app store channels and catalog ids
-- depends: 00004_app_store_catalog_contract

-- migrate: apply

ALTER TABLE app_catalog_entries
    DROP CONSTRAINT IF EXISTS app_catalog_entries_pkey;

ALTER TABLE app_catalog_entries
    ADD COLUMN IF NOT EXISTS catalog_id TEXT,
    ADD COLUMN IF NOT EXISTS channel TEXT DEFAULT 'stable',
    ADD COLUMN IF NOT EXISTS channel_label TEXT,
    ADD COLUMN IF NOT EXISTS risk_level TEXT,
    ADD COLUMN IF NOT EXISTS support_tier TEXT,
    ADD COLUMN IF NOT EXISTS origin_channel TEXT,
    ADD COLUMN IF NOT EXISTS promotion_status TEXT;

UPDATE app_catalog_entries
SET channel = COALESCE(NULLIF(channel, ''), 'stable');

UPDATE app_catalog_entries
SET catalog_id = CONCAT(channel, ':', app_id)
WHERE catalog_id IS NULL OR catalog_id = '';

UPDATE app_installations
SET app_id = CONCAT('stable:', app_id)
WHERE app_id IS NOT NULL AND POSITION(':' IN app_id) = 0;

UPDATE app_install_resources
SET app_id = CONCAT('stable:', app_id)
WHERE app_id IS NOT NULL AND POSITION(':' IN app_id) = 0;

ALTER TABLE app_catalog_entries
    ALTER COLUMN catalog_id SET NOT NULL;

ALTER TABLE app_catalog_entries
    ADD CONSTRAINT app_catalog_entries_pkey PRIMARY KEY (catalog_id);

CREATE INDEX IF NOT EXISTS idx_app_catalog_app_id ON app_catalog_entries(app_id);
CREATE INDEX IF NOT EXISTS idx_app_catalog_channel ON app_catalog_entries(channel);
