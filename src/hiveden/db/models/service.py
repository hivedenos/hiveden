from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import Field

from hiveden.pydantic_compat import BaseModel


class ServiceTemplate(BaseModel):
    id: Optional[int] = None
    name: str
    slug: str
    type: str
    description: Optional[str] = None
    logo: Optional[str] = None
    default_config: Dict[str, Any] = Field(default_factory=dict)
    maintainer: str = "hiveden"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ManagedService(BaseModel):
    id: Optional[int] = None
    identifier: str
    name: str
    type: str
    template_id: Optional[int] = None
    category: str = "general"
    icon: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    is_managed: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
