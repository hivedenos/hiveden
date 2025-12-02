"""Pydantic models for shell sessions."""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ShellType(str, Enum):
    """Types of shell sessions supported."""
    DOCKER = "docker"
    SSH = "ssh"
    LOCAL = "local"


class ShellCommand(BaseModel):
    """Command to execute in a shell session."""
    command: str = Field(..., description="Command to execute")
    session_id: Optional[str] = Field(None, description="Session ID for the command")


class ShellOutput(BaseModel):
    """Output from a shell command."""
    session_id: str = Field(..., description="Session ID")
    output: str = Field(..., description="Command output")
    error: bool = Field(False, description="Whether this is an error output")
    exit_code: Optional[int] = Field(None, description="Exit code if command completed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of output")


class ShellSession(BaseModel):
    """Shell session information."""
    session_id: str = Field(..., description="Unique session identifier")
    shell_type: ShellType = Field(..., description="Type of shell session")
    target: str = Field(..., description="Target (container ID, hostname, etc.)")
    user: Optional[str] = Field("root", description="User to execute commands as")
    working_dir: Optional[str] = Field("/", description="Working directory")
    environment: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    active: bool = Field(True, description="Whether session is active")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True


class ShellSessionCreate(BaseModel):
    """Request to create a new shell session."""
    shell_type: ShellType = Field(..., description="Type of shell session")
    target: str = Field(..., description="Target (container ID, hostname, etc.)")
    user: Optional[str] = Field("root", description="User to execute commands as")
    working_dir: Optional[str] = Field("/", description="Working directory")
    environment: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")
    
    # Docker-specific options
    docker_command: Optional[str] = Field("/bin/bash", description="Shell command for Docker exec")
    
    # SSH-specific options
    ssh_port: Optional[int] = Field(22, description="SSH port")
    ssh_key_path: Optional[str] = Field(None, description="Path to SSH private key")
    ssh_password: Optional[str] = Field(None, description="SSH password (if not using key)")

    class Config:
        use_enum_values = True


class PackageCheckRequest(BaseModel):
    """Request to check if a package is installed."""
    package_name: str = Field(..., description="Name of the package to check")
    package_manager: Optional[str] = Field("auto", description="Package manager (apt, yum, dnf, pacman, or auto)")


class PackageInstallRequest(BaseModel):
    """Request to install a package."""
    package_name: str = Field(..., description="Name of the package to install")
    package_manager: Optional[str] = Field("auto", description="Package manager (apt, yum, dnf, pacman, or auto)")
    yes_to_prompts: bool = Field(True, description="Automatically answer yes to prompts")
