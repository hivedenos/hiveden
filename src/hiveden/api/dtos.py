from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ContainerCreate(BaseModel):
    image: str
    name: str
    command: Optional[str] = None
    detach: bool = True
    network_name: Optional[str] = "hiveden-net"


class NetworkCreate(BaseModel):
    name: str


class HostConfig(BaseModel):
    NetworkMode: str


class NetworkSettings(BaseModel):
    Ports: Dict
    Networks: Dict


class Container(BaseModel):
    Id: str
    Names: List[str]
    Image: str
    ImageID: str
    Command: str
    Created: int
    State: str
    Status: str
    Ports: List[Dict]
    Labels: Dict
    NetworkSettings: NetworkSettings
    HostConfig: HostConfig


class Network(BaseModel):
    Name: str
    Id: str
    Created: str
    Scope: str
    Driver: str
    EnableIPv6: bool
    IPAM: Dict
    Internal: bool
    Attachable: bool
    Ingress: bool
    ConfigFrom: Dict
    ConfigOnly: bool
    Containers: Dict
    Options: Optional[Dict] = None
    Labels: Optional[Dict] = None


class ConfigResponse(BaseModel):
    messages: List[str]
