import yaml
from fastapi import Body, FastAPI, HTTPException

from hiveden.api.dtos import (
    ConfigResponse,
    Container,
    ContainerCreate,
    DataResponse,
    LXCContainer,
    LXCContainerCreate,
    Network,
    NetworkCreate,
    SuccessResponse,
)
from hiveden.docker.actions import apply_configuration

app = FastAPI(
    title="Hiveden API",
    description="An API for managing your personal server.",
    version="0.1.0",
)


@app.post("/config", response_model=DataResponse, tags=["Config"])
def submit_config(config: str = Body(...)):
    """Submit a YAML configuration."""
    try:
        data = yaml.safe_load(config)
        messages = apply_configuration(data['docker'])
        return DataResponse(data=messages)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docker/containers", response_model=DataResponse, tags=["Docker"])
def list_all_containers():
    from hiveden.docker.containers import list_containers
    try:
        containers = [c.attrs for c in list_containers(all=True)]
        return DataResponse(data=containers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docker/containers", response_model=DataResponse, tags=["Docker"])
def create_new_container(container: ContainerCreate):
    from hiveden.docker.containers import create_container
    try:
        c = create_container(**container.dict())
        return DataResponse(data=c.attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docker/containers/{container_id}", response_model=DataResponse, tags=["Docker"])
def get_one_container(container_id: str):
    from hiveden.docker.containers import get_container
    try:
        return DataResponse(data=get_container(container_id).attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docker/containers/{container_id}/stop", response_model=DataResponse, tags=["Docker"])
def stop_one_container(container_id: str):
    from hiveden.docker.containers import stop_container
    try:
        return DataResponse(data=stop_container(container_id).attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/docker/containers/{container_id}", response_model=SuccessResponse, tags=["Docker"])
def remove_one_container(container_id: str):
    from hiveden.docker.containers import remove_container
    try:
        remove_container(container_id)
        return SuccessResponse(message=f"Container {container_id} removed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docker/networks", response_model=DataResponse, tags=["Docker"])
def list_all_networks():
    from hiveden.docker.networks import list_networks
    try:
        networks = [n.attrs for n in list_networks()]
        return DataResponse(data=networks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/docker/networks", response_model=DataResponse, tags=["Docker"])
def create_new_network(network: NetworkCreate):
    from hiveden.docker.networks import create_network
    try:
        n = create_network(**network.dict())
        return DataResponse(data=n.attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docker/networks/{network_id}", response_model=DataResponse, tags=["Docker"])
def get_one_network(network_id: str):
    from hiveden.docker.networks import get_network
    try:
        return DataResponse(data=get_network(network_id).attrs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info/os", response_model=DataResponse, tags=["Info"])
def get_os_info_endpoint():
    from hiveden.hwosinfo.os import get_os_info
    try:
        return DataResponse(data=get_os_info())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/hw", response_model=DataResponse, tags=["Info"])
def get_hw_info_endpoint():
    from hiveden.hwosinfo.hw import get_hw_info
    try:
        return DataResponse(data=get_hw_info())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/lxc/containers", response_model=DataResponse, tags=["LXC"])
def list_lxc_containers_endpoint():
    from hiveden.lxc.containers import list_containers
    try:
        containers = [{"name": c.name, "state": c.state, "pid": c.init_pid, "ips": c.get_ips()} for c in list_containers()]
        return DataResponse(data=containers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lxc/containers", response_model=DataResponse, tags=["LXC"])
def create_lxc_container_endpoint(container: LXCContainerCreate):
    from hiveden.lxc.containers import create_container
    try:
        c = create_container(**container.dict())
        return DataResponse(data={"name": c.name, "state": c.state})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/lxc/containers/{name}", response_model=DataResponse, tags=["LXC"])
def get_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import get_container
    try:
        c = get_container(name)
        return DataResponse(data={"name": c.name, "state": c.state, "pid": c.init_pid, "ips": c.get_ips()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lxc/containers/{name}/start", response_model=SuccessResponse, tags=["LXC"])
def start_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import start_container
    try:
        start_container(name)
        return SuccessResponse(message=f"Container {name} started.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/lxc/containers/{name}/stop", response_model=SuccessResponse, tags=["LXC"])
def stop_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import stop_container
    try:
        stop_container(name)
        return SuccessResponse(message=f"Container {name} stopped.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/lxc/containers/{name}", response_model=SuccessResponse, tags=["LXC"])
def delete_lxc_container_endpoint(name: str):
    from hiveden.lxc.containers import delete_container
    try:
        delete_container(name)
        return SuccessResponse(message=f"Container {name} deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/docker/networks/{network_id}", response_model=SuccessResponse)
def remove_one_network(network_id: str):
    from hiveden.docker.networks import remove_network
    try:
        remove_network(network_id)
        return SuccessResponse(message=f"Network {network_id} removed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
