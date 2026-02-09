from types import SimpleNamespace

from hiveden.api.routers import system


def test_get_metrics_config_resolves_prometheus_host(monkeypatch):
    class FakeDockerManager:
        def list_containers(self, all=False):
            return [SimpleNamespace(Id="abc123", Image="prom/prometheus:v3.8.1")]

        def get_container_config(self, container_id):
            return {
                "labels": {
                    "traefik.http.routers.prom.rule": "Host(`metrics.hiveden.local`)",
                    "traefik.http.routers.prom.entrypoints": "websecure",
                }
            }

    monkeypatch.setattr(system, "DockerManager", lambda: FakeDockerManager())

    test_metrics = SimpleNamespace(
        dependencies=SimpleNamespace(containers=["prometheus", "cadvisor", "node-exporter"]),
    )
    monkeypatch.setattr(system, "config", SimpleNamespace(metrics=test_metrics))

    response = system.get_metrics_config()
    data = response.model_dump()

    assert data["host"] == "https://metrics.hiveden.local"
    assert data["dependencies"]["containers"] == ["prometheus", "cadvisor", "node-exporter"]


def test_get_metrics_config_returns_null_host_when_unresolved(monkeypatch):
    class FakeDockerManager:
        def list_containers(self, all=False):
            return [SimpleNamespace(Id="abc123", Image="prom/prometheus:v3.8.1")]

        def get_container_config(self, container_id):
            return {"labels": {}}

    monkeypatch.setattr(system, "DockerManager", lambda: FakeDockerManager())

    test_metrics = SimpleNamespace(
        dependencies=SimpleNamespace(containers=["prometheus", "cadvisor", "node-exporter"]),
    )
    monkeypatch.setattr(system, "config", SimpleNamespace(metrics=test_metrics))

    response = system.get_metrics_config()
    data = response.model_dump()

    assert data["host"] is None
    assert data["dependencies"]["containers"] == ["prometheus", "cadvisor", "node-exporter"]


def test_get_traefik_url_from_labels_supports_single_quotes():
    labels = {
        "traefik.http.routers.prom.rule": "Host('metrics.hiveden.local')",
        "traefik.http.routers.prom.entrypoints": "web",
    }
    assert system.get_traefik_url_from_labels(labels) == "http://metrics.hiveden.local"
