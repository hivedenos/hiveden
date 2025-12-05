from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class JobLog(BaseModel):
    timestamp: datetime
    output: str
    error: bool = False

class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    command: str
    logs: List[JobLog] = []
    created_at: datetime = datetime.now()
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
