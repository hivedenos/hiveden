from docker import errors

from hiveden.docker.containers import DockerManager
from hiveden.docker.models import DockerContainer
from hiveden.docker.networks import create_network, list_networks


def apply_configuration(config):
    """Apply the docker configuration."""
    messages = []
    network_name = config["network_name"]
    
    manager = DockerManager(network_name=network_name)

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
            manager.create_container(
                image=container.image,
                name=container.name,
                command=container.command,
                dependencies=container.dependencies,
                detach=True,
                network_name=network_name,
                env=container.env,
                ports=container.ports,
                mounts=container.mounts,
                labels=container.labels,
            )
        except errors.ImageNotFound as e:
            messages.append(str(e))
        except errors.APIError as e:
            messages.append(f"Error creating container '{container.name}': {e}")

    return messages
