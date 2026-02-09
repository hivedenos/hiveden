import os

def _parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class MetricsDependenciesConfig:
    def __init__(self, containers: list[str]):
        self.containers = containers


class MetricsConfig:
    def __init__(self, host: str, dependencies: MetricsDependenciesConfig):
        self.host = host
        self.dependencies = dependencies


class Config:
    def __init__(self):
        self.app_directory = os.getenv("HIVEDEN_APP_DIRECTORY", "/hiveden-temp-root/apps")
        self.movies_directory = os.getenv("HIVEDEN_MOVIES_DIRECTORY", "/hiveden-temp-root/movies")
        self.tvshows_directory = os.getenv("HIVEDEN_TVSHOWS_DIRECTORY", "/hiveden-temp-root/tvshows")
        self.backup_directory = os.getenv("HIVEDEN_BACKUP_DIRECTORY", "/hiveden-temp-root/backups")
        self.pictures_directory = os.getenv("HIVEDEN_PICTURES_DIRECTORY", "/hiveden-temp-root/pictures")
        self.documents_directory = os.getenv("HIVEDEN_DOCUMENTS_DIRECTORY", "/hiveden-temp-root/documents")
        self.ebooks_directory = os.getenv("HIVEDEN_EBOOKS_DIRECTORY", "/hiveden-temp-root/ebooks")
        self.music_directory = os.getenv("HIVEDEN_MUSIC_DIRECTORY", "/hiveden-temp-root/music")
        self.docker_network_name = os.getenv("HIVEDEN_DOCKER_NETWORK_NAME", "hiveden-net")
        self.domain = os.getenv("HIVEDEN_DOMAIN", "hiveden.local")

        # Pi-hole Configuration
        self.pihole_enabled = os.getenv("HIVEDEN_PIHOLE_ENABLED", "false").lower() == "true"
        self.pihole_host = os.getenv("HIVEDEN_PIHOLE_HOST", "http://pi.hole")
        self.pihole_password = os.getenv("HIVEDEN_PIHOLE_PASSWORD", "")

        # Metrics configuration
        self.metrics_host = os.getenv("HIVEDEN_METRICS_HOST", "http://prometheus:9090")
        self.metrics_dependencies_containers = os.getenv(
            "HIVEDEN_METRICS_DEPENDENCIES_CONTAINERS",
            "prometheus,cadvisor,node-exporter",
        )
        self.metrics = MetricsConfig(
            host=self.metrics_host,
            dependencies=MetricsDependenciesConfig(
                containers=_parse_csv_list(self.metrics_dependencies_containers)
            ),
        )

config = Config()
