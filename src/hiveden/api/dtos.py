from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from hiveden.docker.models import Container as DockerContainer
from hiveden.docker.models import ContainerCreate
from hiveden.docker.models import DockerContainer as ContainerConfig
from hiveden.docker.models import Network as DockerNetwork
from hiveden.explorer.models import FilesystemLocation
from hiveden.hwosinfo.models import HWInfo, OSInfo, SystemDevices
from hiveden.lxc.models import LXCContainer
from hiveden.pkgs.models import PackageStatus
from hiveden.shares.models import (
    BtrfsShare,
    BtrfsSubvolume,
    BtrfsVolume,
    SMBShare,
    ZFSDataset,
    ZFSPool,
)
from hiveden.storage.models import Disk, DiskDetail, StorageStrategy
from hiveden.systemd.models import SystemdServiceStatus


class ConfigResponse(BaseModel):
    messages: List[str]


class BaseResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None


class SuccessResponse(BaseResponse):
    pass


class ErrorResponse(BaseResponse):
    status: str = "error"


class LXCContainerCreate(BaseModel):
    name: str
    template: str = "ubuntu"


class ZFSPoolCreate(BaseModel):
    name: str
    devices: List[str]


class ZFSDatasetCreate(BaseModel):
    name: str


class SMBShareCreate(BaseModel):
    name: str
    path: str
    comment: Optional[str] = ""
    read_only: bool = False
    browsable: bool = True
    guest_ok: bool = False


class CreateBtrfsShareRequest(BaseModel):
    parent_path: str
    name: str
    mount_path: str


class VersionInfo(BaseModel):
    version: str


class JobInfo(BaseModel):
    job_id: str
    message: Optional[str] = None


class ContainerListResponse(BaseResponse):
    data: List[DockerContainer]


class ContainerResponse(BaseResponse):
    data: DockerContainer


class ContainerCreateResponse(BaseResponse):
    data: DockerContainer


class ContainerConfigResponse(BaseResponse):
    data: ContainerCreate


class TemplateResponse(BaseResponse):
    data: ContainerConfig


class NetworkListResponse(BaseResponse):
    data: List[DockerNetwork]


class NetworkResponse(BaseResponse):
    data: DockerNetwork


class DiskListResponse(BaseResponse):
    data: List[Disk]


class DiskDetailResponse(BaseResponse):
    data: DiskDetail


class StorageStrategyListResponse(BaseResponse):
    data: List[StorageStrategy]


class StorageStrategyApplyResponse(BaseResponse):
    data: JobInfo


class BtrfsShareListResponse(BaseResponse):
    data: List[BtrfsShare]

class BtrfsVolumeListResponse(BaseResponse):
    data: List[BtrfsVolume]

class LocationListResponse(BaseResponse):
    data: List[FilesystemLocation]


class IngressContainerInfo(BaseModel):
    name: str
    id: str
    url: str

class DomainInfoResponse(BaseResponse):
    domain: str
    containers: List[IngressContainerInfo]

class DomainUpdateRequest(BaseModel):
    domain: str

class DomainUpdateResponse(BaseModel):
    updated_containers: List[str]

class UpdateLocationRequest(BaseModel):
    new_path: str
    should_migrate_data: bool = False

class FileUploadResponse(BaseResponse):
    relative_path: str
    absolute_path: str

class DNSConfigResponse(BaseResponse):
    enabled: bool
    domain: Optional[str] = None
    container_id: Optional[str] = None
    api_key: Optional[str] = None

class DNSUpdateRequest(BaseModel):
    api_key: str

class SystemdServiceResponse(BaseResponse):
    data: Optional[SystemdServiceStatus] = None

class SystemdServiceListResponse(BaseResponse):
    data: List[SystemdServiceStatus]

class DatabaseInfo(BaseModel):
    name: str
    owner: str
    encoding: str
    size_bytes: int

class DatabaseUser(BaseModel):
    name: str
    is_superuser: bool
    can_create_role: bool
    can_create_db: bool

class DatabaseCreateRequest(BaseModel):
    name: str
    owner: Optional[str] = None

class DatabaseListResponse(BaseResponse):
    data: List[DatabaseInfo]

class DatabaseUserListResponse(BaseResponse):
    data: List[DatabaseUser]

class ImageContainerInfo(BaseModel):
    id: str
    name: str

class DockerImage(BaseModel):
    id: str
    tags: List[str]
    created: str
    size: int
    labels: Optional[Dict[str, str]] = None
    containers: Optional[List[ImageContainerInfo]] = None

class ImageListResponse(BaseResponse):
    data: List[DockerImage]

class ImageLayer(BaseModel):
    id: str
    created: int
    created_by: str
    size: int
    comment: str
    tags: Optional[List[str]] = None

class ImageLayerListResponse(BaseResponse):
    data: List[ImageLayer]

class DataResponse(BaseResponse):
    data: Optional[Union[
        DockerContainer,
        DockerNetwork,
        DiskDetail,
        Disk,
        StorageStrategy,
        PackageStatus,
        OSInfo,
        HWInfo,
        SystemDevices,
        LXCContainer,
        ZFSPool,
        ZFSDataset,
        SMBShare,
        BtrfsVolume,
        BtrfsSubvolume,
        BtrfsShare,
        VersionInfo,
        JobInfo,
        List[DockerContainer],
        List[DockerNetwork],
        List[Disk],
        List[StorageStrategy],
        List[PackageStatus],
        List[LXCContainer],
        List[ZFSPool],
        List[ZFSDataset],
        List[SMBShare],
        List[BtrfsVolume],
        List[BtrfsSubvolume],
        List[BtrfsShare],
        List[str],
        List[Dict[str, Any]],
        Dict[str, Any],
        DomainInfoResponse,
        DomainUpdateResponse,
        DNSConfigResponse
    ]] = None
