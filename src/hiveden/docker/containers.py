import docker
from docker import errors

from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.networks import create_network, network_exists

client = docker.from_env()


def create_container(
    image,
    command=None,
    network_name="hiveden-net",
    env=None,
    ports=None,
    **kwargs,
):
    """Create a new Docker container and connect it to the hiveden network."""
    if not image_exists(image):
        print(f"Image '{image}' not found locally. Pulling from registry...")
        try:
            pull_image(image)
            print(f"Image '{image}' pulled successfully.")
        except errors.ImageNotFound:
            raise errors.ImageNotFound(f"Image '{image}' not found in registry.")

    if not network_exists(network_name):
        create_network(network_name)

    labels = kwargs.get("labels", {})
    labels["managed-by"] = "hiveden"
    kwargs["labels"] = labels

    environment = []
    if env:
        for item in env:
            environment.append(f"{item.name}={item.value}")

    port_bindings = {}
    if ports:
        for port in ports:
            port_bindings[f"{port.container_port}/{port.protocol}"] = port.host_port

    container = client.containers.create(
        image, command, environment=environment, ports=port_bindings, **kwargs
    )
    network = client.networks.get(network_name)
    network.connect(container)
    return container


def get_container(container_id):
    """Get a Docker container by its ID."""
    return client.containers.get(container_id)


def list_containers(all=False, only_managed=False, **kwargs):
    """List all Docker containers."""
    if only_managed:
        kwargs["filters"] = {"label": "managed-by=hiveden"}

    return client.containers.list(all=all, **kwargs)


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
