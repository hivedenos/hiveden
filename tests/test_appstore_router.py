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
    def list_resources(self, app_id):
        if app_id != "stable:bitcoin":
            return []
        return [
            {
                "id": 2,
                "app_id": app_id,
                "resource_type": "directory",
                "resource_name": "/data/bitcoin",
                "metadata": {"service": "bitcoin-node"},
            },
            {
                "id": 1,
                "app_id": app_id,
                "resource_type": "container",
                "resource_name": "/bitcoin-node",
                "metadata": {
                    "container_id": "container-123",
                    "image": "lncm/bitcoind:latest",
                    "status": "running",
                    "external": False,
                },
            },
        ]

    def list_apps(self, **_kwargs):
        return [
            SimpleNamespace(
                catalog_id="stable:bitcoin",
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
                channel="stable",
                channel_label="Official",
                risk_level="low",
                support_tier="official",
                origin_channel="incubator",
                promotion_status="promoted",
                installed=False,
                install_status="not_installed",
                installable=True,
                install_block_reason=None,
                promotion_request_status=None,
            )
        ]

    def list_installed_apps(self):
        return [
            SimpleNamespace(
                catalog_id="stable:bitcoin",
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
                channel="stable",
                channel_label="Official",
                risk_level="low",
                support_tier="official",
                origin_channel="incubator",
                promotion_status="promoted",
                installed=True,
                install_status="installed",
                installable=True,
                install_block_reason=None,
                promotion_request_status=None,
            )
        ]

    def get_app(self, app_id):
        if app_id != "bitcoin":
            return None
        return SimpleNamespace(
            catalog_id="stable:bitcoin",
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
            source={"id": "umbrel"},
            channel="stable",
            channel_label="Official",
            risk_level="low",
            support_tier="official",
            origin_channel="incubator",
            promotion_status="promoted",
            installed=True,
            install_status="installed",
            installable=True,
            install_block_reason=None,
            promotion_request_status=None,
        )

    def upsert_catalog(self, apps):
        return SimpleNamespace(total=len(apps), upserted=len(apps))

    def clear_catalog_cache(self):
        return SimpleNamespace(cleared_entries=4)


class FakeIncubatorCatalogService(FakeCatalogService):
    def get_app(self, app_id):
        return SimpleNamespace(
            catalog_id="incubator:umbrel:bitcoin",
            app_id="bitcoin",
            title="Bitcoin",
            version="1.0.0",
            tagline="Node",
            description="Bitcoin node",
            category="finance",
            icon="icon.png",
            icon_url=None,
            image_urls=[],
            dependencies=[],
            developer="Umbrel",
            website="https://example.com",
            repo="https://github.com/example",
            support="https://support.example.com",
            dependencies_apps=[],
            dependencies_system_packages=[],
            manifest_url="https://raw.example/umbrel-app.yml",
            compose_url="https://raw.example/docker-compose.yml",
            source={"id": "umbrel"},
            channel="incubator",
            channel_label="Incubator",
            risk_level="high",
            support_tier="candidate",
            origin_channel="incubator",
            promotion_status="none",
            installed=False,
            install_status="not_installed",
            installable=False,
            install_block_reason=(
                "Incubator apps are visible for discovery only and cannot be installed until promoted to a supported channel."
            ),
            promotion_request_status=None,
        )


class FakeAdoptionService:
    def adopt_app(
        self,
        app_id,
        container_names_or_ids,
        replace_existing=False,
        force=False,
    ):
        return SimpleNamespace(
            containers=[
                SimpleNamespace(
                    Id="container-123",
                    Name=container_names_or_ids[0],
                    Image="pihole/pihole:latest",
                    Status="running",
                )
            ],
            warnings=[],
        )


class FakeDockerManager:
    def get_container(self, container_id):
        if container_id in {"container-123", "bitcoin-node"}:
            return SimpleNamespace(
                Id="container-123",
                Name="/bitcoin-node-runtime",
                Image="lncm/bitcoind:runtime",
                Status="restarting",
            )
        raise RuntimeError("container not found")


class FailingDockerManager:
    def get_container(self, _container_id):
        raise RuntimeError("docker unavailable")


class NameLookupDockerManager:
    def __init__(self):
        self.calls = []

    def get_container(self, container_id):
        self.calls.append(container_id)
        if container_id == "bitcoin-node":
            return SimpleNamespace(
                Id="container-lookup-by-name",
                Name="/bitcoin-node-live",
                Image="lncm/bitcoind:live",
                Status="running",
            )
        raise RuntimeError("container not found")


def test_list_apps_endpoint_returns_data():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        response = client.get("/app-store/apps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"][0]["app_id"] == "bitcoin"
    assert payload["data"][0]["catalog_id"] == "stable:bitcoin"
    assert payload["data"][0]["channel"] == "stable"
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
    log_service.return_value.info.assert_called()


def test_get_app_detail_endpoint_returns_item():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.DockerManager", FakeDockerManager),
    ):
        response = client.get("/app-store/apps/bitcoin")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["compose_url"].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"]["catalog_id"] == "stable:bitcoin"
    assert payload["data"]["icon_url"].startswith("https://raw.githubusercontent.com/")
    assert payload["data"]["image_urls"][0].startswith(
        "https://raw.githubusercontent.com/"
    )
    assert payload["data"]["dependencies"] == ["postgres"]
    assert payload["data"]["installed_containers"] == [
        {
            "container_id": "container-123",
            "container_name": "bitcoin-node-runtime",
            "image": "lncm/bitcoind:runtime",
            "status": "restarting",
            "external": False,
        }
    ]


def test_get_app_detail_endpoint_returns_empty_installed_containers_when_not_installed():
    client = _client()

    class NotInstalledCatalogService(FakeCatalogService):
        def get_app(self, app_id):
            entry = super().get_app(app_id)
            entry.installed = False
            entry.install_status = "not_installed"
            return entry

        def list_resources(self, app_id):
            raise AssertionError("list_resources should not be called")

    with patch(
        "hiveden.api.routers.appstore.AppCatalogService",
        NotInstalledCatalogService,
    ):
        response = client.get("/app-store/apps/bitcoin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["installed_containers"] == []


def test_get_app_detail_endpoint_returns_empty_installed_containers_when_none_linked():
    client = _client()

    class NoContainerCatalogService(FakeCatalogService):
        def list_resources(self, app_id):
            return [
                {
                    "id": 9,
                    "app_id": app_id,
                    "resource_type": "directory",
                    "resource_name": "/data/bitcoin",
                    "metadata": {"service": "bitcoin-node"},
                }
            ]

    with patch(
        "hiveden.api.routers.appstore.AppCatalogService",
        NoContainerCatalogService,
    ):
        response = client.get("/app-store/apps/bitcoin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["installed_containers"] == []


def test_get_app_detail_endpoint_falls_back_to_stored_container_metadata():
    client = _client()

    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.DockerManager", FailingDockerManager),
    ):
        response = client.get("/app-store/apps/bitcoin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["installed_containers"] == [
        {
            "container_id": "container-123",
            "container_name": "bitcoin-node",
            "image": "lncm/bitcoind:latest",
            "status": "running",
            "external": False,
        }
    ]


def test_get_app_detail_endpoint_enriches_container_by_name_when_id_missing():
    client = _client()
    docker_manager = NameLookupDockerManager()

    class NameOnlyCatalogService(FakeCatalogService):
        def list_resources(self, app_id):
            return [
                {
                    "id": 1,
                    "app_id": app_id,
                    "resource_type": "container",
                    "resource_name": "/bitcoin-node",
                    "metadata": {
                        "image": "lncm/bitcoind:latest",
                        "status": "created",
                        "external": False,
                    },
                }
            ]

    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", NameOnlyCatalogService),
        patch(
            "hiveden.api.routers.appstore.DockerManager",
            lambda: docker_manager,
        ),
    ):
        response = client.get("/app-store/apps/bitcoin")

    assert response.status_code == 200
    payload = response.json()
    assert docker_manager.calls == ["/bitcoin-node", "bitcoin-node"]
    assert payload["data"]["installed_containers"] == [
        {
            "container_id": "container-lookup-by-name",
            "container_name": "bitcoin-node-live",
            "image": "lncm/bitcoind:live",
            "status": "running",
            "external": False,
        }
    ]


def test_install_endpoint_returns_job_id():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.JobManager", FakeJobManager),
        patch("hiveden.api.routers.appstore.asyncio.create_task", _drop_task),
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        response = client.post("/app-store/apps/bitcoin/install", json={})
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"
    log_service.return_value.info.assert_called()


def test_uninstall_endpoint_returns_job_id():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.JobManager", FakeJobManager),
        patch("hiveden.api.routers.appstore.asyncio.create_task", _drop_task),
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        response = client.post("/app-store/apps/bitcoin/uninstall", json={})
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"
    log_service.return_value.info.assert_called()


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
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        client_cls.return_value.fetch_catalog.return_value = {
            "version": "2.0.0",
            "generated_at": "2026-01-01T00:00:00Z",
            "total_apps": 1,
            "apps": [],
            "apps_by_channel": {
                "stable": [
                    {
                        "id": "bitcoin",
                        "name": "Bitcoin",
                        "version": "1.0.0",
                        "tagline": "Node",
                        "description": "Bitcoin node",
                        "repository_path": "apps/stable/bitcoin",
                        "icon_url": "apps/stable/bitcoin/img/icon.png",
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
                ]
            },
        }
        response = client.post("/app-store/sync")
    assert response.status_code == 202
    assert response.json()["data"]["job_id"] == "job-123"
    log_service.return_value.info.assert_called()


def test_adopt_endpoint_returns_linked_containers():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.AppAdoptionService", FakeAdoptionService),
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        response = client.post(
            "/app-store/apps/bitcoin/adopt",
            json={"container_names_or_ids": ["pihole"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["app"]["app_id"] == "bitcoin"
    assert payload["data"]["containers"][0]["container_name"] == "pihole"
    assert payload["data"]["containers"][0]["external"] is True
    log_service.return_value.info.assert_called()


def test_adopt_endpoint_requires_container_list():
    client = _client()
    with patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService):
        response = client.post(
            "/app-store/apps/bitcoin/adopt",
            json={"container_names_or_ids": []},
        )

    assert response.status_code == 400


def test_install_endpoint_blocks_incubator_apps():
    client = _client()
    with patch(
        "hiveden.api.routers.appstore.AppCatalogService", FakeIncubatorCatalogService
    ):
        response = client.post(
            "/app-store/apps/incubator:umbrel:bitcoin/install", json={}
        )

    assert response.status_code == 409
    assert "cannot be installed" in response.json()["detail"]


def test_adopt_endpoint_blocks_incubator_apps():
    client = _client()
    with patch(
        "hiveden.api.routers.appstore.AppCatalogService", FakeIncubatorCatalogService
    ):
        response = client.post(
            "/app-store/apps/incubator:umbrel:bitcoin/adopt",
            json={"container_names_or_ids": ["pihole"]},
        )

    assert response.status_code == 409
    assert "cannot be installed" in response.json()["detail"]


def test_promotion_request_endpoint_returns_request():
    client = _client()
    with patch(
        "hiveden.api.routers.appstore.AppCatalogService", FakeIncubatorCatalogService
    ):
        response = client.post(
            "/app-store/apps/incubator:umbrel:bitcoin/promotion-request",
            json={"target_channel": "edge", "reason": "Looks useful"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["catalog_id"] == "incubator:umbrel:bitcoin"
    assert payload["data"]["target_channel"] == "edge"
    assert payload["data"]["github_repo_url"] == (
        "https://github.com/hivedenos/hivedenos-apps"
    )
    assert payload["data"]["github_issue_url"].startswith(
        "https://github.com/hivedenos/hivedenos-apps/issues/new?"
    )
    assert payload["data"]["github_pulls_url"] == (
        "https://github.com/hivedenos/hivedenos-apps/pulls"
    )


def test_clear_cache_endpoint_returns_counts():
    client = _client()
    with (
        patch("hiveden.api.routers.appstore.AppCatalogService", FakeCatalogService),
        patch("hiveden.api.routers.appstore.LogService") as log_service,
    ):
        response = client.post("/app-store/cache/clear", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["cleared_entries"] == 4
    assert payload["data"]["job_id"] is None
    log_service.return_value.info.assert_called()
