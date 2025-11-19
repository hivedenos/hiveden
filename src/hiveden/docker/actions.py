from docker import errors

from hiveden.docker.containers import create_container, list_containers
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
        container_name = container_config["name"]
        image = container_config["image"]
        try:
            containers = list_containers(all=True, filters={"name": container_name})
            if not containers:
                create_container(
                    image=image,
                    name=container_name,
                    detach=True,
                    network_name=network_name,
                )
                messages.append(f"Container '{container_name}' created.")
            else:
                messages.append(f"Container '{container_name}' already exists.")
        except errors.ImageNotFound:
            messages.append(
                f"Image '{image}' not found for container '{container_name}'."
            )
        except errors.APIError as e:
            messages.append(f"Error creating container '{container_name}': {e}")

    return messages
