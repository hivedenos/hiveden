import traceback
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.logger import logger
from typing import Optional

from hiveden.api.dtos import DataResponse, SuccessResponse
from hiveden.docker.models import DBContainerCreate as ContainerCreate, NetworkCreate
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


@router.get("/containers", response_model=DataResponse)
def list_all_containers():
    from hiveden.docker.containers import list_containers
    try:
        return DataResponse(data=list_containers(all=True))
    except Exception as e:
        logger.error(f"Error listing all containers: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers", response_model=DataResponse)
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
            "command": container.command,
            "env": json.dumps([e.dict() for e in container.env]) if container.env else None,
            "ports": json.dumps([p.dict() for p in container.ports]) if container.ports else None,
            "mounts": json.dumps([m.dict() for m in container.mounts]) if container.mounts else None,
            "labels": json.dumps(container.labels) if container.labels else None
        }
        
        for key, value in attributes.items():
            if value:
                attr_repo.create({
                    "container_id": new_container_record.id,
                    "name": key,
                    "value": value
                })

        # 2. Create and Start in Docker (if it's meant to be a running container)
        docker_response = None
        if container.is_container:
            # Convert DB model back to Docker args format
            # We use the original request object 'container' as it has the right structure
            c = create_container(
                name=container.name,
                image=container.image,
                command=container.command,
                env=container.env,
                ports=container.ports,
                mounts=container.mounts,
                labels=container.labels
            )
            docker_response = c.attrs

        return DataResponse(data={
            "db_record": new_container_record.dict(),
            "docker_attrs": docker_response
        })
    except Exception as e:
        # TODO: Rollback DB transaction if Docker creation fails?
        # For now, we raise 500
        logger.error(f"Error creating new container: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}", response_model=DataResponse)
def get_one_container(container_id: str):
    from hiveden.docker.containers import get_container
    try:
        return DataResponse(data=get_container(container_id))
    except Exception as e:
        logger.error(f"Error getting container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/start", response_model=DataResponse)
def start_one_container(container_id: str):
    from hiveden.docker.containers import start_container
    try:
        return DataResponse(data=start_container(container_id).dict())
    except Exception as e:
        logger.error(f"Error starting container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/stop", response_model=DataResponse)
def stop_one_container(container_id: str):
    from hiveden.docker.containers import stop_container
    try:
        return DataResponse(data=stop_container(container_id))
    except Exception as e:
        logger.error(f"Error stopping container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/containers/{container_id}", response_model=SuccessResponse)
def remove_one_container(container_id: str):
    from hiveden.docker.containers import remove_container
    try:
        remove_container(container_id)
        return SuccessResponse(message=f"Container {container_id} removed.")
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


@router.get("/networks", response_model=DataResponse)
def list_all_networks():
    from hiveden.docker.networks import list_networks
    try:
        networks = [n.attrs for n in list_networks()]
        return DataResponse(data=networks)
    except Exception as e:
        logger.error(f"Error listing all networks: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/networks", response_model=DataResponse)
def create_new_network(network: NetworkCreate):
    from hiveden.docker.networks import create_network
    try:
        n = create_network(**network.dict())
        return DataResponse(data=n.attrs)
    except Exception as e:
        logger.error(f"Error creating new network: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/networks/{network_id}", response_model=DataResponse)
def get_one_network(network_id: str):
    from hiveden.docker.networks import get_network
    try:
        return DataResponse(data=get_network(network_id).attrs)
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
