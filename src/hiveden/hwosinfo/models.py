from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from hiveden.storage.models import Disk

class OSInfo(BaseModel):
    system: str
    release: str
    version: str
    machine: str
    processor: str
    hostname: str

class NetworkAddress(BaseModel):
    address: str
    netmask: Optional[str] = None
    broadcast: Optional[str] = None
    ptp: Optional[str] = None
    family: str

class NetworkInterface(BaseModel):
    addresses: List[NetworkAddress]

class NetworkIOCounters(BaseModel):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

class NetworkInfo(BaseModel):
    interfaces: Dict[str, NetworkInterface]
    io_counters: NetworkIOCounters
    primary_ip: str

class HWInfo(BaseModel):
    cpu: Dict
    memory: Dict
    disk: Dict
    network: NetworkInfo

class GenericDevice(BaseModel):
    id: str
    name: str # product name usually
    vendor: Optional[str] = None
    product: Optional[str] = None
    description: Optional[str] = None
    driver: Optional[str] = None
    bus_info: Optional[str] = None
    
    # Detailed fields
    logical_name: Optional[str] = None
    version: Optional[str] = None
    serial: Optional[str] = None
    capacity: Optional[int] = None
    clock: Optional[int] = None
    capabilities: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    
    # Raw children or extra info if needed, but keeping it flat is better for UI
    
class SystemDevices(BaseModel):
    summary: Dict[str, Any]
    storage: List[Disk]
    video: List[GenericDevice]
    usb: List[GenericDevice]
    network: List[GenericDevice]
    multimedia: List[GenericDevice]
    other: List[GenericDevice]