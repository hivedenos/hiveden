import os
import shutil
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from hiveden.db.session import get_db_manager
from hiveden.db.repositories.locations import LocationRepository
from hiveden.db.repositories.core import ConfigRepository, ModuleRepository
from hiveden.docker.containers import DockerManager
from hiveden.config.settings import config
from hiveden.api.dtos import (
    SuccessResponse, 
    LocationListResponse, 
    DomainInfoResponse, 
    DomainUpdateRequest, 
    DomainUpdateResponse, 
    IngressContainerInfo
)
from hiveden.explorer.models import FilesystemLocation
from hiveden.docker.models import IngressConfig

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)

class UpdateLocationRequest(BaseModel):
    new_path: str

def get_system_domain_value() -> str:
    """Get the effective system domain (DB > Env)."""
    db_manager = get_db_manager()
    module_repo = ModuleRepository(db_manager)
    config_repo = ConfigRepository(db_manager)
    
    # Try DB
    try:
        core_module = module_repo.get_by_short_name('core')
        if core_module:
            cfg = config_repo.get_by_module_and_key(core_module.id, 'domain')
            if cfg:
                return cfg['value']
    except Exception as e:
        logger.warning(f"Failed to fetch domain from DB: {e}")
        
    # Fallback
    return config.domain

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
            return IngressConfig(domain=f"{entrypoint}{domain_part}", port=port)
        except Exception as e:
            logger.error(f"Failed to parse ingress from labels: {e}")
            pass
            
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

@router.put("/domain", response_model=DomainUpdateResponse)
def update_system_domain(req: DomainUpdateRequest):
    """Update system domain and recreate accessible containers."""
    new_domain = req.domain
    existing_domain = get_system_domain_value()
    
    # 1. Update DB
    db_manager = get_db_manager()
    config_repo = ConfigRepository(db_manager)
    config_repo.set_value('core', 'domain', new_domain)
    
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
    if not location:
        raise HTTPException(status_code=404, detail="Location key not found")
        
    old_path = location.path
    new_path = req.new_path
    
    if old_path == new_path:
        return SuccessResponse(message="Path is unchanged")

    # Update DB immediately to reflect intent
    repo.update(location.id, path=new_path)
    
    # Trigger background task
    background_tasks.add_task(perform_location_update, key, new_path, old_path)
    
    return SuccessResponse(message=f"Update started. Moving data from {old_path} to {new_path}")
