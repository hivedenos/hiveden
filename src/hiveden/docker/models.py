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


class Mount(BaseModel):
    source: str
    target: str
    type: str = "bind"
    is_app_directory: bool = False


class IngressConfig(BaseModel):
    domain: str
    port: int


class DockerContainer(BaseModel):
    name: str
    image: str
    command: Optional[List[str]] = None
    env: Optional[List[EnvVar]] = None
    ports: Optional[List[Port]] = None
    mounts: Optional[List[Mount]] = None
    labels: Optional[Dict[str, str]] = None
    ingress_config: Optional[IngressConfig] = None

class ContainerCreate(DockerContainer):
    is_container: bool = True
    enabled: bool = True
    type: str = "docker"

class TemplateCreate(DockerContainer):
    is_container: bool = False
    enabled: bool = True
    type: str = "template"

class NetworkCreate(BaseModel):
    name: str

class HostConfig(BaseModel):
    NetworkMode: str

class NetworkSettings(BaseModel):
    Ports: Dict
    Networks: Dict

class Container(BaseModel):
    Id: str
    Name: str
    Image: str
    ImageID: str
    Command: List[str]
    Created: datetime
    State: str
    Status: str
    Ports: dict
    Labels: dict
    NetworkSettings: NetworkSettings
    HostConfig: HostConfig
    IPAddress: Optional[str] = None

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
