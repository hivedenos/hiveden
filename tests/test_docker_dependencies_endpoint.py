from unittest.mock import MagicMock, patch
import sys

from fastapi import FastAPI
from fastapi.dependencies import utils as fastapi_dep_utils
from fastapi.testclient import TestClient

# Mock optional runtime dependencies used during router package imports.
sys.modules["yoyo"] = MagicMock()
sys.modules["psutil"] = MagicMock()
sys.modules["apscheduler"] = MagicMock()
sys.modules["apscheduler.schedulers"] = MagicMock()
sys.modules["apscheduler.schedulers.asyncio"] = MagicMock()
sys.modules["apscheduler.triggers"] = MagicMock()
sys.modules["apscheduler.triggers.cron"] = MagicMock()
fastapi_dep_utils.ensure_multipart_is_installed = lambda: None

from hiveden.api.routers.docker.containers import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_check_dependencies_endpoint_returns_status_per_container():
    client = _client()

    class FakeDockerManager:
        def check_dependencies(self, dependencies):
            assert dependencies == ["postgres", "redis", "missing-db"]
            return {
                "all_satisfied": False,
                "missing": ["missing-db"],
                "items": [
                    {"name": "postgres", "exists": True},
                    {"name": "redis", "exists": True},
                    {"name": "missing-db", "exists": False},
                ],
            }

    with patch("hiveden.docker.containers.DockerManager", FakeDockerManager):
        response = client.post(
            "/containers/dependencies/check",
            json={"dependencies": ["postgres", "redis", "missing-db"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["all_satisfied"] is False
    assert payload["data"]["missing"] == ["missing-db"]


def test_create_container_returns_400_when_dependencies_missing():
    client = _client()
    payload = {
        "name": "app",
        "image": "nginx:latest",
        "dependencies": ["postgres"],
    }

    with patch(
        "hiveden.docker.containers.create_container",
        side_effect=ValueError("Missing container dependencies: postgres"),
    ):
        response = client.post("/containers", json=payload)

    assert response.status_code == 400
    assert "Missing container dependencies" in response.json()["detail"]
