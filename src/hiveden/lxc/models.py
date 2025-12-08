from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel

@dataclass
class Resources:
    cpu: Optional[float]
    ram: Optional[int]
    hdd: Optional[float]
    os: Optional[str]
    version: Optional[str]

@dataclass
class InstallMethod:
    type: str
    script: str
    resources: Resources

@dataclass
class DefaultCredentials:
    username: Optional[str]
    password: Optional[str]

@dataclass
class Note:
    text: str
    type: str

@dataclass
class Script:
    name: str
    slug: str
    categories: List[int]
    date_created: str
    type: str
    updateable: bool
    privileged: bool
    interface_port: Optional[int]
    documentation: Optional[str]
    website: Optional[str]
    logo: Optional[str]
    config_path: str
    description: str
    install_methods: List[InstallMethod]
    default_credentials: DefaultCredentials
    notes: List[Note]

    @property
    def default_install_script(self) -> Optional[str]:
        for method in self.install_methods:
            if method.type == "default":
                return method.script
        return None

@dataclass
class Category:
    name: str
    id: int
    sort_order: int
    description: str
    icon: str
    scripts: List[Script]

class LXCContainer(BaseModel):
    name: str
    state: str
    status: str
    pid: int
    ips: List[str]
    ipv4: List[str]