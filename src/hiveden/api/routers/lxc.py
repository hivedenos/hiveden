from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
import traceback

from hiveden.api.dtos import DataResponse, LXCContainerCreate, SuccessResponse
from hiveden.lxc.models import LXCContainer

router = APIRouter(prefix="/lxc", tags=["LXC"])

@router.get("/containers", response_model=DataResponse)
def list_lxc_containers_endpoint():
    from hiveden.lxc.containers import list_containers
    try:
        containers = [
            LXCContainer(
                name=c.name,
                state=c.state,
                status=c.state,
                pid=c.init_pid,
                ips=c.get_ips(),
                ipv4=[ip for ip in c.get_ips() if "." in ip]
            )
            for c in list_containers()
        ]
        return DataResponse(data=containers)
    except Exception as e:
        logger.error(f"Error listing LXC containers: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/containers", response_model=DataResponse)
def create_lxc_container_endpoint(container: LXCContainerCreate):
    from hiveden.lxc.containers import create_container
    try:
        c = create_container(**container.dict())
        # create_container returns the lxc object, we map it to our model
        # Assuming created container might not have IPs immediately, but let's check attributes
        return DataResponse(data=LXCContainer(
            name=c.name,
            state=c.state,
            status=c.state,
            pid=c.init_pid,
            ips=c.get_ips(),
            ipv4=[ip for ip in c.get_ips() if "." in ip]
        ))
    except Exception as e:
        logger.error(f"Error creating LXC container: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/containers/{name}", response_model=DataResponse)
def get_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import get_container
    try:
        c = get_container(name)
        return DataResponse(data=LXCContainer(
            name=c.name,
            state=c.state,
            status=c.state,
            pid=c.init_pid,
            ips=c.get_ips(),
            ipv4=[ip for ip in c.get_ips() if "." in ip]
        ))
    except Exception as e:
        logger.error(f"Error getting LXC container {name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/containers/{name}/start", response_model=SuccessResponse)
def start_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import start_container
    try:
        start_container(name)
        return SuccessResponse(message=f"Container {name} started.")
    except Exception as e:
        logger.error(f"Error starting LXC container {name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/containers/{name}/stop", response_model=SuccessResponse)
def stop_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import stop_container
    try:
        stop_container(name)
        return SuccessResponse(message=f"Container {name} stopped.")
    except Exception as e:
        logger.error(f"Error stopping LXC container {name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/containers/{name}", response_model=SuccessResponse)
def delete_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import delete_container
    try:
        delete_container(name)
        return SuccessResponse(message=f"Container {name} deleted.")
    except Exception as e:
        logger.error(f"Error deleting LXC container {name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
