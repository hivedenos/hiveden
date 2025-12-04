from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class Container(BaseModel):
    id: int
    name: str
    type: str
    is_container: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

class ContainerAttribute(BaseModel):
    id: int
    container_id: int
    name: str
    value: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
