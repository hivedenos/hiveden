from fastapi import APIRouter, HTTPException

from hiveden.api.dtos import DataResponse, SuccessResponse
from hiveden.docker.models import DockerContainer as ContainerCreate, NetworkCreate

router = APIRouter(prefix="/docker", tags=["Docker"])


@router.get("/containers", response_model=DataResponse)
def list_all_containers():
    from hiveden.docker.containers import list_containers
    try:
        return DataResponse(data=list_containers(all=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers", response_model=DataResponse)
def create_new_container(container: ContainerCreate):
    from hiveden.docker.containers import create_container
    try:
        c = create_container(**container.dict())
        return DataResponse(data=c.attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/containers/{container_id}", response_model=DataResponse)
def get_one_container(container_id: str):
    from hiveden.docker.containers import get_container
    try:
        return DataResponse(data=get_container(container_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/containers/{container_id}/stop", response_model=DataResponse)
def stop_one_container(container_id: str):
    from hiveden.docker.containers import stop_container
    try:
        return DataResponse(data=stop_container(container_id).attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/containers/{container_id}", response_model=SuccessResponse)
def remove_one_container(container_id: str):
    from hiveden.docker.containers import remove_container
    try:
        remove_container(container_id)
        return SuccessResponse(message=f"Container {container_id} removed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/networks", response_model=DataResponse)
def list_all_networks():
    from hiveden.docker.networks import list_networks
    try:
        networks = [n.attrs for n in list_networks()]
        return DataResponse(data=networks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/networks", response_model=DataResponse)
def create_new_network(network: NetworkCreate):
    from hiveden.docker.networks import create_network
    try:
        n = create_network(**network.dict())
        return DataResponse(data=n.attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/networks/{network_id}", response_model=DataResponse)
def get_one_network(network_id: str):
    from hiveden.docker.networks import get_network
    try:
        return DataResponse(data=get_network(network_id).attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/networks/{network_id}", response_model=SuccessResponse)
def remove_one_network(network_id: str):
    from hiveden.docker.networks import remove_network
    try:
        remove_network(network_id)
        return SuccessResponse(message=f"Network {network_id} removed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
