import docker
from docker import errors

from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.models import Container
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

    response_data = []
    for c in client.containers.list(all=all, **kwargs):
        try:
            image = c.image.tags[0] if c.image and c.image.tags else "N/A"
            image_id = c.image.id
        except errors.ImageNotFound:
            image = "Not Found (404)"
            image_id = "Not Found (404)"

        names = [c.name] if c.name else []

        response_data.append(
            Container(
                Id=c.id,
                Names=names,
                Image=image,
                ImageID=image_id,
                Command=(
                    " ".join(c.attrs.get("Config", {}).get("Cmd", []))
                    if c.attrs.get("Config", {}).get("Cmd")
                    else ""
                ),
                Created=c.attrs.get("Created", 0),
                State=c.attrs.get("State", {}).get("Status", "N/A"),
                Status=c.status,
                Ports=c.attrs.get("NetworkSettings", {}).get("Ports", {}),
                Labels=c.labels,
                NetworkSettings=c.attrs.get("NetworkSettings", {}),
                HostConfig=c.attrs.get("HostConfig", {}),
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


def describe_container(container_id=None, name=None):
    """Describe a Docker container by its ID or name."""
    search_by = ""
    if not container_id and not name:
        raise ValueError("Either container_id or name must be provided.")

    if container_id:
        search_by = container_id

    if name and search_by == "":
        search_by = name


    container = None
    try:
        container = client.containers.get(search_by)
    except errors.NotFound or errors.NullResource:
        raise errors.NotFound(f"Container '{container_id or name}' not found.")

    try:
        image = container.image.tags[0] if container.image and container.image.tags else "N/A"
        image_id = container.image.id or "N/A"
    except errors.ImageNotFound:
        image = "Not Found (404)"
        image_id = "Not Found (404)"


    return Container(
        Id=container.id or "N/A",
        Names=[container.name or "N/A"],
        Image=image,
        ImageID=image_id,
        Command=(
            " ".join(container.attrs.get("Config", {}).get("Cmd", []))
            if container.attrs.get("Config", {}).get("Cmd")
            else ""
        ),
        Created=container.attrs.get("Created", 0),
        State=container.attrs.get("State", {}).get("Status", "N/A"),
        Status=container.status,
        Ports=container.attrs.get("NetworkSettings", {}).get("Ports", {}),
        Labels=container.labels,
        NetworkSettings=container.attrs.get("NetworkSettings", {}),
        HostConfig=container.attrs.get("HostConfig", {}),
    )
