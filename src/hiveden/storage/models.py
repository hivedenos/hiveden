from typing import List, Optional, Literal
from pydantic import BaseModel

class Partition(BaseModel):
    name: str
    path: str
    size: int
    fstype: Optional[str] = None
    uuid: Optional[str] = None
    mountpoint: Optional[str] = None

class Disk(BaseModel):
    name: str
    path: str
    size: int
    model: Optional[str] = None
    serial: Optional[str] = None
    rotational: bool  # True if HDD, False if SSD
    partitions: List[Partition] = []
    is_system: bool = False  # True if contains root filesystem or boot
    available: bool = False  # True if empty/reusable

class StorageStrategy(BaseModel):
    name: str
    description: str
    raid_level: Literal["raid0", "raid1", "raid5", "raid6", "raid10", "single"]
    disks: List[str]  # List of disk paths
    usable_capacity: int
    redundancy: str  # Description of redundancy (e.g. "1 drive failure")

class Share(BaseModel):
    name: str
    path: str
    pool_name: str
    snapshots_enabled: bool = True
