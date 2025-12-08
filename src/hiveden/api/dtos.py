from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from hiveden.docker.models import Container as DockerContainer, Network as DockerNetwork, DockerContainer as ContainerConfig
from hiveden.pkgs.models import PackageStatus
from hiveden.storage.models import Disk, DiskDetail, StorageStrategy
from hiveden.shares.models import (
    SMBShare,
    ZFSPool,
    ZFSDataset,
    BtrfsVolume,
    BtrfsSubvolume,
    BtrfsShare
)
from hiveden.lxc.models import LXCContainer
from hiveden.hwosinfo.models import OSInfo, HWInfo


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
        Dict[str, Any]
    ]] = None

