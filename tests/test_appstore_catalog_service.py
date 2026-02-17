from datetime import datetime
import sys
from unittest.mock import MagicMock

# Mock optional runtime dependencies imported by database manager.
sys.modules["yoyo"] = MagicMock()

from hiveden.appstore.catalog_service import AppCatalogService


def test_normalize_entry_resolves_compose_and_manifest_urls_from_install_files():
    service = AppCatalogService.__new__(AppCatalogService)
    app = {
        "id": "bitcoin",
        "name": "Bitcoin",
        "version": "1.0.0",
        "tagline": "Node",
        "description": "Bitcoin node",
        "developer": "Umbrel",
        "repository_path": "apps/bitcoin",
        "icon_url": "https://raw.example/icon.png",
        "image_urls": ["https://raw.example/1.png"],
        "source": {
            "id": "umbrel",
            "repo": "https://github.com/getumbrel/umbrel-apps.git",
            "commit": "abc123",
            "path": "bitcoin",
        },
        "install": {
            "method": "docker-compose",
            "files": ["bitcoin/docker-compose.yml", "bitcoin/umbrel-app.yml"],
        },
        "search": {
            "keywords": ["bitcoin"],
            "categories": ["finance"],
        },
        "dependencies": ["postgres"],
        "updated_at": "2026-01-01T00:00:00Z",
    }

    normalized = service._normalize_app_entry(app)

    assert normalized["app_id"] == "bitcoin"
    assert normalized["title"] == "Bitcoin"
    assert normalized["category"] == "finance"
    assert normalized["compose_url"] == (
        "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/"
        "main/apps/bitcoin/docker-compose.yml"
    )
    assert normalized["manifest_url"] == (
        "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/"
        "main/apps/bitcoin/umbrel-app.yml"
    )
    assert normalized["dependencies"] == ["postgres"]
    assert isinstance(normalized["source_updated_at"], datetime)


def test_normalize_entry_resolves_icon_and_image_urls_to_raw_github():
    service = AppCatalogService.__new__(AppCatalogService)
    app = {
        "id": "bitcoin",
        "name": "Bitcoin",
        "version": "1.0.0",
        "tagline": "Node",
        "description": "Bitcoin node",
        "repository_path": "apps/bitcoin",
        "icon_url": "https://raw.githubusercontent.com/getumbrel/umbrel-apps-gallery/master/bitcoin/icon.png",
        "image_urls": [
            "https://raw.githubusercontent.com/getumbrel/umbrel-apps-gallery/master/bitcoin/1.png",
            "https://raw.githubusercontent.com/getumbrel/umbrel-apps-gallery/master/bitcoin/2.webp",
        ],
        "source": {
            "id": "hivedenos",
            "repo": "https://github.com/getumbrel/umbrel-apps.git",
            "commit": "abc123",
            "path": "apps/bitcoin",
        },
        "install": {
            "method": "docker-compose",
            "files": ["apps/bitcoin/docker-compose.yml"],
        },
        "search": {
            "keywords": ["bitcoin"],
            "categories": ["finance"],
        },
        "dependencies": ["postgres"],
        "updated_at": "2026-01-01T00:00:00Z",
    }

    normalized = service._normalize_app_entry(app)

    assert normalized["icon_url"] == (
        "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/"
        "main/apps/bitcoin/imgs/icon.png"
    )
    assert normalized["image_urls"] == [
        "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/"
        "main/apps/bitcoin/imgs/1.png",
        "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/"
        "main/apps/bitcoin/imgs/2.webp",
    ]
