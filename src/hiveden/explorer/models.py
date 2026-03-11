from typing import List, Optional, Any, Union, Dict
from datetime import datetime
from pydantic import Field

from hiveden.pydantic_compat import BaseModel
from enum import Enum

# --- Enums ---


class FileType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class SortBy(str, Enum):
    NAME = "name"
    SIZE = "size"
    MODIFIED = "modified"
    TYPE = "type"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OperationType(str, Enum):
    COPY = "copy"
    MOVE = "move"
    SEARCH = "search"
    DELETE = "delete"


class OperationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# --- DB Models (Representations) ---


class ExplorerConfig(BaseModel):
    id: Optional[int] = None
    key: str
    value: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FilesystemLocation(BaseModel):
    id: Optional[int] = None
    key: Optional[str] = None
    label: str
    name: str  # Compatibility alias for label
    path: str
    type: str = "user_bookmark"
    description: Optional[str] = None
    is_editable: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Augmented field
    exists: Optional[bool] = None


class ExplorerOperation(BaseModel):
    id: str  # UUID
    operation_type: str
    status: str
    progress: int = 0
    total_items: Optional[int] = None
    processed_items: int = 0
    source_paths: Optional[str] = None  # JSON string in DB
    destination_path: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[str] = None  # JSON string in DB
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# --- API DTOs ---


class FileEntry(BaseModel):
    name: str
    path: str
    type: FileType
    size: int
    size_human: str
    permissions: str
    owner: str
    group: str
    modified: Optional[datetime] = None
    accessed: Optional[datetime] = None
    created: Optional[datetime] = None
    is_hidden: bool
    is_symlink: bool
    symlink_target: Optional[str] = None
    mime_type: Optional[str] = None
    # Detailed properties
    permissions_octal: Optional[str] = None
    owner_id: Optional[int] = None
    group_id: Optional[int] = None
    inode: Optional[int] = None
    hard_links: Optional[int] = None
    is_readable: Optional[bool] = None
    is_writable: Optional[bool] = None
    is_executable: Optional[bool] = None


class DirectoryListingResponse(BaseModel):
    success: bool = True
    current_path: str
    parent_path: Optional[str] = None
    entries: List[FileEntry]
    total_entries: int
    total_size: int
    total_size_human: str


class FilePropertyResponse(BaseModel):
    success: bool = True
    entry: FileEntry


class CreateDirectoryRequest(BaseModel):
    path: str
    parents: bool = False


class DeleteRequest(BaseModel):
    paths: List[str]
    recursive: bool = False


class RenameRequest(BaseModel):
    source: str
    destination: str
    overwrite: bool = False


class ClipboardCopyRequest(BaseModel):
    paths: List[str]
    session_id: str


class ClipboardPasteRequest(BaseModel):
    destination: str
    session_id: str
    conflict_resolution: str = "rename"
    rename_pattern: str = "{name} ({n})"


class ClipboardStatusResponse(BaseModel):
    success: bool = True
    has_items: bool
    operation: Optional[str] = None
    items_count: int
    paths: List[str]
    total_size: int
    total_size_human: str


class LocationCreateRequest(BaseModel):
    label: str = Field(..., alias="name")
    path: str
    type: str = "user_bookmark"
    description: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class LocationUpdateRequest(BaseModel):
    label: Optional[str] = Field(None, alias="name")
    path: Optional[str] = None
    description: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class SearchRequest(BaseModel):
    path: str
    pattern: str
    use_regex: bool = False
    case_sensitive: bool = False
    type_filter: str = "all"
    show_hidden: bool = False


class USBDevice(BaseModel):
    device: str
    mount_point: Optional[str] = None
    label: Optional[str] = None
    filesystem: Optional[str] = None
    total_size: int
    total_size_human: str
    used_size: int
    used_size_human: str
    free_size: int
    free_size_human: str
    usage_percent: float
    is_removable: bool
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    show_hidden_files: Optional[bool] = None
    usb_mount_path: Optional[str] = None
    root_directory: Optional[str] = None


class GenericResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


class DeleteResponse(GenericResponse):
    deleted: List[str] = []
    failed: List[Dict[str, str]] = []


class OperationResponse(BaseModel):
    success: bool = True
    operation: ExplorerOperation
