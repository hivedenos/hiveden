import docker
from docker import errors

from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.models import Container
from hiveden.docker.networks import create_network, network_exists

client = docker.from_env()


import docker
from docker import errors

from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.models import Container
from hiveden.docker.networks import create_network, network_exists

client = docker.from_env()


class DockerManager:
    def __init__(self, network_name="hiveden-network"):
        self.network_name = network_name
        self.client = client

    def extract_ip(self, container_attrs):
        """Extract IP address from container attributes."""
        ip_address = None
        networks = container_attrs.get("NetworkSettings", {}).get("Networks", {})
        
        if self.network_name in networks:
            ip_address = networks[self.network_name].get("IPAddress")
        elif networks:
            # Fallback to first network
            first_net = next(iter(networks.values()))
            ip_address = first_net.get("IPAddress")
        return ip_address

    def create_container(
        self,
        image,
        command=None,
        network_name=None,
        env=None,
        ports=None,
        mounts=None,
        labels=None,
        **kwargs,
    ):
        """Create a new Docker container and connect it to the hiveden network."""
        # Use instance network_name if not provided, though argument overrides it
        target_network = network_name or self.network_name

        if not image_exists(image):
            print(f"Image '{image}' not found locally. Pulling from registry...")
            try:
                pull_image(image)
                print(f"Image '{image}' pulled successfully.")
            except errors.ImageNotFound:
                raise errors.ImageNotFound(f"Image '{image}' not found in registry.")

        if not network_exists(target_network):
            create_network(target_network)

        container_labels = kwargs.get("labels", {})
        if labels:
            container_labels.update(labels)
        container_labels["managed-by"] = "hiveden"
        kwargs["labels"] = container_labels

        environment = []
        if env:
            for item in env:
                environment.append(f"{item.name}={item.value}")

        port_bindings = {}
        if ports:
            for port in ports:
                port_bindings[f"{port.container_port}/{port.protocol}"] = port.host_port

        volumes = {}
        if mounts:
            for mount in mounts:
                volumes[mount.source] = {"bind": mount.target, "mode": "rw"}

        container_name = kwargs.get("name", "")
        try:
            container = self.client.containers.get(container_name)
            print(f"Container '{container_name}' already exists. Recreating with new configuration...")
            container.stop()
            container.remove()
            container = self.client.containers.create(
                image,
                command,
                environment=environment,
                ports=port_bindings,
                volumes=volumes,
                restart_policy="always",
                **kwargs,
            )
            print(f"Container '{container_name}' recreated.")
        except errors.NotFound:
            container = self.client.containers.create(
                image,
                command,
                environment=environment,
                ports=port_bindings,
                volumes=volumes,
                restart_policy="always",
                **kwargs,
            )
            print(f"Container '{container_name}' created.")

        network = self.client.networks.get(target_network)
        network.connect(container)
        container.start()
        print(f"Container '{container_name}' started.")

        return container

    def get_container(self, container_id):
        """Get a Docker container by its ID."""
        return self.client.containers.get(container_id)

    def list_containers(self, all=False, only_managed=False, names=None, **kwargs) -> list[Container]:
        """List all Docker containers."""
        if only_managed:
            kwargs["filters"] = {"label": "managed-by=hiveden"}

        if names:
            kwargs["filters"] = {"name": names}

        response_data = []
        for c in self.client.containers.list(all=all, **kwargs):
            try:
                image = c.image.tags[0] if c.image and c.image.tags else "N/A"
                image_id = c.image.id
            except errors.ImageNotFound:
                image = "Not Found (404)"
                image_id = "Not Found (404)"

            names = [c.name] if c.name else []

            ip_address = self.extract_ip(c.attrs)

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
                    IPAddress=ip_address,
                )
            )
        return response_data

    def stop_containers(self, containers):
        """Stop a list of containers."""
        for container in containers:
            if container.Status != "running":
                print(f"Container '{container.Names[0]}' is already stopped.")
                continue
            self.stop_container(container.Id)
            print(f"Container '{container.Names[0]}' stopped.")

    def stop_container(self, container_id):
        """Stop a running Docker container."""
        container = self.get_container(container_id)
        container.stop()
        return container

    def remove_container(self, container_id):
        """Remove a Docker container."""
        container = self.get_container(container_id)
        container.remove()
        return container

    def delete_containers(self, containers):
        """Delete a list of containers."""
        for container in containers:
            if container.Status == "running":
                self.stop_container(container.Id)
            self.remove_container(container.Id)
            print(f"Container '{container.Names[0]}' deleted.")

    def describe_container(self, container_id=None, name=None):
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
            container = self.client.containers.get(search_by)
        except errors.NotFound or errors.NullResource:
            raise errors.NotFound(f"Container '{container_id or name}' not found.")

        try:
            image = container.image.tags[0] if container.image and container.image.tags else "N/A"
            image_id = container.image.id or "N/A"
        except errors.ImageNotFound:
            image = "Not Found (404)"
            image_id = "Not Found (404)"

        ip_address = self.extract_ip(container.attrs)

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
            IPAddress=ip_address,
        )


# Wrappers for backward compatibility
def create_container(*args, **kwargs):
    return DockerManager().create_container(*args, **kwargs)

def get_container(container_id):
    return DockerManager().get_container(container_id)

def list_containers(*args, **kwargs):
    return DockerManager().list_containers(*args, **kwargs)

def stop_containers(containers):
    return DockerManager().stop_containers(containers)

def stop_container(container_id):
    return DockerManager().stop_container(container_id)

def remove_container(container_id):
    return DockerManager().remove_container(container_id)

def delete_containers(containers):
    return DockerManager().delete_containers(containers)

def describe_container(container_id=None, name=None):
    return DockerManager().describe_container(container_id, name)
