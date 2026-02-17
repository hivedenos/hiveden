from types import SimpleNamespace
from unittest.mock import patch
import sys
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.dependencies import utils as fastapi_dep_utils
from fastapi.testclient import TestClient

# Mock optional runtime dependencies used during router imports.
sys.modules["yoyo"] = MagicMock()
sys.modules["psutil"] = MagicMock()
sys.modules["apscheduler"] = MagicMock()
sys.modules["apscheduler.schedulers"] = MagicMock()
sys.modules["apscheduler.schedulers.asyncio"] = MagicMock()
sys.modules["apscheduler.triggers"] = MagicMock()
sys.modules["apscheduler.triggers.cron"] = MagicMock()
fastapi_dep_utils.ensure_multipart_is_installed = lambda: None

from hiveden.api.routers.appstore import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _drop_task(coro):
    coro.close()
    return None


class FakeJobManager:
    def create_external_job(self, _command):
        return "job-123"

    async def run_external_job(self, _job_id, _worker):
        return None


class FakeCatalogService:
    def list_apps(self, **_kwargs):
        return [
            SimpleNamespace(
                app_id="bitcoin",
                title="Bitcoin",
                version="1.0.0",
                tagline="Node",
                description="Bitcoin node",
                category="finance",
                icon="icon.png",
                icon_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/icon.png",
                compose_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/docker-compose.yml",
                image_urls=[
                    "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/1.png"
                ],
                dependencies=["postgres"],
                developer="Umbrel",
                installed=False,
                install_status="not_installed",
            )
        ]

    def list_installed_apps(self):
        return [
            SimpleNamespace(
                app_id="bitcoin",
                title="Bitcoin",
                version="1.0.0",
                tagline="Node",
                description="Bitcoin node",
                category="finance",
                icon="icon.png",
                icon_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/icon.png",
                compose_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/docker-compose.yml",
                image_urls=[
                    "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/1.png"
                ],
                dependencies=["postgres"],
                developer="Umbrel",
                installed=True,
                install_status="installed",
            )
        ]

    def get_app(self, app_id):
        if app_id != "bitcoin":
            return None
        return SimpleNamespace(
            app_id="bitcoin",
            title="Bitcoin",
            version="1.0.0",
            tagline="Node",
            description="Bitcoin node",
            category="finance",
            icon="icon.png",
            icon_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/icon.png",
            image_urls=[
                "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/imgs/1.png"
            ],
            dependencies=["postgres"],
            developer="Umbrel",
            website="https://example.com",
            repo="https://github.com/example",
            support="https://support.example.com",
            dependencies_apps=[],
            dependencies_system_packages=[],
            manifest_url="https://raw.example/umbrel-app.yml",
            compose_url="https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main/apps/bitcoin/docker-compose.yml",
            installed=True,
            install_status="installed",
        )

    def upsert_catalog(self, apps):
        return SimpleNamespace(total=len(apps), upserted=len(apps))


def test_list_apps_endpoint_returns_data():
    client = _client()
    with patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService):
        response = client.get("/app-store/apps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"][0]["app_id"] == "bitcoin"
    assert payload["data"][0]["icon_url"].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"][0]["image_urls"][0].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"][0]["compose_url"].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"][0]["dependencies"] == ["postgres"]


def test_get_app_detail_endpoint_returns_item():
    client = _client()
    with patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService):
        response = client.get("/app-store/apps/bitcoin")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["compose_url"].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"]["icon_url"].startswith("https://raw.githubusercontent.com/")
    assert payload["data"]["image_urls"][0].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"]["dependencies"] == ["postgres"]


def test_install_endpoint_returns_job_id():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.JobManager", FakeJobManager),
        patch("hiveden.api.routers.appstore.asyncio.create_task", _drop_task),
    ):
        response = client.post("/app-store/apps/bitcoin/install", json={})
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"


def test_uninstall_endpoint_returns_job_id():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.JobManager", FakeJobManager),
        patch("hiveden.api.routers.appstore.asyncio.create_task", _drop_task),
    ):
        response = client.post("/app-store/apps/bitcoin/uninstall", json={})
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"


def test_sync_endpoint_returns_job_id():
    client = _client()
    fake_config = SimpleNamespace(
        appstore_index_url="https://raw.example/apps.json",
        appstore_http_timeout_seconds=5,
    )
    with (
        patch("hiveden.api.routers.appstore.config", fake_config),
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.CatalogClient") as client_cls,
        patch("hiveden.api.routers.appstore.JobManager", FakeJobManager),
        patch("hiveden.api.routers.appstore.asyncio.create_task", _drop_task),
    ):
        client_cls.return_value.fetch_catalog.return_value = {
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
                        "path": "bitcoin",
                    },
                    "install": {
                        "method": "docker-compose",
                        "files": [
                            "bitcoin/docker-compose.yml",
                            "bitcoin/umbrel-app.yml",
                        ],
                    },
                    "search": {
                        "keywords": ["bitcoin"],
                        "categories": ["finance"],
                    },
                    "dependencies": [],
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
        response = client.post("/app-store/sync")
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"
