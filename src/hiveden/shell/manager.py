"""Shell manager for handling different types of shell sessions."""

import asyncio
import uuid
import subprocess
import shlex
from typing import Dict, Optional, AsyncIterator
import docker
from docker import errors as docker_errors
import paramiko
from datetime import datetime

from hiveden.shell.models import (
    ShellSession,
    ShellSessionCreate,
    ShellType,
    ShellOutput,
)
from hiveden.pkgs.manager import get_package_manager
from hiveden.pkgs.base import PackageManager



class ShellManager:
    """Manages shell sessions for Docker, SSH, and local execution."""

    def __init__(self):
        self.sessions: Dict[str, ShellSession] = {}
        self.docker_client = docker.from_env()
        self._ssh_clients: Dict[str, paramiko.SSHClient] = {}

    def create_session(self, request: ShellSessionCreate) -> ShellSession:
        """Create a new shell session.
        
        Args:
            request: Session creation request
            
        Returns:
            Created shell session
            
        Raises:
            ValueError: If target is invalid or connection fails
        """
        session_id = str(uuid.uuid4())
        
        # Validate target based on shell type
        if request.shell_type == ShellType.DOCKER:
            self._validate_docker_target(request.target)
        elif request.shell_type == ShellType.SSH:
            self._validate_ssh_target(request.target, request.ssh_port, 
                                     request.ssh_key_path, request.ssh_password)
        
        session = ShellSession(
            session_id=session_id,
            shell_type=request.shell_type,
            target=request.target,
            user=request.user,
            working_dir=request.working_dir,
            environment=request.environment or {},
            metadata={
                "docker_command": request.docker_command,
                "ssh_port": request.ssh_port,
                "ssh_key_path": request.ssh_key_path,
            }
        )
        
        self.sessions[session_id] = session
        return session

    def _validate_docker_target(self, container_id: str):
        """Validate that Docker container exists and is running."""
        try:
            container = self.docker_client.containers.get(container_id)
            if container.status != "running":
                raise ValueError(f"Container {container_id} is not running (status: {container.status})")
        except docker_errors.NotFound:
            raise ValueError(f"Container {container_id} not found")
        except docker_errors.APIError as e:
            raise ValueError(f"Docker API error: {str(e)}")

    def _validate_ssh_target(self, hostname: str, port: int, key_path: Optional[str], password: Optional[str]):
        """Validate SSH connection parameters."""
        if not key_path and not password:
            raise ValueError("Either ssh_key_path or ssh_password must be provided")
        
        # Test SSH connection
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if key_path:
                ssh.connect(hostname, port=port, username="root", key_filename=key_path, timeout=5)
            else:
                ssh.connect(hostname, port=port, username="root", password=password, timeout=5)
            
            ssh.close()
        except Exception as e:
            raise ValueError(f"SSH connection failed: {str(e)}")

    async def execute_command_stream(
        self, 
        session_id: str, 
        command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute a command and stream output in real-time.
        
        Args:
            session_id: Session ID to execute command in
            command: Command to execute
            
        Yields:
            ShellOutput objects with command output
            
        Raises:
            ValueError: If session not found or inactive
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        if not session.active:
            raise ValueError(f"Session {session_id} is not active")

        if session.shell_type == ShellType.DOCKER:
            async for output in self._execute_docker_command(session, command):
                yield output
        elif session.shell_type == ShellType.SSH:
            async for output in self._execute_ssh_command(session, command):
                yield output
        elif session.shell_type == ShellType.LOCAL:
            async for output in self._execute_local_command(session, command):
                yield output

    async def _execute_docker_command(
        self, 
        session: ShellSession, 
        command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command in Docker container with streaming output."""
        try:
            container = self.docker_client.containers.get(session.target)
            
            # Prepare environment variables
            env_vars = session.environment.copy()
            
            # Execute command with streaming
            exec_result = container.exec_run(
                command,
                user=session.user,
                workdir=session.working_dir,
                environment=env_vars,
                stream=True,
                demux=True,  # Separate stdout and stderr
            )
            
            # Stream output
            for stdout, stderr in exec_result.output:
                if stdout:
                    yield ShellOutput(
                        session_id=session.session_id,
                        output=stdout.decode('utf-8', errors='replace'),
                        error=False,
                    )
                if stderr:
                    yield ShellOutput(
                        session_id=session.session_id,
                        output=stderr.decode('utf-8', errors='replace'),
                        error=True,
                    )
            
            # Get exit code
            exit_code = exec_result.exit_code
            yield ShellOutput(
                session_id=session.session_id,
                output="",
                error=False,
                exit_code=exit_code,
            )
            
        except docker_errors.NotFound:
            yield ShellOutput(
                session_id=session.session_id,
                output=f"Container {session.target} not found",
                error=True,
                exit_code=1,
            )
        except Exception as e:
            yield ShellOutput(
                session_id=session.session_id,
                output=f"Error executing command: {str(e)}",
                error=True,
                exit_code=1,
            )

    async def _execute_ssh_command(
        self, 
        session: ShellSession, 
        command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command via SSH with streaming output."""
        ssh = None
        try:
            # Get or create SSH client for this session
            if session.session_id not in self._ssh_clients:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                ssh_port = session.metadata.get("ssh_port", 22)
                ssh_key_path = session.metadata.get("ssh_key_path")
                
                if ssh_key_path:
                    ssh.connect(
                        session.target, 
                        port=ssh_port, 
                        username=session.user, 
                        key_filename=ssh_key_path
                    )
                else:
                    # Note: Password should be stored securely, not in metadata
                    raise ValueError("SSH password authentication not implemented for security reasons")
                
                self._ssh_clients[session.session_id] = ssh
            else:
                ssh = self._ssh_clients[session.session_id]
            
            # Prepare command with environment and working directory
            env_str = " ".join([f"{k}={shlex.quote(v)}" for k, v in session.environment.items()])
            full_command = f"cd {shlex.quote(session.working_dir)} && {env_str} {command}"
            
            # Execute command
            stdin, stdout, stderr = ssh.exec_command(full_command)
            
            # Stream stdout
            for line in stdout:
                yield ShellOutput(
                    session_id=session.session_id,
                    output=line,
                    error=False,
                )
            
            # Stream stderr
            for line in stderr:
                yield ShellOutput(
                    session_id=session.session_id,
                    output=line,
                    error=True,
                )
            
            # Get exit code
            exit_code = stdout.channel.recv_exit_status()
            yield ShellOutput(
                session_id=session.session_id,
                output="",
                error=False,
                exit_code=exit_code,
            )
            
        except Exception as e:
            yield ShellOutput(
                session_id=session.session_id,
                output=f"SSH error: {str(e)}",
                error=True,
                exit_code=1,
            )

    async def _execute_local_command(
        self, 
        session: ShellSession, 
        command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command locally with streaming output."""
        try:
            # Prepare environment
            env = session.environment.copy()
            
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=session.working_dir,
                env=env,
            )
            
            # Stream output
            async def read_stream(stream, is_error=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    yield ShellOutput(
                        session_id=session.session_id,
                        output=line.decode('utf-8', errors='replace'),
                        error=is_error,
                    )
            
            # Read stdout and stderr concurrently
            async for output in read_stream(process.stdout, False):
                yield output
            
            async for output in read_stream(process.stderr, True):
                yield output
            
            # Wait for process to complete
            exit_code = await process.wait()
            yield ShellOutput(
                session_id=session.session_id,
                output="",
                error=False,
                exit_code=exit_code,
            )
            
        except Exception as e:
            yield ShellOutput(
                session_id=session.session_id,
                output=f"Local execution error: {str(e)}",
                error=True,
                exit_code=1,
            )

    def close_session(self, session_id: str):
        """Close a shell session and cleanup resources.
        
        Args:
            session_id: Session ID to close
        """
        session = self.sessions.get(session_id)
        if session:
            session.active = False
            
            # Cleanup SSH connection if exists
            if session_id in self._ssh_clients:
                try:
                    self._ssh_clients[session_id].close()
                except:
                    pass
                del self._ssh_clients[session_id]

    def get_session(self, session_id: str) -> Optional[ShellSession]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Shell session or None if not found
        """
        return self.sessions.get(session_id)

    def list_sessions(self, active_only: bool = True) -> list[ShellSession]:
        """List all shell sessions.
        
        Args:
            active_only: If True, only return active sessions
            
        Returns:
            List of shell sessions
        """
        sessions = list(self.sessions.values())
        if active_only:
            sessions = [s for s in sessions if s.active]
        return sessions

    async def check_package_installed(self, package_name: str, package_manager: str = "auto") -> tuple[bool, str]:
        """Check if a package is installed on the local system.
        
        Args:
            package_name: Name of the package
            package_manager: Package manager to use (auto, or ignored as we detect automatically)
            
        Returns:
            Tuple of (is_installed, message)
        """
        try:
            if package_manager == "auto":
                pm = self._detect_package_manager()
            else:
                # Fallback/Legacy support: if a specific string is passed, we try to match it to a command manually
                # or we could ignore it and just use detected. 
                # For safety/correctness per prompt "use the hiveden.pkgs package", we prefer detection.
                # But to be safe let's just use detection if we can't map it.
                pm = self._detect_package_manager()

            if not isinstance(pm, PackageManager):
                 return False, f"Failed to get package manager instance"

            command = pm.get_check_installed_command(package_name)
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
            )
            is_installed = result.returncode == 0
            message = f"Package {package_name} is {'installed' if is_installed else 'not installed'}"
            return is_installed, message
        except Exception as e:
            return False, f"Error checking package: {str(e)}"

    async def install_package_stream(
        self, 
        package_name: str, 
        package_manager: str = "auto",
        yes_to_prompts: bool = True
    ) -> AsyncIterator[ShellOutput]:
        """Install a package and stream the output.
        
        Args:
            package_name: Name of the package to install
            package_manager: Package manager to use
            yes_to_prompts: Automatically answer yes to prompts
            
        Yields:
            ShellOutput objects with installation progress
        """
        try:
            if package_manager == "auto":
                pm = self._detect_package_manager()
            else:
                pm = self._detect_package_manager()
            
            if not isinstance(pm, PackageManager):
                yield ShellOutput(
                    session_id="system",
                    output="Failed to detect package manager",
                    error=True,
                    exit_code=1,
                )
                return

            command = pm.get_install_command(package_name)
            
            # Create a temporary local session for package installation
            session = ShellSession(
                session_id="pkg-install-" + str(uuid.uuid4()),
                shell_type=ShellType.LOCAL,
                target="localhost",
                user="root",
                working_dir="/",
            )
            
            async for output in self._execute_local_command(session, command):
                yield output
        except Exception as e:
            yield ShellOutput(
                session_id="system",
                output=f"Error preparing installation: {str(e)}",
                error=True,
                exit_code=1,
            )

    def _detect_package_manager(self) -> PackageManager:
        """Detect the system's package manager.
        
        Returns:
            PackageManager instance
        """
        return get_package_manager()
