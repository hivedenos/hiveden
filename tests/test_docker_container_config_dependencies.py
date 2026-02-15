from types import SimpleNamespace
import sys
from unittest.mock import MagicMock

# Mock optional runtime dependency required by DB manager import chain.
sys.modules["yoyo"] = MagicMock()
sys.modules["psutil"] = MagicMock()

from hiveden.docker.containers import DockerManager


def test_get_container_config_parses_dependencies_from_labels():
    fake_container = SimpleNamespace(
        name="app",
        attrs={
            "Config": {
                "Image": "nginx:latest",
                "Cmd": None,
                "Env": [],
                "Labels": {"hiveden.dependencies": "postgres,redis"},
            },
            "HostConfig": {"PortBindings": {}, "Binds": [], "Devices": [], "Privileged": False},
        },
    )

    manager = DockerManager()
    manager.client = SimpleNamespace(
        containers=SimpleNamespace(
            get=lambda _container_id: fake_container,
        )
    )

    config = manager.get_container_config("ignored")
    assert config["dependencies"] == ["postgres", "redis"]
