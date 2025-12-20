from typing import Dict, List, Optional
from pydantic import BaseModel

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
