import traceback
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.logger import logger
from typing import Optional

from hiveden.api.dtos import (
    DataResponse, 
    SuccessResponse,
    ErrorResponse,
    ContainerListResponse, 
    ContainerResponse, 
    ContainerCreateResponse, 
    ContainerConfigResponse,
    NetworkListResponse, 
    NetworkResponse,
    TemplateResponse
)
from hiveden.docker.models import ContainerCreate, NetworkCreate, TemplateCreate
from hiveden.db.manager import DatabaseManager
from hiveden.db.repositories.templates import ContainerRepository, ContainerAttributeRepository
import os
import json

# Helper to get DB manager (in a real app, use dependency injection properly)
def get_db_manager():
    # Assuming DB URL is in environment or config
    # For now, defaulting to local sqlite for dev
    db_path = os.path.join(os.getcwd(), "hiveden.db")
    return DatabaseManager(f"sqlite:///{db_path}")

router = APIRouter(prefix="/docker", tags=["Docker"])


@router.post("/containers/template", response_model=TemplateResponse)
def create_template(template: TemplateCreate):
    
    db_manager = get_db_manager()
    container_repo = ContainerRepository(db_manager)
    attr_repo = ContainerAttributeRepository(db_manager)
    
    try:
        # 1. Store in Database
        # Create main container record
        new_container_record = container_repo.create({
            "name": template.name,
            "type": template.type,
            "is_container": False,
            "enabled": template.enabled
        })
        
        if not new_container_record:
            raise Exception("Failed to create container record in database")
            
        # Store attributes (image, command, ports, etc.)
        attributes = {
            "image": template.image,
            "command": json.dumps(template.command) if template.command else None,
            "env": json.dumps([e.dict() for e in template.env]) if template.env else None,
            "ports": json.dumps([p.dict() for p in template.ports]) if template.ports else None,
            "mounts": json.dumps([m.dict() for m in template.mounts]) if template.mounts else None,
            "labels": json.dumps(template.labels) if template.labels else None,
            "ingress_config": json.dumps(template.ingress_config.dict()) if template.ingress_config else None
        }
        
        for key, value in attributes.items():
            if value:
                attr_repo.create({
                    "container_id": new_container_record.id,
                    "name": key,
                    "value": value
                })

        return TemplateResponse(data=template)
    except Exception as e:
        logger.error(f"Error creating template: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers", response_model=ContainerListResponse)
def list_all_containers():
    from hiveden.docker.containers import list_containers
    try:
        return ContainerListResponse(data=list_containers(all=True))
    except Exception as e:
        logger.error(f"Error listing all containers: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers", response_model=ContainerCreateResponse)
def create_new_container(container: ContainerCreate):
    from hiveden.docker.containers import create_container
    
    db_manager = get_db_manager()
    container_repo = ContainerRepository(db_manager)
    attr_repo = ContainerAttributeRepository(db_manager)
    
    try:
        # 1. Store in Database
        # Create main container record
        new_container_record = container_repo.create({
            "name": container.name,
            "type": container.type,
            "is_container": container.is_container,
            "enabled": container.enabled
        })
        
        if not new_container_record:
            raise Exception("Failed to create container record in database")
            
        # Store attributes (image, command, ports, etc.)
        # We serialize complex objects to JSON strings for storage
        attributes = {
            "image": container.image,
            "command": json.dumps(container.command) if container.command else None,
            "env": json.dumps([e.dict() for e in container.env]) if container.env else None,
            "ports": json.dumps([p.dict() for p in container.ports]) if container.ports else None,
            "mounts": json.dumps([m.dict() for m in container.mounts]) if container.mounts else None,
            "labels": json.dumps(container.labels) if container.labels else None,
            "ingress_config": json.dumps(container.ingress_config.dict()) if container.ingress_config else None
        }
        
        for key, value in attributes.items():
            if value:
                attr_repo.create({
                    "container_id": new_container_record.id,
                    "name": key,
                    "value": value
                })

        # 2. Create and Start in Docker (always, as /template handles DB-only)
        # Convert DB model back to Docker args format
        # We use the original request object 'container' as it has the right structure
        c = create_container(
            name=container.name,
            image=container.image,
            command=container.command,
            env=container.env,
            ports=container.ports,
            mounts=container.mounts,
            labels=container.labels,
            ingress_config=container.ingress_config
        )
        
        # We need to return the Pydantic model, not the raw docker attributes
        from hiveden.docker.containers import get_container
        docker_response = get_container(c.id)
        
        return ContainerCreateResponse(data=docker_response)
    except Exception as e:
        # TODO: Rollback DB transaction if Docker creation fails?
        # For now, we raise 500
        logger.error(f"Error creating new container: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}", response_model=ContainerResponse)
def get_one_container(container_id: str):
    from hiveden.docker.containers import get_container
    try:
        return ContainerResponse(data=get_container(container_id))
    except Exception as e:
        logger.error(f"Error getting container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/start", response_model=ContainerResponse)
def start_one_container(container_id: str):
    from hiveden.docker.containers import start_container
    try:
        return ContainerResponse(data=start_container(container_id).dict())
    except Exception as e:
        logger.error(f"Error starting container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/stop", response_model=ContainerResponse)
def stop_one_container(container_id: str):
    from hiveden.docker.containers import stop_container
    try:
        return ContainerResponse(data=stop_container(container_id))
    except Exception as e:
        logger.error(f"Error stopping container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/restart", response_model=ContainerResponse)
def restart_one_container(container_id: str):
    from hiveden.docker.containers import restart_container
    try:
        return ContainerResponse(data=restart_container(container_id))
    except Exception as e:
        logger.error(f"Error restarting container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}/config", response_model=ContainerConfigResponse)
def get_container_configuration(container_id: str):
    from hiveden.docker.containers import get_container_config
    try:
        config = get_container_config(container_id)
        return ContainerConfigResponse(data=config)
    except Exception as e:
        logger.error(f"Error getting container config {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/containers/{container_id}", response_model=ContainerCreateResponse)
def update_container_configuration(container_id: str, container: ContainerCreate):
    from hiveden.docker.containers import update_container, get_container
    
    db_manager = get_db_manager()
    container_repo = ContainerRepository(db_manager)
    attr_repo = ContainerAttributeRepository(db_manager)
    
    try:
        # Update DB Record
        # 1. Find existing record by old name (Need to get old name first)
        # We need the old container info to find the DB record if we rely on name.
        # But wait, get_container_config(container_id) gives us the current name.
        # Alternatively, if we tracked container_id in DB, it would be easier.
        # Assuming we can find by name.
        
        # Get old config to know the name
        from hiveden.docker.containers import get_container_config
        try:
            old_config = get_container_config(container_id)
            old_name = old_config["name"]
        except Exception:
            logger.warning(f"Could not retrieve config for container {container_id}, assuming it is gone.")
            old_name = container.name
        
        # Find DB record
        record = container_repo.find_by_name(old_name)
        if record:
            # Update record
            container_repo.update(record.id, **{
                "name": container.name,
                "type": container.type,
                "is_container": container.is_container,
                "enabled": container.enabled
            })
            
            # Update attributes (delete old, insert new)
            attr_repo.delete_by_container_id(record.id)
            
            attributes = {
                "image": container.image,
                "command": json.dumps(container.command) if container.command else None,
                "env": json.dumps([e.dict() for e in container.env]) if container.env else None,
                "ports": json.dumps([p.dict() for p in container.ports]) if container.ports else None,
                "mounts": json.dumps([m.dict() for m in container.mounts]) if container.mounts else None,
                "labels": json.dumps(container.labels) if container.labels else None,
                "ingress_config": json.dumps(container.ingress_config.dict()) if container.ingress_config else None
            }
            
            for key, value in attributes.items():
                if value:
                    attr_repo.create({
                        "container_id": record.id,
                        "name": key,
                        "value": value
                    })
        
        # Update Docker
        c = update_container(container_id, container)
        
        # Return new container info
        docker_response = get_container(c.id)
        return ContainerCreateResponse(data=docker_response)
        
    except Exception as e:
        logger.error(f"Error updating container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/containers/{container_id}", response_model=SuccessResponse, responses={400: {"model": ErrorResponse, "description": "Bad Request: Container is running or other client-side error."}})
def remove_one_container(container_id: str):
    from hiveden.docker.containers import remove_container
    try:
        remove_container(container_id)
        return SuccessResponse(message=f"Container {container_id} removed.")
    except ValueError as e:
        logger.warning(f"Attempt to remove running container {container_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/containers/{container_id}/logs")
def stream_container_logs(
    container_id: str,
    follow: Optional[bool] = True,
    tail: Optional[int] = 100
):
    """Stream container logs in real-time using Server-Sent Events.    
    Args:
        container_id: Container ID or name
        follow: If True, stream logs in real-time (default: True)
        tail: Number of lines to show from the end (default: 100)    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    from hiveden.docker.containers import DockerManager
    
    def event_generator():
        try:
            manager = DockerManager()
            for log_line in manager.stream_logs(container_id, follow=follow, tail=tail):
                # Format as Server-Sent Event
                yield f"data: {log_line}\n\n"
        except Exception as e:
            logger.error(f"Error streaming container {container_id} logs: {e}\n{traceback.format_exc()}")
            yield f"data: Error: {str(e)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/networks", response_model=NetworkListResponse)
def list_all_networks():
    from hiveden.docker.networks import list_networks
    try:
        networks = [n.attrs for n in list_networks()]
        return NetworkListResponse(data=networks)
    except Exception as e:
        logger.error(f"Error listing all networks: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/networks", response_model=NetworkResponse)
def create_new_network(network: NetworkCreate):
    from hiveden.docker.networks import create_network
    try:
        n = create_network(**network.dict())
        return NetworkResponse(data=n.attrs)
    except Exception as e:
        logger.error(f"Error creating new network: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/networks/{network_id}", response_model=NetworkResponse)
def get_one_network(network_id: str):
    from hiveden.docker.networks import get_network
    try:
        return NetworkResponse(data=get_network(network_id).attrs)
    except Exception as e:
        logger.error(f"Error getting network {network_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/networks/{network_id}", response_model=SuccessResponse)
def remove_one_network(network_id: str):
    from hiveden.docker.networks import remove_network
    try:
        remove_network(network_id)
        return SuccessResponse(message=f"Network {network_id} removed.")
    except Exception as e:
        logger.error(f"Error removing network {network_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))