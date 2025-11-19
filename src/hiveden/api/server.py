from typing import List

import yaml
from fastapi import Body, FastAPI

from hiveden.api.dtos import (
    ConfigResponse,
    Container,
    ContainerCreate,
    Network,
    NetworkCreate,
)
from hiveden.docker.actions import apply_configuration

app = FastAPI()


@app.post("/config", response_model=ConfigResponse)
def submit_config(config: str = Body(...)):
    """Submit a YAML configuration."""
    try:
        data = yaml.safe_load(config)
        messages = apply_configuration(data['docker'])
        return {"messages": messages}
    except yaml.YAMLError as e:
        return {"error": f"Invalid YAML: {e}"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/docker/containers", response_model=List[Container])
def list_all_containers():
    from hiveden.docker.containers import list_containers
    return [c.attrs for c in list_containers(all=True)]


@app.post("/docker/containers", response_model=Container)
def create_new_container(container: ContainerCreate):
    from hiveden.docker.containers import create_container
    c = create_container(**container.dict())
    return c.attrs


@app.get("/docker/containers/{container_id}", response_model=Container)
def get_one_container(container_id: str):
    from hiveden.docker.containers import get_container
    return get_container(container_id).attrs


@app.post("/docker/containers/{container_id}/stop", response_model=Container)
def stop_one_container(container_id: str):
    from hiveden.docker.containers import stop_container
    return stop_container(container_id).attrs


@app.delete("/docker/containers/{container_id}")
def remove_one_container(container_id: str):
    from hiveden.docker.containers import remove_container
    remove_container(container_id)
    return {"message": f"Container {container_id} removed."}


@app.get("/docker/networks", response_model=List[Network])
def list_all_networks():
    from hiveden.docker.networks import list_networks
    return [n.attrs for n in list_networks()]


@app.post("/docker/networks", response_model=Network)
def create_new_network(network: NetworkCreate):
    from hiveden.docker.networks import create_network
    n = create_network(**network.dict())
    return n.attrs


@app.get("/docker/networks/{network_id}", response_model=Network)
def get_one_network(network_id: str):
    from hiveden.docker.networks import get_network
    return get_network(network_id).attrs


@app.delete("/docker/networks/{network_id}")
def remove_one_network(network_id: str):
    from hiveden.docker.networks import remove_network
    remove_network(network_id)
    return {"message": f"Network {network_id} removed."}


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/hello/{name}")
def read_name(name: str):
    return {"message": f"Hello {name}"}
