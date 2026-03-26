from types import SimpleNamespace

from hiveden.appstore.adoption_service import AppAdoptionService


class _FakeCatalog:
    def __init__(self):
        self.resources = []
        self.status_calls = []
        self.deleted_resources = []

    def get_app(self, app_id):
        return SimpleNamespace(
            catalog_id=f"stable:{app_id}",
            app_id=app_id,
            version="1.0.0",
            compose_url="https://example.com/docker-compose.yml",
            install_status="not_installed",
            installed=False,
            installable=True,
            install_block_reason=None,
        )

    def list_container_resource_owners(self, container_name, exclude_app_id=None):
        return []

    def list_resources(self, app_id):
        return [item for item in self.resources if item["app_id"] == app_id]

    def delete_resources_by_type(self, app_id, resource_type):
        return None

    def delete_resource(self, app_id, resource_type, resource_name):
        self.deleted_resources.append(
            {
                "app_id": app_id,
                "resource_type": resource_type,
                "resource_name": resource_name,
            }
        )
        self.resources = [
            item
            for item in self.resources
            if not (
                item["app_id"] == app_id
                and item["resource_type"] == resource_type
                and item["resource_name"] == resource_name
            )
        ]

    def add_resource(self, app_id, resource_type, resource_name, metadata=None):
        self.resources.append(
            {
                "app_id": app_id,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "metadata": metadata or {},
            }
        )

    def set_installation_status(
        self,
        app_id,
        status,
        installed_version=None,
        last_error=None,
    ):
        self.status_calls.append(
            {
                "app_id": app_id,
                "status": status,
                "installed_version": installed_version,
                "last_error": last_error,
            }
        )


class _FakeDocker:
    def get_container(self, _identifier):
        return SimpleNamespace(
            Id="abc123",
            Name="pihole",
            Image="pihole/pihole:latest",
            Status="running",
        )


class _MissingDocker:
    def get_container(self, _identifier):
        raise RuntimeError("container missing")


def test_adopt_app_links_external_container_and_marks_installed():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _FakeDocker()
    service._get_expected_images = lambda _compose_url, _warnings: {"pihole/pihole"}

    result = service.adopt_app(
        app_id="pi-hole",
        container_names_or_ids=["pihole"],
    )

    assert len(result.containers) == 1
    assert service.catalog.resources[0]["resource_type"] == "container"
    assert service.catalog.resources[0]["metadata"]["external"] is True
    assert service.catalog.status_calls[-1]["status"] == "installed"


def test_adopt_app_rejects_image_mismatch_without_force():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _FakeDocker()
    service._get_expected_images = lambda _compose_url, _warnings: {"nginx"}

    try:
        service.adopt_app(
            app_id="pi-hole",
            container_names_or_ids=["pihole"],
            force=False,
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "does not match expected images" in str(exc)


def test_adopt_app_persists_resource_when_container_missing_from_docker():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _MissingDocker()
    service._get_expected_images = lambda _compose_url, _warnings: {"pihole/pihole"}

    result = service.adopt_app(
        app_id="pi-hole",
        container_names_or_ids=["pihole"],
    )

    assert len(result.containers) == 1
    assert result.containers[0].Id == "pihole"
    assert result.containers[0].Name == "pihole"
    assert service.catalog.resources[0]["resource_name"] == "pihole"
    assert service.catalog.resources[0]["metadata"]["container_id"] == "pihole"
    assert service.catalog.resources[0]["metadata"]["external"] is True


def test_unlink_adopted_container_removes_external_resource():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _FakeDocker()
    service.catalog.get_app = lambda app_id: SimpleNamespace(
        catalog_id=f"stable:{app_id}",
        app_id=app_id,
        version="1.0.0",
        compose_url="https://example.com/docker-compose.yml",
        install_status="installed",
        installed=True,
        installable=True,
        install_block_reason=None,
    )
    service.catalog.resources = [
        {
            "app_id": "stable:pi-hole",
            "resource_type": "container",
            "resource_name": "/pihole",
            "metadata": {
                "container_id": "abc123",
                "external": True,
            },
        }
    ]

    resource_name = service.unlink_adopted_container("pi-hole", "abc123")

    assert resource_name == "/pihole"
    assert service.catalog.deleted_resources == [
        {
            "app_id": "stable:pi-hole",
            "resource_type": "container",
            "resource_name": "/pihole",
        }
    ]
    assert service.catalog.status_calls[-1]["status"] == "not_installed"


def test_unlink_adopted_container_rejects_managed_container():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _FakeDocker()
    service.catalog.get_app = lambda app_id: SimpleNamespace(
        catalog_id=f"stable:{app_id}",
        app_id=app_id,
        version="1.0.0",
        compose_url="https://example.com/docker-compose.yml",
        install_status="installed",
        installed=True,
        installable=True,
        install_block_reason=None,
    )
    service.catalog.resources = [
        {
            "app_id": "stable:pi-hole",
            "resource_type": "container",
            "resource_name": "/pihole",
            "metadata": {
                "container_id": "abc123",
                "external": False,
            },
        }
    ]

    try:
        service.unlink_adopted_container("pi-hole", "abc123")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "cannot be unlinked" in str(exc)


def test_unlink_adopted_container_uses_db_record_when_app_state_is_stale():
    service = AppAdoptionService.__new__(AppAdoptionService)
    service.catalog = _FakeCatalog()
    service.docker = _FakeDocker()
    service.catalog.get_app = lambda app_id: SimpleNamespace(
        catalog_id=f"stable:{app_id}",
        app_id=app_id,
        version="1.0.0",
        compose_url="https://example.com/docker-compose.yml",
        install_status="not_installed",
        installed=False,
        installable=True,
        install_block_reason=None,
    )
    service.catalog.resources = [
        {
            "app_id": "stable:pi-hole",
            "resource_type": "container",
            "resource_name": "/pihole",
            "metadata": {
                "container_id": "abc123",
                "external": True,
            },
        }
    ]

    resource_name = service.unlink_adopted_container("pi-hole", "abc123")

    assert resource_name == "/pihole"
    assert service.catalog.deleted_resources == [
        {
            "app_id": "stable:pi-hole",
            "resource_type": "container",
            "resource_name": "/pihole",
        }
    ]
    assert service.catalog.status_calls[-1]["status"] == "not_installed"
