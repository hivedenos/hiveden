import json
import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.logger import logger
from fastapi.responses import StreamingResponse

from hiveden.api.dtos import (
    ContainerConfigResponse,
    ContainerCreateResponse,
    ContainerListResponse,
    ContainerResponse,
    ErrorResponse,
    FileUploadResponse,
    NetworkListResponse,
    NetworkResponse,
    SuccessResponse,
)
from hiveden.db.session import get_db_manager
from hiveden.docker.models import ContainerCreate, NetworkCreate


def get_db():
    return get_db_manager()

router = APIRouter(tags=["Docker"])

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

    try:
        # 1. Create and Start in Docker FIRST (to get ID and verify valid config)
        c = create_container(
            name=container.name,
            image=container.image,
            command=container.command,
            env=container.env,
            ports=container.ports,
            mounts=container.mounts,
            devices=container.devices,
            labels=container.labels,
            ingress_config=container.ingress_config,
            privileged=container.privileged or False
        )

        # We need to return the Pydantic model, not the raw docker attributes
        from hiveden.docker.containers import get_container
        docker_response = get_container(c.id)

        return ContainerCreateResponse(data=docker_response)
    except Exception as e:
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
    from hiveden.docker.containers import get_container, update_container

    try:
        # 1. Update Docker
        c = update_container(container_id, container)

        # Return new container info
        docker_response = get_container(c.id)
        return ContainerCreateResponse(data=docker_response)

    except Exception as e:
        logger.error(f"Error updating container {container_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/containers/{container_id}", response_model=SuccessResponse, responses={400: {"model": ErrorResponse, "description": "Bad Request: Container is running or other client-side error."}})
def remove_one_container(
    container_id: str,
    delete_database: bool = Query(False, description="Delete the associated database if it exists."),
    delete_volumes: bool = Query(False, description="Delete the container's application directory."),
    delete_dns: bool = Query(False, description="Delete associated DNS entry from Pi-hole.")
):
    from hiveden.docker.containers import remove_container
    try:
        remove_container(container_id, delete_database=delete_database, delete_volumes=delete_volumes, delete_dns=delete_dns)
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

@router.post("/containers/{container_name}/files", response_model=FileUploadResponse)
async def upload_container_file(
    container_name: str,
    path: str = Query(..., description="Relative path within the container's app directory (e.g., 'config/prometheus.yml')"),
    file: UploadFile = File(...)
):
    """
    Upload a file to the container's application directory.

    The file will be saved to: {apps_directory}/{container_name}/{path}

    Returns the relative path to be used in the mount source.
    """
    import os
    import shutil

    from hiveden.docker.containers import DockerManager

    manager = DockerManager()

    try:
        # 1. Ensure container directory exists
        container_dir = manager.ensure_app_directory(container_name)

        # 2. Prevent directory traversal
        # Clean the path
        clean_path = os.path.normpath(path)
        if clean_path.startswith("..") or os.path.isabs(clean_path):
             raise HTTPException(status_code=400, detail="Invalid path: Must be relative and inside container directory.")

        # 3. Construct full target path
        target_path = os.path.join(container_dir, clean_path)

        # 4. Ensure parent directories exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # 5. Write file
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return FileUploadResponse(
            message=f"File uploaded successfully to {clean_path}",
            relative_path=clean_path,
            absolute_path=target_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file for container {container_name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
