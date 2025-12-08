from typing import List, Optional
from pydantic import BaseModel

class SMBShare(BaseModel):
    name: str
    path: str
    comment: Optional[str] = None
    read_only: bool = False
    browsable: bool = True
    guest_ok: bool = False

class ZFSPool(BaseModel):
    name: str

class ZFSDataset(BaseModel):
    name: str

class BtrfsVolume(BaseModel):
    device: str
    mountpoint: str
    label: Optional[str] = None

class BtrfsSubvolume(BaseModel):
    id: int
    parent_id: int
    path: str
    name: str

class BtrfsShare(BaseModel):
    name: str
    parent_path: str
    mount_path: str
    device: str
    subvolid: str
