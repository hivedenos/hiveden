from enum import Enum
from typing import List, Optional
from hiveden.pydantic_compat import BaseModel


class PackageOperation(str, Enum):
    INSTALL = "INSTALL"
    UNINSTALL = "UNINSTALL"


class OSType(str, Enum):
    ARCH = "arch"
    DEBIAN = "debian"
    UBUNTU = "ubuntu"
    FEDORA = "fedora"
    CENTOS = "centos"
    RHEL = "rhel"
    ALL = "all"


class RequiredPackage(BaseModel):
    name: str
    title: str
    description: str
    operation: PackageOperation = PackageOperation.INSTALL
    os_types: List[OSType] = [OSType.ALL]
    tags: List[str] = []


class PackageStatus(RequiredPackage):
    installed: bool
