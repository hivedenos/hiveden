from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class Module(BaseModel):
    id: Optional[int] = None
    name: str
    short_name: str
    enabled: bool
    created_at: Optional[datetime] = None
