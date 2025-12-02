"""API router for shell functionality."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from hiveden.api.dtos import DataResponse, SuccessResponse
from hiveden.shell.manager import ShellManager
from hiveden.shell.websocket import ShellWebSocketHandler
from hiveden.shell.models import (
    ShellSessionCreate,
    PackageCheckRequest,
    PackageInstallRequest,
)

router = APIRouter(prefix="/shell", tags=["Shell"])

# Global shell manager instance
shell_manager = ShellManager()
ws_handler = ShellWebSocketHandler(shell_manager)


@router.post("/sessions", response_model=DataResponse)
def create_shell_session(request: ShellSessionCreate):
    """Create a new shell session.
    
    Args:
        request: Shell session creation request
        
    Returns:
        Created session information
        
    Example for Docker:
        ```json
        {
            "shell_type": "docker",
            "target": "container_id_or_name",
            "user": "root",
            "working_dir": "/app"
        }
        ```
    
    Example for SSH:
        ```json
        {
            "shell_type": "ssh",
            "target": "192.168.1.100",
            "user": "root",
            "ssh_port": 22,
            "ssh_key_path": "/path/to/key"
        }
        ```
    
    Example for Local:
        ```json
        {
            "shell_type": "local",
            "target": "localhost",
            "working_dir": "/tmp"
        }
        ```
    """
    try:
        session = shell_manager.create_session(request)
        return DataResponse(data=session.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=DataResponse)
def list_shell_sessions(active_only: bool = Query(True, description="Only return active sessions")):
    """List all shell sessions.
    
    Args:
        active_only: If True, only return active sessions
        
    Returns:
        List of shell sessions
    """
    try:
        sessions = shell_manager.list_sessions(active_only=active_only)
        return DataResponse(data=[s.dict() for s in sessions])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=DataResponse)
def get_shell_session(session_id: str):
    """Get a specific shell session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Shell session information
    """
    try:
        session = shell_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return DataResponse(data=session.dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
def close_shell_session(session_id: str):
    """Close a shell session.
    
    Args:
        session_id: Session ID to close
        
    Returns:
        Success message
    """
    try:
        session = shell_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        shell_manager.close_session(session_id)
        return SuccessResponse(message=f"Session {session_id} closed successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{session_id}")
async def websocket_shell_session(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for interactive shell session.
    
    Connect to this endpoint to execute commands and receive real-time output.
    
    Message format (client -> server):
    ```json
    {
        "type": "command",
        "command": "ls -la"
    }
    ```
    
    Message format (server -> client):
    ```json
    {
        "type": "output",
        "data": {
            "session_id": "...",
            "output": "...",
            "error": false,
            "exit_code": null,
            "timestamp": "..."
        }
    }
    ```
    
    Args:
        websocket: WebSocket connection
        session_id: Session ID to connect to
    """
    await ws_handler.handle_session(websocket, session_id)


@router.post("/packages/check", response_model=DataResponse)
async def check_package(request: PackageCheckRequest):
    """Check if a package is installed on the local system.
    
    Args:
        request: Package check request
        
    Returns:
        Installation status and message
        
    Example:
        ```json
        {
            "package_name": "nginx",
            "package_manager": "auto"
        }
        ```
    """
    try:
        is_installed, message = await shell_manager.check_package_installed(
            request.package_name,
            request.package_manager
        )
        return DataResponse(data={
            "package_name": request.package_name,
            "installed": is_installed,
            "message": message
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/packages/install")
async def websocket_package_install(
    websocket: WebSocket,
    package_name: str = Query(..., description="Package name to install"),
    package_manager: str = Query("auto", description="Package manager to use")
):
    """WebSocket endpoint for package installation with real-time output.
    
    Connect to this endpoint to install a package and receive real-time installation progress.
    
    Message format (server -> client):
    ```json
    {
        "type": "output",
        "data": {
            "session_id": "system",
            "output": "Reading package lists...",
            "error": false,
            "exit_code": null,
            "timestamp": "..."
        }
    }
    ```
    
    Args:
        websocket: WebSocket connection
        package_name: Package to install
        package_manager: Package manager to use (auto, apt, yum, dnf, pacman)
    """
    await ws_handler.handle_package_install(websocket, package_name, package_manager)


# Convenience endpoint for Docker container shell
@router.post("/docker/{container_id}/shell", response_model=DataResponse)
def create_docker_shell(
    container_id: str,
    user: Optional[str] = "root",
    working_dir: Optional[str] = "/",
    shell_command: Optional[str] = "/bin/bash"
):
    """Create a shell session for a Docker container.
    
    This is a convenience endpoint that creates a Docker shell session.
    
    Args:
        container_id: Docker container ID or name
        user: User to execute commands as (default: root)
        working_dir: Working directory (default: /)
        shell_command: Shell command to use (default: /bin/bash)
        
    Returns:
        Created session information
    """
    try:
        request = ShellSessionCreate(
            shell_type="docker",
            target=container_id,
            user=user,
            working_dir=working_dir,
            docker_command=shell_command
        )
        session = shell_manager.create_session(request)
        return DataResponse(data=session.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Convenience endpoint for LXC container shell via SSH
@router.post("/lxc/{container_name}/shell", response_model=DataResponse)
def create_lxc_shell(
    container_name: str,
    user: Optional[str] = "root",
    working_dir: Optional[str] = "/",
    ssh_port: Optional[int] = 22,
    ssh_key_path: Optional[str] = None
):
    """Create a shell session for an LXC container via SSH.
    
    This is a convenience endpoint that creates an SSH shell session to an LXC container.
    
    Args:
        container_name: LXC container name (will be used as hostname)
        user: User to execute commands as (default: root)
        working_dir: Working directory (default: /)
        ssh_port: SSH port (default: 22)
        ssh_key_path: Path to SSH private key
        
    Returns:
        Created session information
    """
    try:
        request = ShellSessionCreate(
            shell_type="ssh",
            target=container_name,
            user=user,
            working_dir=working_dir,
            ssh_port=ssh_port,
            ssh_key_path=ssh_key_path
        )
        session = shell_manager.create_session(request)
        return DataResponse(data=session.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
