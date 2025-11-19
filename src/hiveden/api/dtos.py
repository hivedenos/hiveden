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
