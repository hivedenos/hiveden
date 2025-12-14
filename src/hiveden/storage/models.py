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
    raid_group: Optional[str] = None  # Name of the RAID array (e.g., md0)
    raid_level: Optional[str] = None  # RAID level (e.g., raid1)

class SmartData(BaseModel):
    healthy: bool
    health_status: str
    temperature: Optional[int] = None
    power_on_hours: Optional[int] = None
    power_cycles: Optional[int] = None
    model_name: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    rotation_rate: Optional[int] = None
    attributes: List[dict] = []  # Raw attributes list

class DiskDetail(Disk):
    vendor: Optional[str] = None
    bus: Optional[str] = None  # ATA, USB, NVMe, etc.
    smart: Optional[SmartData] = None

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

class MountRequest(BaseModel):
    device: str
    automatic: bool
    mount_name: Optional[str] = None
