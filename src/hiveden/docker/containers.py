import docker
from docker import errors

from hiveden.docker.models import DockerContainer
from hiveden.docker.networks import create_network, network_exists

client = docker.from_env()


def create_container(image, command=None, network_name="hiveden-net", env=None, **kwargs):
    """Create a new Docker container and connect it to the hiveden network."""
    if not network_exists(network_name):
        create_network(network_name)

    labels = kwargs.get("labels", {})
    labels["managed-by"] = "hiveden"
    kwargs["labels"] = labels

    environment = []
    if env:
        for item in env:
            environment.append(f"{item.name}={item.value}")

    container = client.containers.create(image, command, environment=environment, **kwargs)
    network = client.networks.get(network_name)
    network.connect(container)
    return container


def get_container(container_id):
    """Get a Docker container by its ID."""
    return client.containers.get(container_id)


def list_containers(all=False, only_managed=False, **kwargs):
    """List all Docker containers."""
    response_data = []
    if only_managed:
        kwargs["filters"] = {"label": "managed-by=hiveden"}

    for c in client.containers.list(all=all, **kwargs):
        try:
            image = c.image.tags[0] if c.image and c.image.tags else "N/A"
        except errors.ImageNotFound:
            image = "Not Found (404)"
        response_data.append(
            DockerContainer(
                name=c.name,
                image=image,
                status=c.status,
                managed_by_hiveden="managed-by" in c.labels and c.labels["managed-by"] == "hiveden",
            )
        )
    return response_data



def stop_container(container_id):
    """Stop a running Docker container."""
    container = get_container(container_id)
    container.stop()
    return container


def remove_container(container_id):
    """Remove a Docker container."""
    container = get_container(container_id)
    container.remove()
    return container
