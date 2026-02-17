from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AppCatalogEntry(BaseModel):
    app_id: str
    title: str
    version: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    developer: Optional[str] = None
    website: Optional[str] = None
    repo: Optional[str] = None
    support: Optional[str] = None
    dependencies_apps: List[str] = Field(default_factory=list)
    dependencies_system_packages: List[str] = Field(default_factory=list)
    manifest_url: Optional[str] = None
    compose_url: Optional[str] = None
    compose_sha256: Optional[str] = None
    repository_path: Optional[str] = None
    icon_url: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
    source: Dict[str, Any] = Field(default_factory=dict)
    install: Dict[str, Any] = Field(default_factory=dict)
    search: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    source_updated_at: Optional[str] = None
    raw_manifest: Dict[str, Any] = Field(default_factory=dict)
    installed: bool = False
    install_status: Optional[str] = None


class AppInstallState(BaseModel):
    app_id: str
    installed_version: Optional[str] = None
    status: str = "not_installed"
    last_error: Optional[str] = None


class CatalogSyncResult(BaseModel):
    total: int
    upserted: int
