import os
import re
import shutil
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from hiveden.db.session import get_db_manager
from hiveden.db.repositories.locations import LocationRepository
from hiveden.db.repositories.core import ConfigRepository, ModuleRepository
from hiveden.docker.containers import DockerManager
from hiveden.config.settings import config
from hiveden.config.utils.domain import get_system_domain_value
from hiveden.api.dtos import (
    SuccessResponse,
    LocationListResponse,
    DomainInfoResponse,
    DomainUpdateRequest,
    DomainUpdateResponse,
    IngressContainerInfo,
    DNSConfigResponse,
    DNSUpdateRequest,
    MetricsConfigResponse,
    MetricsDependenciesConfig,
    UpdateLocationRequest
)
from hiveden.explorer.models import FilesystemLocation
from hiveden.docker.models import IngressConfig
from hiveden.services.logs import LogService

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)

def _extract_traefik_domain_from_rule(rule: str) -> Optional[str]:
    """Extract first host from a Traefik Host(...) rule."""
    if "Host(" not in rule:
        return None

    match = re.search(r"Host\((.*?)\)", rule)
    if not match:
        return None

    host_part = match.group(1)
    host_match = re.search(r"[`'\"]([^`'\"]+)[`'\"]", host_part)
    if not host_match:
        return None

    return host_match.group(1).strip()


def _get_traefik_scheme(labels: dict) -> str:
    """Infer URL scheme from Traefik entrypoint labels."""
    for key, value in labels.items():
        if ".entrypoints" not in key:
            continue

        value_l = str(value).lower()
        if "websecure" in value_l:
            return "https://"
        if "web" in value_l:
            return "http://"

    return "http://"


def get_traefik_url_from_labels(labels: dict) -> Optional[str]:
    """Extract full URL from Traefik labels if Host rule exists."""
    if not labels:
        return None

    for key, value in labels.items():
        if ".rule" in key and "Host(" in str(value):
            domain = _extract_traefik_domain_from_rule(str(value))
            if domain:
                return f"{_get_traefik_scheme(labels)}{domain}"
    return None


def parse_ingress_from_labels(domain: str, labels: dict) -> Optional[IngressConfig]:
    """Reconstruct IngressConfig from Traefik labels."""
    if not labels:
        return None

    port = None
    router_rule = None
    entrypoint = None

    for k, v in labels.items():
        if "loadbalancer.server.port" in k:
            try:
                port = int(v)
            except:
                pass
        if ".rule" in k and "Host(" in v:
            router_rule = v
        if ".entrypoints" in k and "websecure" in v:
            entrypoint = "https://"
        elif ".entrypoints" in k and "web" in v:
            entrypoint = "http://"

    if port and router_rule and entrypoint:
        try:
            domain_part = router_rule.split("Host(`")[1].split("`)")[0]

            if domain in domain_part:
                return IngressConfig(domain=f"{entrypoint}{domain_part}", port=port)
        except Exception as e:
            logger.error(f"Failed to parse ingress from labels: {e}")
            pass

    return None

def resolve_prometheus_metrics_host(docker_manager: DockerManager) -> Optional[str]:
    """Resolve Prometheus host from running container Traefik labels."""
    try:
        containers = docker_manager.list_containers(all=False)
    except Exception as e:
        logger.warning(f"Failed to list containers for metrics host resolution: {e}")
        return None

    for c in containers:
        image = (c.Image or "").lower()
        if "prometheus" not in image:
            continue

        try:
            config_dict = docker_manager.get_container_config(c.Id)
            labels = config_dict.get("labels", {})
            resolved_url = get_traefik_url_from_labels(labels)
            if resolved_url:
                return resolved_url
        except Exception as e:
            logger.warning(f"Failed to inspect container {c.Id} for metrics host: {e}")

    return None

@router.get("/domain", response_model=DomainInfoResponse)
def get_system_domain():
    """Get the current system domain and accessible containers."""
    domain = get_system_domain_value()

    docker_manager = DockerManager()
    containers = docker_manager.list_containers(only_managed=True)

    ingress_list = []
    for c in containers:
        config_dict = docker_manager.get_container_config(c.Id)
        labels = config_dict.get('labels', {})
        ingress = parse_ingress_from_labels(domain, labels)

        if ingress:
            url = ingress.domain
            ingress_list.append(IngressContainerInfo(
                name=c.Name,
                id=c.Id,
                url=url
            ))

    return DomainInfoResponse(domain=domain, containers=ingress_list)

@router.get("/dns", response_model=DNSConfigResponse)
def get_dns_config():
    """
    Get DNS configuration and Pi-hole status.
    """
    db_manager = get_db_manager()
    module_repo = ModuleRepository(db_manager)
    config_repo = ConfigRepository(db_manager)

    # 1. Get Domain and API Key from DB
    dns_domain = None
    api_key = None
    try:
        core_module = module_repo.get_by_short_name('core')
        if core_module:
            # Get domain
            cfg_domain = config_repo.get_by_module_and_key(core_module.id, 'dns.domain')
            if cfg_domain:
                dns_domain = cfg_domain['value']

            # Get API Key
            cfg_key = config_repo.get_by_module_and_key(core_module.id, 'dns.api_key')
            if cfg_key:
                api_key = cfg_key['value']

    except Exception as e:
        logger.warning(f"Failed to fetch DNS config from DB: {e}")

    # 2. Check for Pi-hole Container
    docker_manager = DockerManager()
    containers = docker_manager.list_containers(all=False) # Only running containers

    pihole_enabled = False
    container_id = None

    for c in containers:
        # Check image name for 'pihole'
        if c.Image and "pihole" in c.Image.lower():
            pihole_enabled = True
            container_id = c.Id
            break

    return DNSConfigResponse(
        enabled=pihole_enabled,
        domain=dns_domain,
        container_id=container_id,
        api_key=api_key
    )

@router.put("/dns", response_model=SuccessResponse)
def update_dns_config(req: DNSUpdateRequest):
    """
    Update DNS API key.
    """
    db_manager = get_db_manager()
    config_repo = ConfigRepository(db_manager)

    try:
        config_repo.set_value('core', 'dns.api_key', req.api_key)

        LogService().info(
            actor="user",
            action="system.dns.update",
            message="Updated DNS API configuration",
            module="system"
        )

        return SuccessResponse(message="DNS configuration updated successfully.")
    except Exception as e:
        logger.error(f"Failed to update DNS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=MetricsConfigResponse)
def get_metrics_config():
    """Get metrics configuration for UI."""
    metrics_host = resolve_prometheus_metrics_host(DockerManager())
    return MetricsConfigResponse(
        host=metrics_host,
        dependencies=MetricsDependenciesConfig(
            containers=config.metrics.dependencies.containers
        )
    )

@router.put("/domain", response_model=DomainUpdateResponse)
def update_system_domain(req: DomainUpdateRequest):
    """Update system domain and recreate accessible containers."""
    new_domain = req.domain
    existing_domain = get_system_domain_value()

    # 1. Update DB
    db_manager = get_db_manager()
    config_repo = ConfigRepository(db_manager)
    config_repo.set_value('core', 'domain', new_domain)

    LogService().info(
        actor="user",
        action="system.domain.update",
        message=f"Updated system domain to {new_domain}",
        module="system",
        metadata={"old_domain": existing_domain, "new_domain": new_domain}
    )

    # 2. Recreate Containers
    docker_manager = DockerManager()
    containers = docker_manager.list_containers(only_managed=True)
    updated_list = []

    for c in containers:
        config_dict = docker_manager.get_container_config(c.Id)
        labels = config_dict.get('labels', {})
        current_ingress = parse_ingress_from_labels(existing_domain, labels)

        if current_ingress:
            logger.info(f"Updating domain for container {c.Name}...")

            # Determine new FQDN
            # Heuristic: If old was "plex.old.com", and new domain is "new.com",
            # we want "plex.new.com".
            # We need the subdomain.
            old_fqdn = current_ingress.domain

            # Get current system domain to strip it?
            # Or just assume the first part is subdomain?
            # Safer: Look at container name or 'hiveden.service' label if we had one.
            # Fallback: container name.
            # E.g. Name: plex -> plex.new_domain

            # Assumption: We want {container_name}.{new_domain}
            # Exceptions: Traefik dashboard?

            # Let's use container name as subdomain default
            subdomain = c.Name.lower()
            new_fqdn = f"{subdomain}.{new_domain}"

            # Create new IngressConfig
            new_ingress_config = IngressConfig(
                domain=new_fqdn,
                port=current_ingress.port
            )

            # Inject into config_dict for update_container
            config_dict['ingress_config'] = new_ingress_config

            # Update
            try:
                docker_manager.update_container(c.Id, config_dict)
                updated_list.append(c.Name)
            except Exception as e:
                logger.error(f"Failed to update container {c.Name}: {e}")

    return DomainUpdateResponse(
        status="success",
        message="Domain updated successfully",
        updated_containers=updated_list
    )

@router.get("/locations", response_model=LocationListResponse)
def get_system_locations():
    """
    Retrieve all system locations (system_root).
    """
    db_manager = get_db_manager()
    repo = LocationRepository(db_manager)
    locations = repo.get_system_locations()
    return LocationListResponse(data=locations)

def perform_location_update(key: str, new_path: str, old_path: str):
    """
    Background task to perform the potentially long-running operation
    of moving files and recreating containers.
    """
    docker_manager = DockerManager()

    try:
        logger.info(f"Starting location update for '{key}': {old_path} -> {new_path}")

        # 1. Identify Affected Containers
        # We need to find containers that use this path.
        # If key is 'apps', create_container handles it via app_directory param.
        # If key is 'movies' etc., they are likely bind mounts.

        affected_containers = []
        all_containers = docker_manager.list_containers(only_managed=True)

        for c in all_containers:
            config = docker_manager.get_container_config(c.Id)
            mounts = config.get('mounts', [])
            is_affected = False

            # Check if container uses this path
            if key == 'apps':
                # For apps, we check if any mount is marked as app_directory relative
                # OR if the absolute source starts with old_path
                # Note: get_container_config returns relative paths for 'is_app_directory=True'
                # but we should check if the container relies on app root.
                # Simplest heuristic: all managed containers rely on apps root if they have app_dir mounts.
                for m in mounts:
                    if m.get('is_app_directory'):
                        is_affected = True
                        break
            else:
                # For other keys (movies, etc), check if bind source starts with old_path
                for m in mounts:
                    source = m.get('source')
                    # If it's not an app dir mount, source is absolute path on host
                    if not m.get('is_app_directory') and source and source.startswith(old_path):
                        is_affected = True
                        break

            if is_affected:
                affected_containers.append((c.Id, config))

        logger.info(f"Found {len(affected_containers)} affected containers.")

        # 2. Stop Containers
        for cid, _ in affected_containers:
            try:
                logger.info(f"Stopping container {cid}...")
                docker_manager.stop_container(cid)
            except Exception as e:
                logger.error(f"Failed to stop container {cid}: {e}")

        # 3. Move Data
        # Ensure parent of new_path exists
        os.makedirs(os.path.dirname(new_path), exist_ok=True)

        if os.path.exists(old_path):
            if os.path.exists(new_path):
                # If target exists and is empty, remove it to allow move
                if not os.listdir(new_path):
                    os.rmdir(new_path)
                    shutil.move(old_path, new_path)
                    logger.info(f"Moved data from {old_path} to {new_path}")
                else:
                    # Target exists and not empty. Merge? Or fail?
                    # For safety, we'll try to merge move or just log warning and rely on user knowing what they do.
                    # shutil.move into existing dir might put old_path INSIDE new_path (e.g. /new/old).
                    # We want contents of old_path to be in new_path.
                    logger.warning(f"Target {new_path} exists and is not empty. merging contents.")
                    for item in os.listdir(old_path):
                        s = os.path.join(old_path, item)
                        d = os.path.join(new_path, item)
                        if os.path.exists(d):
                            logger.warning(f"Skipping {item}, already exists in {new_path}")
                        else:
                            shutil.move(s, d)
                    # Try to remove old empty dir
                    try:
                        os.rmdir(old_path)
                    except:
                        pass
            else:
                shutil.move(old_path, new_path)
                logger.info(f"Moved data from {old_path} to {new_path}")
        else:
            # Old path didn't exist, just ensure new one does
            os.makedirs(new_path, exist_ok=True)
            logger.info(f"Old path did not exist. Created new path {new_path}")

        # 4. Update Database
        # Done in the API endpoint before task, OR here?
        # Doing it here ensures it matches the physical move.
        # But for API responsiveness, maybe update first?
        # Let's verify DB state.
        db_manager = get_db_manager()
        repo = LocationRepository(db_manager)
        # We assume the caller already updated the DB or passed the intention.
        # Actually, for consistency, let's update DB here if not done,
        # BUT the API endpoint logic below updates it first.
        # So we just proceed to step 5.

        # 5. Recreate Containers
        for cid, config in affected_containers:
            try:
                logger.info(f"Recreating container {config.get('name')}...")

                # If key is apps, we pass the new app_directory
                app_dir = new_path if key == 'apps' else None

                # If key is NOT apps, we might need to patch the mounts in the config
                # because `create_container` only auto-resolves `is_app_directory` mounts.
                # Explicit absolute bind mounts (like /hiveden/movies) need manual update in the config object.
                if key != 'apps':
                    mounts = config.get('mounts', [])
                    updated_mounts = []
                    for m in mounts:
                        source = m.get('source')
                        if not m.get('is_app_directory') and source and source.startswith(old_path):
                            # Replace prefix
                            new_source = source.replace(old_path, new_path, 1)
                            m['source'] = new_source
                        updated_mounts.append(m)
                    config['mounts'] = updated_mounts

                docker_manager.update_container(cid, config, app_directory=app_dir)
            except Exception as e:
                logger.error(f"Failed to recreate container {cid}: {e}")

        logger.info(f"Location update for '{key}' completed successfully.")

    except Exception as e:
        logger.error(f"Critical error during location update for {key}: {e}")
        # TODO: Notify user via notification system

@router.put("/locations/{key}", response_model=SuccessResponse)
def update_system_location(key: str, req: UpdateLocationRequest, background_tasks: BackgroundTasks):
    """
    Update a system location path (e.g., 'apps', 'movies').
    Triggers data migration and container recreation.
    """
    db_manager = get_db_manager()
    repo = LocationRepository(db_manager)

    location = repo.get_by_key(key)
    if location is None:
        raise HTTPException(status_code=404, detail="Location key not found")

    old_path = location.path
    new_path = req.new_path

    if old_path == new_path:
        return SuccessResponse(message="Path is unchanged")

    # Update DB immediately to reflect intent
    repo.update(location.id, path=new_path)

    LogService().info(
        actor="user",
        action="system.location.update",
        message=f"Updated system location {key} to {new_path}",
        module="system",
        metadata={"key": key, "old_path": old_path, "new_path": new_path, "migrating": req.should_migrate_data}
    )

    msg = f"Path updated to {new_path}."

    if req.should_migrate_data:
        # Trigger background task
        background_tasks.add_task(perform_location_update, key, new_path, old_path)
        msg += f" Data migration started from {old_path}."
    else:
        # If not migrating, ensure the directory exists so startup logic doesn't try to migrate defaults into it
        if not os.path.exists(new_path):
            try:
                os.makedirs(new_path, exist_ok=True)
                msg += " New directory created."
            except Exception as e:
                logger.error(f"Failed to create directory {new_path}: {e}")

    return SuccessResponse(message=msg)

@router.get("/locations/tree", response_model=LocationListResponse)
def get_comprehensive_locations():
    """
    Retrieve a comprehensive list of all system locations including:
    1. All Btrfs shares
    2. All system storage locations
    3. Expanded directories for the 'apps' location (2 levels deep)
    """
    locations = []

    # 1. Btrfs Shares
    try:
        from hiveden.shares.btrfs import BtrfsManager
        btrfs_shares = BtrfsManager().list_shares()
        for share in btrfs_shares:
            locations.append(FilesystemLocation(
                label=share.name,
                name=share.name,
                path=share.mount_path,
                type="share_btrfs"
            ))
    except Exception as e:
        logger.warning(f"Failed to fetch Btrfs shares: {e}")

    # 2. System Locations (DB)
    db_manager = get_db_manager()
    repo = LocationRepository(db_manager)
    sys_locs = repo.get_system_locations()

    # Add system locations, but mark 'apps' specifically to avoid duplication if we want
    # Actually prompt says "All storage locations", so we add them.
    locations.extend(sys_locs)

    # 3. Apps Expansion
    # Find 'apps' location
    apps_loc = next((l for l in sys_locs if l.key == 'apps'), None)

    if apps_loc and os.path.exists(apps_loc.path):
        try:
            # Scan Level 1 (e.g., apps/radarr)
            with os.scandir(apps_loc.path) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith('.'):
                        # Add Level 1 directory
                        l1_path = entry.path
                        locations.append(FilesystemLocation(
                            label=entry.name,
                            name=entry.name,
                            path=l1_path,
                            type="app_directory",
                            key=f"apps/{entry.name}" # Synthetic key for frontend reference
                        ))

                        # Scan Level 2 (e.g., apps/radarr/config)
                        try:
                            with os.scandir(l1_path) as it2:
                                for sub in it2:
                                    if sub.is_dir() and not sub.name.startswith('.'):
                                        locations.append(FilesystemLocation(
                                            label=f"{entry.name}/{sub.name}",
                                            name=f"{entry.name}/{sub.name}",
                                            path=sub.path,
                                            type="app_subdirectory",
                                            key=f"apps/{entry.name}/{sub.name}" # Synthetic key
                                        ))
                        except OSError as e:
                            logger.warning(f"Error scanning app subdirectory {l1_path}: {e}")
        except OSError as e:
            logger.warning(f"Error scanning apps directory {apps_loc.path}: {e}")

    return LocationListResponse(data=locations)
