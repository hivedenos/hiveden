import os

import docker
from docker import errors

from hiveden.config import config as app_config
from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.models import Container
from hiveden.docker.networks import create_network, network_exists
from hiveden.apps.traefik import generate_traefik_labels, TraefikClient
from hiveden.apps.pihole import PiHoleManager
from hiveden.hwosinfo.hw import get_host_ip

client = docker.from_env()


class DockerManager:
    def __init__(self, network_name="hiveden-network"):
        self.network_name = network_name
        self.client = client

    def _resolve_app_directory(self):
        """Resolve the effective application directory, preferring DB configuration."""
        app_root = app_config.app_directory
        try:
            from hiveden.db.session import get_db_manager
            from hiveden.db.repositories.locations import LocationRepository
            
            db_manager = get_db_manager()
            repo = LocationRepository(db_manager)
            apps_location = repo.get_by_key('apps')
            if apps_location:
                app_root = apps_location.path
        except Exception:
            pass
        return app_root

    def ensure_app_directory(self, container_name):
        """Ensure the container's application directory exists."""
        app_root = self._resolve_app_directory()
        container_dir = os.path.join(app_root, container_name)
        if not os.path.exists(container_dir):
            try:
                os.makedirs(container_dir, exist_ok=True)
                print(f"Created app directory: {container_dir}")
            except OSError as e:
                print(f"Error creating app directory {container_dir}: {e}")
                raise
        return container_dir

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
        devices=None,
        labels=None,
        ingress_config=None,
        app_directory=None,
        privileged=False,
        **kwargs,
    ):
        """Create a new Docker container and connect it to the hiveden network."""
        # Use instance network_name if not provided, though argument overrides it
        target_network = network_name or self.network_name
        # Use provided app_directory or resolve it
        effective_app_dir = app_directory or self._resolve_app_directory()

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
        
        if ingress_config:
            # Handle Ingress Configuration
            traefik_labels = generate_traefik_labels(ingress_config.domain, ingress_config.port)
            container_labels.update(traefik_labels)
            
            # Filter ports: Remove the port that is being managed by ingress
            if ports:
                ports = [p for p in ports if p.container_port != ingress_config.port]

            traefik_client = TraefikClient("http://localhost:8080")
            pihole_ip = traefik_client.get_service_ip("pihole")
            pihole_domains = traefik_client.find_domains_for_router("pihole")
            if len(pihole_domains) > 0 and len(pihole_ip) > 0:
                try:
                    pihole_manager = PiHoleManager(pihole_domains[0], app_config.pihole_password)
                    target_ip = ingress_config.host_ip or get_host_ip()
                    pihole_manager.add_ingress_domain_to_pihole(ingress_config.domain, target_ip)
                except Exception as e:
                    print(f"Failed to add ingress domain {ingress_config.domain} to pihole: {e}")

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

        container_name = kwargs.get("name", "")
        volumes = {}
        if mounts:
            for mount in mounts:
                source_path = mount.source
                if getattr(mount, "is_app_directory", False):
                    source_path = os.path.join(effective_app_dir, container_name, mount.source)
                    if not os.path.exists(source_path):
                        try:
                            os.makedirs(source_path, exist_ok=True)
                            print(f"Created app directory: {source_path}")
                        except OSError as e:
                            print(f"Error creating app directory {source_path}: {e}")

                mode = "ro" if getattr(mount, "read_only", False) else "rw"
                volumes[source_path] = {"bind": mount.target, "mode": mode}

        device_requests = []
        if devices:
            for device in devices:
                # Format: /host:/container:rwm
                device_str = f"{device.path_on_host}:{device.path_in_container}:{device.cgroup_permissions}"
                device_requests.append(device_str)

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
                devices=device_requests,
                restart_policy={"Name": "always"},
                privileged=privileged,
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
                devices=device_requests,
                restart_policy={"Name": "always"},
                privileged=privileged,
                **kwargs,
            )
            print(f"Container '{container_name}' created.")

        network = self.client.networks.get(target_network)
        network.connect(container)
        container.start()
        print(f"Container '{container_name}' started.")

        return container

    def get_container(self, container_id) -> Container:
        """Get a Docker container by its ID."""
        c = self.client.containers.get(container_id)

        try:
            image = c.image.tags[0] if c.image and c.image.tags else "N/A"
            image_id = c.image.id
        except errors.ImageNotFound:
            image = "Not Found (404)"
            image_id = "Not Found (404)"

        name = c.name if c.name else "N/A"
        ip_address = self.extract_ip(c.attrs)

        return Container(
            Id=c.id,
            Name=name,
            Image=image,
            ImageID=image_id,
            Command=c.attrs.get("Config", {}).get("Cmd", []) or [],
            Created=c.attrs.get("Created", 0),
            State=c.attrs.get("State", {}).get("Status", "N/A"),
            Status=c.status,
            Ports=c.attrs.get("NetworkSettings", {}).get("Ports", {}),
            Labels=c.labels,
            NetworkSettings=c.attrs.get("NetworkSettings", {}),
            HostConfig=c.attrs.get("HostConfig", {}),
            IPAddress=ip_address,
        )

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

            name = c.name if c.name else "N/A"

            ip_address = self.extract_ip(c.attrs)

            response_data.append(
                Container(
                    Id=c.id,
                    Name=name,
                    Image=image,
                    ImageID=image_id,
                    Command=c.attrs.get("Config", {}).get("Cmd", []) or [],
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

    def stream_logs(self, container_id, follow=True, tail=100):
        """Stream logs from a Docker container.

        Args:
            container_id: Container ID or name
            follow: If True, stream logs in real-time
            tail: Number of lines to show from the end (default 100)

        Yields:
            Log lines as they are generated
        """
        container = self.client.containers.get(container_id)

        # Stream logs
        for log_line in container.logs(stream=follow, follow=follow, tail=tail):
            # Decode bytes to string and yield
            yield log_line.decode('utf-8', errors='replace')

    def stop_containers(self, containers):
        """Stop a list of containers."""
        for container in containers:
            if container.Status != "running":
                print(f"Container '{container.Name}' is already stopped.")
                continue
            self.stop_container(container.Id)
            print(f"Container '{container.Name}' stopped.")

    def start_container(self, container_id):
        """Start a stopped Docker container."""
        # Use the raw client to get the container object, which has the .start() method
        container = self.client.containers.get(container_id)
        container.start()
        # Return the Pydantic model for the response
        return self.get_container(container_id)

    def restart_container(self, container_id):
        """Restart a Docker container."""
        container = self.client.containers.get(container_id)
        container.restart()
        return self.get_container(container_id)

    def stop_container(self, container_id):
        """Stop a running Docker container."""
        # Use the raw client to get the container object, which has the .stop() method
        container = self.client.containers.get(container_id)
        container.stop()
        # Return the Pydantic model for the response
        return self.get_container(container_id)

    def remove_container(self, container_id):
        """Remove a Docker container."""
        container = self.client.containers.get(container_id)

        if container.status == 'running':
            raise ValueError(f"Container '{container.name}' is currently running. Please stop it before removal.")

        container_model = self.get_container(container_id)
        container.remove()
        return container_model

    def delete_containers(self, containers):
        """Delete a list of containers."""
        for container in containers:
            if container.Status == "running":
                self.stop_container(container.Id)
            self.remove_container(container.Id)
            print(f"Container '{container.Name}' deleted.")

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
            Name=container.name or "N/A",
            Image=image,
            ImageID=image_id,
            Command=container.attrs.get("Config", {}).get("Cmd", []) or [],
            Created=container.attrs.get("Created", 0),
            State=container.attrs.get("State", {}).get("Status", "N/A"),
            Status=container.status,
            Ports=container.attrs.get("NetworkSettings", {}).get("Ports", {}),
            Labels=container.labels,
            NetworkSettings=container.attrs.get("NetworkSettings", {}),
            HostConfig=container.attrs.get("HostConfig", {}),
            IPAddress=ip_address,
        )


    def get_container_config(self, container_id):
        """Retrieve the configuration of a container."""
        c = self.client.containers.get(container_id)
        config = c.attrs['Config']
        host_config = c.attrs['HostConfig']

        # Env: ["VAR=VAL", ...] -> [{"name": "VAR", "value": "VAL"}]
        env = []
        for e in config.get('Env', []) or []:
            if '=' in e:
                k, v = e.split('=', 1)
                env.append({'name': k, 'value': v})

        # Ports: "80/tcp": [{"HostPort": "8080"}] -> [{"host_port": 8080, "container_port": 80, "protocol": "tcp"}]
        ports = []
        port_bindings = host_config.get('PortBindings') or {}
        for k, v in port_bindings.items():
            if v:
                host_port = v[0].get('HostPort')
                if '/' in k:
                    cp, proto = k.split('/')
                else:
                    cp, proto = k, 'tcp'
                ports.append({'host_port': int(host_port), 'container_port': int(cp), 'protocol': proto})

        # Mounts: Binds ["/host:/container:rw"] -> [{"source": "/host", "target": "/container"}]
        mounts = []
        binds = host_config.get('Binds') or []
        effective_app_dir = self._resolve_app_directory()
        
        for b in binds:
            parts = b.split(':')
            if len(parts) >= 2:
                source = parts[0]
                target = parts[1]
                read_only = False
                
                if len(parts) >= 3:
                     mode = parts[2]
                     if 'ro' in mode.split(','):
                         read_only = True

                is_app_dir = False

                if source == effective_app_dir or source.startswith(os.path.join(effective_app_dir, "")):
                    is_app_dir = True
                    source = os.path.relpath(source, effective_app_dir)

                mounts.append({'source': source, 'target': target, 'is_app_directory': is_app_dir, 'read_only': read_only})

        # Devices: [{"PathOnHost": "...", "PathInContainer": "...", "CgroupPermissions": "..."}]
        devices = []
        host_devices = host_config.get('Devices') or []
        for d in host_devices:
            devices.append({
                'path_on_host': d.get('PathOnHost'),
                'path_in_container': d.get('PathInContainer'),
                'cgroup_permissions': d.get('CgroupPermissions', 'rwm')
            })

        return {
            "name": c.name.lstrip('/'),
            "image": config.get('Image'),
            "command": config.get('Cmd'),
            "env": env,
            "ports": ports,
            "mounts": mounts,
            "devices": devices,
            "labels": config.get('Labels'),
            "privileged": host_config.get('Privileged', False),
            "is_container": True,
            "enabled": True,
            "type": "docker"
        }

    def update_container(self, container_id, config, app_directory=None):
        """Update a container by removing the old one and creating a new one."""
        try:
            old_container = self.client.containers.get(container_id)
            # Always remove the old container to avoid conflicts and ensure clean state
            # If name is same, create_container would handle it, but if name changed, we need this.
            old_container.remove(force=True)

        except errors.NotFound:
            print(f"Container {container_id} not found during update. Proceeding to create.")

        # Helper to get value from dict or object
        def get_val(obj, key):
            if isinstance(obj, dict):
                return obj.get(key)
            return getattr(obj, key, None)

        # Call create_container
        return self.create_container(
            name=get_val(config, 'name'),
            image=get_val(config, 'image'),
            command=get_val(config, 'command'),
            env=get_val(config, 'env'),
            ports=get_val(config, 'ports'),
            mounts=get_val(config, 'mounts'),
            devices=get_val(config, 'devices'),
            labels=get_val(config, 'labels'),
            ingress_config=get_val(config, 'ingress_config'),
            privileged=get_val(config, 'privileged') or False,
            app_directory=app_directory
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

def start_container(container_id):
    return DockerManager().start_container(container_id)

def restart_container(container_id):
    return DockerManager().restart_container(container_id)

def stop_container(container_id):
    return DockerManager().stop_container(container_id)

def remove_container(container_id):
    return DockerManager().remove_container(container_id)

def delete_containers(containers):
    return DockerManager().delete_containers(containers)

def describe_container(container_id=None, name=None):
    return DockerManager().describe_container(container_id, name)

def get_container_config(container_id):
    return DockerManager().get_container_config(container_id)

def update_container(container_id, config, app_directory=None):
    return DockerManager().update_container(container_id, config, app_directory)
