from typing import Optional
from hiveden.pydantic_compat import BaseModel


class SystemdServiceStatus(BaseModel):
    name: str
    description: Optional[str] = None
    load_state: str  # e.g., 'loaded'
    active_state: str  # e.g., 'active', 'inactive'
    sub_state: str  # e.g., 'running', 'dead'
    unit_file_state: str  # e.g., 'enabled', 'disabled'
    main_pid: Optional[int] = None
    since: Optional[str] = None


class ServiceActionRequest(BaseModel):
    action: str  # start, stop, restart, enable, disable
