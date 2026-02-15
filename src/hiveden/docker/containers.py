import os

import docker
from docker import errors

from hiveden.apps.pihole import PiHoleManager
from hiveden.apps.traefik import generate_traefik_labels
from hiveden.config import config as app_config
from hiveden.config.utils.domain import get_system_domain_value
from hiveden.docker.dependencies import (
    DEPENDENCIES_LABEL_KEY,
    evaluate_dependencies,
    parse_dependencies_label,
    serialize_dependencies_label,
)
from hiveden.docker.images import image_exists, pull_image
from hiveden.docker.models import Container, Device, EnvVar, IngressConfig, Mount, Port
from hiveden.docker.networks import create_network, network_exists
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
            from hiveden.db.repositories.locations import LocationRepository
            from hiveden.db.session import get_db_manager

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
        name: str,
        image: str,
        command: list[str]|None=None,
        dependencies: list[str]|None=None,
        network_name=None,
        env: list[EnvVar]|None=None,
        ports: list[Port]|None=None,
        mounts: list[Mount]|None=None,
        devices:list[Device]|None=None,
        labels: dict[str, str]|None=None,
        ingress_config: IngressConfig|None=None,
        app_directory=None,
        privileged: bool|None=False,
        **kwargs,
    ):
        """Create a new Docker container and connect it to the hiveden network."""
        # Use instance network_name if not provided, though argument overrides it
        target_network = network_name or self.network_name
        # Use provided app_directory or resolve it
        effective_app_dir = app_directory or self._resolve_app_directory()
        self.ensure_dependencies_exist(dependencies)

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
        serialized_dependencies = serialize_dependencies_label(dependencies)
        if serialized_dependencies:
            container_labels[DEPENDENCIES_LABEL_KEY] = serialized_dependencies
        else:
            container_labels.pop(DEPENDENCIES_LABEL_KEY, None)

        if ingress_config:
            # Handle Ingress Configuration
            traefik_labels = generate_traefik_labels(ingress_config.domain, ingress_config.port)
            container_labels.update(traefik_labels)

            # Filter ports: Remove the port that is being managed by ingress
            if ports:
                ports = [p for p in ports if p.container_port != ingress_config.port]

            # Construct PiHole URL based on system domain
            # "The pihole subdomain is 'dns'"
            try:
                system_domain = get_system_domain_value()
                pihole_host = f"http://dns.{system_domain}"

                # Fetch API Key from DB
                from hiveden.db.repositories.core import (
                    ConfigRepository,
                    ModuleRepository,
                )
                from hiveden.db.session import get_db_manager

                pihole_password = app_config.pihole_password
                try:
                    db_manager = get_db_manager()
                    module_repo = ModuleRepository(db_manager)
                    config_repo = ConfigRepository(db_manager)
                    core_module = module_repo.get_by_short_name('core')
                    if core_module:
                        cfg_key = config_repo.get_by_module_and_key(core_module.id, 'dns.api_key')
                        if cfg_key and cfg_key['value']:
                            pihole_password = cfg_key['value']
                except Exception as ex:
                    print(f"Failed to fetch DNS API key from DB, using default: {ex}")

                # We assume standard port 80/443 or routed via Traefik
                # Try to use this host
                pihole_manager = PiHoleManager(pihole_host, pihole_password)
                target_ip = get_host_ip()
                pihole_manager.add_ingress_domain_to_pihole(f"{ingress_config.domain}.{system_domain}", target_ip)
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

        container_name = name
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
                name=container_name,
                **kwargs,
            )
            print(f"Container '{container_name}' created.")

        network = self.client.networks.get(target_network)
        network.connect(container)
        container.start()
        print(f"Container '{container_name}' started.")

        # Update core.dns.type if this is a DNS container
        try:
            target_dns_type = None
            image_lower = image.lower()
            for dns_type in ["pihole", "adguard"]:
                if dns_type in image_lower:
                    target_dns_type = dns_type
                    break

            if target_dns_type:
                from hiveden.db.repositories.core import ConfigRepository
                from hiveden.db.session import get_db_manager

                db_manager = get_db_manager()
                config_repo = ConfigRepository(db_manager)
                config_repo.set_value('core', 'dns.type', target_dns_type)
                print(f"Updated core.dns.type to {target_dns_type}")
        except Exception as e:
            print(f"Failed to update DNS config: {e}")

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

    def remove_container(self, container_id, delete_database=False, delete_volumes=False, delete_dns=False):
        """Remove a Docker container."""
        container = self.client.containers.get(container_id)

        if container.status == 'running':
            raise ValueError(f"Container '{container.name}' is currently running. Please stop it before removal.")

        # Capture info for cleanup
        container_name = container.name.lstrip('/')
        labels = container.labels

        # Cleanup DNS Entry (Before removal if we need IP, but usually we need domain from labels)
        if delete_dns:
            try:
                # Find Traefik Host Rule
                domain = None
                for k, v in labels.items():
                    if "traefik.http.routers." in k and ".rule" in k and v.startswith("Host("):
                        # Extract domain from Host(`example.com`) or Host('example.com')
                        try:
                            # Split by backtick or single quote
                            if "`" in v:
                                domain = v.split("`")[1]
                            elif "'" in v:
                                domain = v.split("'")[1]
                            break
                        except IndexError:
                            pass

                if domain:
                    # Setup PiHole Manager similar to create_container
                    from hiveden.apps.pihole import PiHoleManager
                    from hiveden.config import config as app_config
                    from hiveden.config.utils.domain import get_system_domain_value
                    from hiveden.db.repositories.core import (
                        ConfigRepository,
                        ModuleRepository,
                    )
                    from hiveden.db.session import get_db_manager
                    from hiveden.hwosinfo.hw import get_host_ip

                    system_domain = get_system_domain_value()
                    pihole_host = f"http://dns.{system_domain}"

                    pihole_password = app_config.pihole_password
                    try:
                        db_manager = get_db_manager()
                        module_repo = ModuleRepository(db_manager)
                        config_repo = ConfigRepository(db_manager)
                        core_module = module_repo.get_by_short_name('core')
                        if core_module:
                            cfg_key = config_repo.get_by_module_and_key(core_module.id, 'dns.api_key')
                            if cfg_key and cfg_key['value']:
                                pihole_password = cfg_key['value']
                    except Exception as ex:
                        print(f"Failed to fetch DNS API key from DB, using default: {ex}")

                    pihole_manager = PiHoleManager(pihole_host, pihole_password)

                    # We need the IP to delete the record. Typically host IP for ingress.
                    target_ip = get_host_ip()
                    # Alternatively, fetch current A record from Pi-hole if possible, but delete usually requires IP match

                    print(f"Deleting DNS entry: {domain} -> {target_ip}")
                    pihole_manager.delete_dns_entry(domain, target_ip)
                else:
                    print(f"No domain found in labels for container {container_name}, skipping DNS deletion.")

            except Exception as e:
                print(f"Error deleting DNS entry for {container_name}: {e}")

        container_model = self.get_container(container_id)
        container.remove()

        # Cleanup Volumes (App Directory)
        if delete_volumes:
            try:
                import shutil
                app_root = self._resolve_app_directory()
                app_dir = f"{app_root}/{container_name}"
                if os.path.exists(app_dir):
                    shutil.rmtree(app_dir)
                    print(f"Deleted app directory: {app_dir}")
            except Exception as e:
                print(f"Error deleting app directory for {container_name}: {e}")

        # Cleanup Database
        if delete_database:
            try:
                from hiveden.db.session import get_db_manager
                db_manager = get_db_manager()

                # Infer DB Name
                db_name = labels.get("hiveden.database.name")
                if not db_name:
                    db_name = container_name

                # Check if DB exists
                # list_databases returns list of RealDictRow(name=..., ...)
                databases = db_manager.list_databases()
                exists = any(db['name'] == db_name for db in databases)

                if exists:
                    try:
                        db_manager.delete_database(db_name)
                        print(f"Deleted database: {db_name}")
                    except ValueError as ve:
                        print(f"Skipped deleting protected database {db_name}: {ve}")
                else:
                    print(f"Database {db_name} not found, skipping deletion.")

            except Exception as e:
                print(f"Error deleting database for {container_name}: {e}")

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

    def list_existing_container_names(self) -> set[str]:
        """List all container names known by the local Docker daemon."""
        names = set()
        for container in self.client.containers.list(all=True):
            if container.name:
                names.add(container.name.lstrip('/'))
        return names

    def check_dependencies(self, dependencies: list[str] | None) -> dict:
        """Check whether all dependency container names exist."""
        return evaluate_dependencies(dependencies or [], self.list_existing_container_names())

    def ensure_dependencies_exist(self, dependencies: list[str] | None):
        """Raise ValueError when one or more dependency containers are missing."""
        result = self.check_dependencies(dependencies)
        if not result["all_satisfied"]:
            missing = ", ".join(result["missing"])
            raise ValueError(f"Missing container dependencies: {missing}")


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
                    source = os.path.relpath(source, f"{effective_app_dir}/{c.name}")

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
            "dependencies": parse_dependencies_label(
                (config.get('Labels') or {}).get(DEPENDENCIES_LABEL_KEY)
            ),
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
            dependencies=get_val(config, 'dependencies'),
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
def create_container(name: str, image: str, command: list[str]|None=None, dependencies: list[str]|None=None, env: list[EnvVar]|None=None, ports: list[Port]|None=None, mounts: list[Mount]|None=None, devices: list[Device]|None=None, labels: dict[str, str]|None=None, ingress_config: IngressConfig|None=None, privileged: bool|None=False, *args, **kwargs):
    return DockerManager().create_container(name=name, image=image, command=command, dependencies=dependencies, env=env, ports=ports, mounts=mounts, devices=devices, labels=labels, ingress_config=ingress_config, privileged=privileged, **kwargs)

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

def remove_container(container_id, delete_database=False, delete_volumes=False, delete_dns=False):
    return DockerManager().remove_container(container_id, delete_database, delete_volumes, delete_dns)

def delete_containers(containers):
    return DockerManager().delete_containers(containers)

def describe_container(container_id=None, name=None):
    return DockerManager().describe_container(container_id, name)

def get_container_config(container_id):
    return DockerManager().get_container_config(container_id)

def update_container(container_id, config, app_directory=None):
    return DockerManager().update_container(container_id, config, app_directory)
