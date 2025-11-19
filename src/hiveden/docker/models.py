from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class EnvVar(BaseModel):
    name: str
    value: str

class Port(BaseModel):
    host_port: int
    container_port: int
    protocol: str = "tcp"

class DockerContainer(BaseModel):
    name: str
    image: str
    command: Optional[str] = None
    env: Optional[List[EnvVar]] = None
    ports: Optional[List[Port]] = None

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
    Created: datetime
    State: str
    Status: str
    Ports: dict
    Labels: dict
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
