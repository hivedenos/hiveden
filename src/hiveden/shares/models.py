from typing import Optional
from pydantic import BaseModel

class SMBShare(BaseModel):
    name: str
    path: str
    comment: Optional[str] = None
    read_only: bool = False
    browsable: bool = True
    guest_ok: bool = False
