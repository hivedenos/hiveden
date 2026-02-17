-- Rollback app store catalog and installation state
-- depends: 00003_app_store

-- migrate: apply

DROP INDEX IF EXISTS idx_app_resources_app_id;
DROP INDEX IF EXISTS idx_app_catalog_category;

DROP TABLE IF EXISTS app_install_resources;
DROP TABLE IF EXISTS app_installations;
DROP TABLE IF EXISTS app_catalog_entries;

