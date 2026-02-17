from unittest.mock import patch

import pytest

from hiveden.appstore.catalog_client import CatalogClient


class _FakeResponse:
    def __init__(self, payload: str):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload.encode("utf-8")


def test_fetch_catalog_accepts_new_catalog_contract():
    payload = """
    {
      "version": "1.0.0",
      "generated_at": "2026-01-01T00:00:00Z",
      "total_apps": 1,
      "apps": [
        {
          "id": "bitcoin",
          "name": "Bitcoin",
          "version": "1.0.0",
          "tagline": "Node",
          "description": "Bitcoin node",
          "repository_path": "apps/bitcoin",
          "icon_url": "https://raw.example/icon.png",
          "image_urls": [],
          "source": {
            "id": "umbrel",
            "repo": "https://github.com/getumbrel/umbrel-apps.git",
            "commit": "abc123",
            "path": "bitcoin"
          },
          "install": {
            "method": "docker-compose",
            "files": ["bitcoin/docker-compose.yml"]
          },
          "search": {
            "keywords": ["bitcoin"],
            "categories": ["finance"]
          },
          "dependencies": [],
          "updated_at": "2026-01-01T00:00:00Z"
        }
      ]
    }
    """

    with patch(
        "hiveden.appstore.catalog_client.urlopen", return_value=_FakeResponse(payload)
    ):
        data = CatalogClient().fetch_catalog("https://raw.example/apps.json")

    assert data["total_apps"] == 1
    assert data["apps"][0]["id"] == "bitcoin"


def test_fetch_catalog_rejects_missing_required_top_level_key():
    payload = """
    {
      "version": "1.0.0",
      "generated_at": "2026-01-01T00:00:00Z",
      "apps": []
    }
    """

    with patch(
        "hiveden.appstore.catalog_client.urlopen", return_value=_FakeResponse(payload)
    ):
        with pytest.raises(ValueError, match="missing required keys"):
            CatalogClient().fetch_catalog("https://raw.example/apps.json")
