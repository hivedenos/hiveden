-- App store catalog and installation state
-- depends: 00002_enhance_logs

-- migrate: apply

CREATE TABLE app_catalog_entries (
    app_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    version TEXT,
    tagline TEXT,
    description TEXT,
    category TEXT,
    icon TEXT,
    developer TEXT,
    website TEXT,
    repo TEXT,
    support TEXT,
    dependencies_apps TEXT[] DEFAULT '{}',
    dependencies_system_packages TEXT[] DEFAULT '{}',
    manifest_url TEXT,
    compose_url TEXT,
    compose_sha256 TEXT,
    raw_manifest JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_installations (
    app_id TEXT PRIMARY KEY,
    installed_version TEXT,
    status TEXT NOT NULL DEFAULT 'not_installed',
    last_error TEXT,
    installed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_install_resources (
    id SERIAL PRIMARY KEY,
    app_id TEXT NOT NULL,
    resource_type TEXT NOT NULL CHECK(resource_type IN ('container', 'directory', 'database', 'network', 'dns')),
    resource_name TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_app_catalog_category ON app_catalog_entries(category);
CREATE INDEX idx_app_resources_app_id ON app_install_resources(app_id);

