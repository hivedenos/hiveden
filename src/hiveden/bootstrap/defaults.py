from typing import List
from hiveden.docker.models import DockerContainer, EnvVar, Port, Mount

def get_default_containers() -> List[DockerContainer]:
    default_labels = {
        "hiveden.stack.name": "core",
        "managed-by": "hiveden"
    }
    
    return [
        DockerContainer(
            name="postgres",
            image="pgvector/pgvector:pg18-trixie",
            env=[
                EnvVar(name="POSTGRES_PASSWORD", value="postgres"),
                EnvVar(name="POSTGRES_DB", value="hiveden")
            ],
            ports=[Port(host_port=5432, container_port=5432, protocol="tcp")],
            mounts=[
                Mount(
                    source="postgres",  # Relative to app directory
                    target="/var/lib/postgresql",
                    type="bind",
                    is_app_directory=True
                )
            ],
            labels=default_labels
        ),
        DockerContainer(
            name="redis",
            image="redis:8.2.2-alpine",
            ports=[Port(host_port=6379, container_port=6379, protocol="tcp")],
            mounts=[
                Mount(
                    source="redis",  # Relative to app directory
                    target="/data",
                    type="bind",
                    is_app_directory=True
                )
            ],
            labels=default_labels
        ),
        DockerContainer(
            name="traefik",
            image="traefik:v3.5",
            command=[
                "--api.insecure=true",
                "--providers.docker=true",
                "--providers.docker.exposedbydefault=false",
                "--entrypoints.web.address=:80",
                "--entrypoints.websecure.address=:443"
            ],
            ports=[
                Port(host_port=80, container_port=80, protocol="tcp"),
                Port(host_port=443, container_port=443, protocol="tcp"),
                Port(host_port=8080, container_port=8080, protocol="tcp")
            ],
            mounts=[
                Mount(
                    source="/var/run/docker.sock",
                    target="/var/run/docker.sock",
                    type="bind",
                    is_app_directory=False
                )
            ],
            labels=default_labels
        ),
        DockerContainer(
            name="prometheus",
            image="prom/prometheus:v3.8.1",
            command=["--config.file=/etc/prometheus/prometheus.yml"],
            ports=[Port(host_port=9090, container_port=9090, protocol="tcp")],
            mounts=[
                Mount(
                    source="prometheus.yml",
                    target="/etc/prometheus/prometheus.yml",
                    type="bind",
                    is_app_directory=True,
                    read_only=True
                )
            ],
            labels=default_labels
        ),
        DockerContainer(
            name="cadvisor",
            image="gcr.io/cadvisor/cadvisor:latest",
            ports=[Port(host_port=8081, container_port=8080, protocol="tcp")],
            mounts=[
                Mount(source="/", target="/rootfs", type="bind", is_app_directory=False, read_only=True),
                Mount(source="/var/run", target="/var/run", type="bind", is_app_directory=False, read_only=False),
                Mount(source="/sys", target="/sys", type="bind", is_app_directory=False, read_only=True),
                Mount(source="/var/lib/docker", target="/var/lib/docker", type="bind", is_app_directory=False, read_only=True),
            ],
            labels=default_labels
        ),
        DockerContainer(
            name="node-exporter",
            image="prom/node-exporter:v1.10.2",
            command=[
                "--path.procfs=/host/proc",
                "--path.sysfs=/host/sys",
                "--path.rootfs=/host/root"
            ],
            ports=[Port(host_port=9100, container_port=9100, protocol="tcp")],
            mounts=[
                Mount(source="/proc", target="/host/proc", type="bind", is_app_directory=False, read_only=True),
                Mount(source="/sys", target="/host/sys", type="bind", is_app_directory=False, read_only=True),
                Mount(source="/", target="/host/root", type="bind", is_app_directory=False, read_only=True),
            ],
            labels=default_labels
        )
    ]
