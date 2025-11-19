from docker import errors

from hiveden.docker.containers import create_container, list_containers
from hiveden.docker.models import DockerContainer
from hiveden.docker.networks import create_network, list_networks


def apply_configuration(config):
    """Apply the docker configuration."""
    messages = []
    network_name = config["network_name"]

    # Create network
    try:
        networks = list_networks(names=[network_name])
        if not networks:
            create_network(network_name)
            messages.append(f"Network '{network_name}' created.")
        else:
            messages.append(f"Network '{network_name}' already exists.")
    except errors.APIError as e:
        messages.append(f"Error creating network: {e}")

    # Create containers
    for container_config in config["containers"]:
        container = DockerContainer(**container_config)
        try:
            containers = list_containers(all=True, filters={"name": container.name})
            if not containers:
                create_container(
                    image=container.image,
                    name=container.name,
                    command=container.command,
                    detach=True,
                    network_name=network_name,
                    env=container.env,
                    ports=container.ports,
                )
                messages.append(f"Container '{container.name}' created.")
            else:
                messages.append(f"Container '{container.name}' already exists.")
        except errors.ImageNotFound:
            messages.append(
                f"Image '{container.image}' not found for container '{container.name}'."
            )
        except errors.APIError as e:
            messages.append(f"Error creating container '{container.name}': {e}")

    return messages
