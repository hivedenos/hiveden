from typing import Dict, List
from pydantic import BaseModel

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
