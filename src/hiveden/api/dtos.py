from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    messages: List[str]


class BaseResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None


class DataResponse(BaseResponse):
    data: Optional[Any] = None


class SuccessResponse(BaseResponse):
    pass


class ErrorResponse(BaseResponse):
    status: str = "error"


class OSInfo(BaseModel):
    system: str
    release: str
    version: str
    machine: str
    processor: str
    hostname: str


class HWInfo(BaseModel):
    cpu: Dict
    memory: Dict
    disk: Dict
    network: Dict


class LXCContainer(BaseModel):
    name: str
    state: str
    pid: int
    ips: List[str]


class LXCContainerCreate(BaseModel):
    name: str
    template: str = "ubuntu"


class ZFSPool(BaseModel):
    name: str


class ZFSPoolCreate(BaseModel):
    name: str
    devices: List[str]


class ZFSDataset(BaseModel):
    name: str


class ZFSDatasetCreate(BaseModel):
    name: str


class SMBShare(BaseModel):
    name: str
    path: str
    comment: Optional[str] = None
    read_only: bool = False
    browsable: bool = True
    guest_ok: bool = False


class SMBShareCreate(BaseModel):
    name: str
    path: str
    comment: Optional[str] = ""
    read_only: bool = False
    browsable: bool = True
    guest_ok: bool = False
