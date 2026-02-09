import importlib


def test_metrics_config_defaults(monkeypatch):
    monkeypatch.delenv("HIVEDEN_METRICS_HOST", raising=False)
    monkeypatch.delenv("HIVEDEN_METRICS_DEPENDENCIES_CONTAINERS", raising=False)

    import hiveden.config.settings as settings_module

    importlib.reload(settings_module)
    cfg = settings_module.config

    assert cfg.metrics.host == "http://prometheus:9090"
    assert cfg.metrics.dependencies.containers == ["prometheus", "cadvisor", "node-exporter"]


def test_metrics_config_csv_parsing(monkeypatch):
    monkeypatch.setenv("HIVEDEN_METRICS_HOST", "http://metrics.local:9090")
    monkeypatch.setenv("HIVEDEN_METRICS_DEPENDENCIES_CONTAINERS", "prometheus, cadvisor, ,node-exporter ,")

    import hiveden.config.settings as settings_module

    importlib.reload(settings_module)
    cfg = settings_module.config

    assert cfg.metrics.host == "http://metrics.local:9090"
    assert cfg.metrics.dependencies.containers == ["prometheus", "cadvisor", "node-exporter"]
