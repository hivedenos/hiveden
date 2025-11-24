from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ContainerTemplate(BaseModel):
    id: int
    name: str
    type: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

class ContainerTemplateAttribute(BaseModel):
    id: int
    container_template_id: int
    name: str
    value: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
