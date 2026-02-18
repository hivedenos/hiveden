"""Shell manager for handling different types of shell sessions."""

import asyncio
import uuid
import subprocess
import shlex
import os
import pty
import errno
import struct
import termios
import fcntl
from dataclasses import dataclass
from typing import Dict, Optional, AsyncIterator, Any
import docker
from docker import errors as docker_errors
import paramiko

from hiveden.shell.models import (
    ShellSession,
    ShellSessionCreate,
    ShellType,
    ShellOutput,
)
from hiveden.pkgs.manager import get_package_manager
from hiveden.pkgs.base import PackageManager


@dataclass
class InteractiveSessionRuntime:
    """Runtime resources for interactive shell sessions."""

    session_id: str
    shell_type: ShellType
    active: bool = True

    pty_master_fd: Optional[int] = None
    pty_slave_fd: Optional[int] = None
    local_process: Optional[subprocess.Popen] = None

    ssh_client: Optional[paramiko.SSHClient] = None
    ssh_channel: Optional[paramiko.Channel] = None

    docker_exec_id: Optional[str] = None
    docker_stream: Optional[Any] = None
    docker_socket: Optional[Any] = None


class ShellManager:
    """Manages shell sessions for Docker, SSH, and local execution."""

    def __init__(self):
        self.sessions: Dict[str, ShellSession] = {}
        self.docker_client = docker.from_env()
        self._ssh_clients: Dict[str, paramiko.SSHClient] = {}
        self._interactive_sessions: Dict[str, InteractiveSessionRuntime] = {}

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
            ssh_port = request.ssh_port or 22
            self._validate_ssh_target(
                request.target,
                ssh_port,
                request.ssh_key_path,
                request.ssh_password,
            )

        session = ShellSession(
            session_id=session_id,
            shell_type=request.shell_type,
            target=request.target,
            user=request.user,
            working_dir=request.working_dir,
            environment=request.environment or {},
            metadata={
                "docker_command": request.docker_command,
                "ssh_port": request.ssh_port or 22,
                "ssh_key_path": request.ssh_key_path,
                "ssh_password": request.ssh_password,
            },
        )

        self.sessions[session_id] = session
        return session

    def _validate_docker_target(self, container_id: str):
        """Validate that Docker container exists and is running."""
        try:
            container = self.docker_client.containers.get(container_id)
            if container.status != "running":
                raise ValueError(
                    f"Container {container_id} is not running (status: {container.status})"
                )
        except docker_errors.NotFound:
            raise ValueError(f"Container {container_id} not found")
        except docker_errors.APIError as e:
            raise ValueError(f"Docker API error: {str(e)}")

    def _validate_ssh_target(
        self, hostname: str, port: int, key_path: Optional[str], password: Optional[str]
    ):
        """Validate SSH connection parameters."""
        if not key_path and not password:
            raise ValueError("Either ssh_key_path or ssh_password must be provided")

        # Test SSH connection
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if key_path:
                ssh.connect(
                    hostname,
                    port=port,
                    username="root",
                    key_filename=key_path,
                    timeout=5,
                )
            else:
                ssh.connect(
                    hostname, port=port, username="root", password=password, timeout=5
                )

            ssh.close()
        except Exception as e:
            raise ValueError(f"SSH connection failed: {str(e)}")

    async def execute_command_stream(
        self, session_id: str, command: str
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

    async def start_interactive_session(
        self,
        session_id: str,
        cols: int = 120,
        rows: int = 30,
    ):
        """Start interactive PTY/channel for a shell session."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.active:
            raise ValueError(f"Session {session_id} is not active")

        existing = self._interactive_sessions.get(session_id)
        if existing and existing.active:
            return

        if session.shell_type == ShellType.LOCAL:
            runtime = self._start_local_interactive(session, cols, rows)
        elif session.shell_type == ShellType.SSH:
            runtime = self._start_ssh_interactive(session, cols, rows)
        elif session.shell_type == ShellType.DOCKER:
            runtime = self._start_docker_interactive(session, cols, rows)
        else:
            raise ValueError(f"Unsupported shell type: {session.shell_type}")

        self._interactive_sessions[session_id] = runtime

    async def stream_interactive_output(
        self,
        session_id: str,
    ) -> AsyncIterator[ShellOutput]:
        """Stream interactive shell output as chunks."""
        session = self.sessions.get(session_id)
        runtime = self._interactive_sessions.get(session_id)

        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not runtime or not runtime.active:
            raise ValueError(f"Interactive session {session_id} not started")

        try:
            if runtime.shell_type == ShellType.LOCAL:
                async for chunk in self._stream_local_interactive(runtime):
                    if chunk:
                        yield ShellOutput(
                            session_id=session_id,
                            output=chunk.decode("utf-8", errors="replace"),
                            error=False,
                        )
            elif runtime.shell_type == ShellType.SSH:
                async for chunk in self._stream_ssh_interactive(runtime):
                    if chunk:
                        yield ShellOutput(
                            session_id=session_id,
                            output=chunk.decode("utf-8", errors="replace"),
                            error=False,
                        )
            elif runtime.shell_type == ShellType.DOCKER:
                async for chunk in self._stream_docker_interactive(runtime):
                    if chunk:
                        yield ShellOutput(
                            session_id=session_id,
                            output=chunk.decode("utf-8", errors="replace"),
                            error=False,
                        )
        finally:
            runtime.active = False

    async def send_interactive_input(self, session_id: str, data: str):
        """Send raw terminal input to an interactive session."""
        runtime = self._interactive_sessions.get(session_id)
        if not runtime or not runtime.active:
            raise ValueError(f"Interactive session {session_id} not started")

        payload = data.encode("utf-8", errors="replace")
        if not payload:
            return

        if runtime.shell_type == ShellType.LOCAL:
            if runtime.pty_master_fd is None:
                raise ValueError("Local interactive PTY is unavailable")
            os.write(runtime.pty_master_fd, payload)
            return

        if runtime.shell_type == ShellType.SSH:
            if not runtime.ssh_channel:
                raise ValueError("SSH interactive channel is unavailable")
            await asyncio.to_thread(runtime.ssh_channel.send, payload)
            return

        if runtime.shell_type == ShellType.DOCKER:
            if not runtime.docker_socket:
                raise ValueError("Docker interactive socket is unavailable")
            await asyncio.to_thread(runtime.docker_socket.sendall, payload)
            return

        raise ValueError(f"Unsupported shell type: {runtime.shell_type}")

    async def resize_interactive_session(self, session_id: str, cols: int, rows: int):
        """Resize an interactive terminal session."""
        runtime = self._interactive_sessions.get(session_id)
        if not runtime or not runtime.active:
            raise ValueError(f"Interactive session {session_id} not started")

        safe_cols = max(1, int(cols))
        safe_rows = max(1, int(rows))

        if runtime.shell_type == ShellType.LOCAL:
            if runtime.pty_master_fd is not None:
                self._set_winsize(runtime.pty_master_fd, safe_rows, safe_cols)
            return

        if runtime.shell_type == ShellType.SSH:
            if runtime.ssh_channel:
                runtime.ssh_channel.resize_pty(width=safe_cols, height=safe_rows)
            return

        if runtime.shell_type == ShellType.DOCKER:
            if runtime.docker_exec_id:
                await asyncio.to_thread(
                    self.docker_client.api.exec_resize,
                    runtime.docker_exec_id,
                    height=safe_rows,
                    width=safe_cols,
                )
            return

        raise ValueError(f"Unsupported shell type: {runtime.shell_type}")

    async def stop_interactive_session(self, session_id: str):
        """Stop interactive runtime and release all resources."""
        runtime = self._interactive_sessions.get(session_id)
        if not runtime:
            return
        self._cleanup_interactive_runtime(runtime)
        self._interactive_sessions.pop(session_id, None)

    def _set_winsize(self, fd: int, rows: int, cols: int):
        """Apply terminal dimensions to a PTY file descriptor."""
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    def _extract_raw_socket(self, stream_socket: Any) -> Any:
        """Extract raw socket from docker stream wrappers."""
        if hasattr(stream_socket, "_sock"):
            return stream_socket._sock
        return stream_socket

    def _start_local_interactive(
        self,
        session: ShellSession,
        cols: int,
        rows: int,
    ) -> InteractiveSessionRuntime:
        """Start a local interactive /bin/bash process under PTY."""
        master_fd, slave_fd = pty.openpty()
        self._set_winsize(slave_fd, rows, cols)

        env = os.environ.copy()
        env.update(session.environment or {})

        shell_bin = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
        shell_cmd = [shell_bin, "-i"]

        process = subprocess.Popen(
            shell_cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=session.working_dir or "/",
            env=env,
            start_new_session=True,
        )

        os.close(slave_fd)
        os.set_blocking(master_fd, False)

        return InteractiveSessionRuntime(
            session_id=session.session_id,
            shell_type=session.shell_type,
            pty_master_fd=master_fd,
            local_process=process,
        )

    def _start_ssh_interactive(
        self,
        session: ShellSession,
        cols: int,
        rows: int,
    ) -> InteractiveSessionRuntime:
        """Start an interactive SSH channel with PTY enabled."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        metadata = session.metadata or {}
        ssh_port = metadata.get("ssh_port", 22)
        ssh_key_path = metadata.get("ssh_key_path")
        ssh_password = metadata.get("ssh_password")
        ssh_user = session.user or "root"

        if ssh_key_path:
            ssh.connect(
                session.target,
                port=ssh_port,
                username=ssh_user,
                key_filename=ssh_key_path,
                timeout=5,
            )
        elif ssh_password:
            ssh.connect(
                session.target,
                port=ssh_port,
                username=ssh_user,
                password=ssh_password,
                timeout=5,
            )
        else:
            raise ValueError("SSH credentials not available for interactive session")

        channel = ssh.invoke_shell(term="xterm-256color", width=cols, height=rows)
        channel.settimeout(0.0)

        self._ssh_clients[session.session_id] = ssh

        return InteractiveSessionRuntime(
            session_id=session.session_id,
            shell_type=session.shell_type,
            ssh_client=ssh,
            ssh_channel=channel,
        )

    def _start_docker_interactive(
        self,
        session: ShellSession,
        cols: int,
        rows: int,
    ) -> InteractiveSessionRuntime:
        """Start interactive docker exec with TTY and attached socket."""
        container = self.docker_client.containers.get(session.target)
        if container.status != "running":
            raise ValueError(
                f"Container {session.target} is not running "
                f"(status: {container.status})"
            )

        metadata = session.metadata or {}
        shell_command = metadata.get("docker_command") or "/bin/bash"
        env_vars = (session.environment or {}).copy()
        docker_user = session.user or "root"
        docker_workdir = session.working_dir or "/"

        exec_data = self.docker_client.api.exec_create(
            container.id,
            shell_command,
            user=docker_user,
            workdir=docker_workdir,
            environment=env_vars,
            tty=True,
            stdin=True,
        )
        exec_id = exec_data.get("Id")
        if not exec_id:
            raise ValueError("Docker exec creation failed")
        stream = self.docker_client.api.exec_start(
            exec_id,
            tty=True,
            stream=False,
            socket=True,
        )
        docker_socket = self._extract_raw_socket(stream)
        if hasattr(docker_socket, "setblocking"):
            docker_socket.setblocking(False)
        if hasattr(docker_socket, "settimeout"):
            docker_socket.settimeout(0.1)

        self.docker_client.api.exec_resize(exec_id, height=rows, width=cols)

        return InteractiveSessionRuntime(
            session_id=session.session_id,
            shell_type=session.shell_type,
            docker_exec_id=exec_id,
            docker_stream=stream,
            docker_socket=docker_socket,
        )

    async def _stream_local_interactive(
        self,
        runtime: InteractiveSessionRuntime,
    ) -> AsyncIterator[bytes]:
        """Stream bytes from local PTY master."""
        master_fd = runtime.pty_master_fd
        process = runtime.local_process

        if master_fd is None or process is None:
            return

        while runtime.active:
            try:
                chunk = os.read(master_fd, 4096)
                if chunk:
                    yield chunk
                    continue
            except BlockingIOError:
                pass
            except OSError as exc:
                if exc.errno in (errno.EIO, errno.EBADF):
                    break
                raise

            if process.poll() is not None:
                break

            await asyncio.sleep(0.01)

    async def _stream_ssh_interactive(
        self,
        runtime: InteractiveSessionRuntime,
    ) -> AsyncIterator[bytes]:
        """Stream bytes from interactive SSH channel."""
        channel = runtime.ssh_channel
        if not channel:
            return

        while runtime.active:
            try:
                if channel.recv_ready():
                    chunk = channel.recv(4096)
                    if chunk:
                        yield chunk
                        continue
                    break

                if channel.closed:
                    break
            except Exception:
                await asyncio.sleep(0.01)
                continue

            await asyncio.sleep(0.01)

    async def _stream_docker_interactive(
        self,
        runtime: InteractiveSessionRuntime,
    ) -> AsyncIterator[bytes]:
        """Stream bytes from interactive docker exec socket."""
        docker_socket = runtime.docker_socket
        if not docker_socket:
            return

        while runtime.active:
            try:
                chunk = await asyncio.to_thread(docker_socket.recv, 4096)
                if chunk:
                    yield chunk
                    continue
                break
            except BlockingIOError:
                await asyncio.sleep(0.01)
                continue
            except TimeoutError:
                await asyncio.sleep(0.01)
                continue
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    await asyncio.sleep(0.01)
                    continue
                if exc.errno in (errno.EIO, errno.EBADF):
                    break
                raise

    def _cleanup_interactive_runtime(self, runtime: InteractiveSessionRuntime):
        """Close all resources for an interactive runtime."""
        runtime.active = False

        if runtime.pty_master_fd is not None:
            try:
                os.close(runtime.pty_master_fd)
            except OSError:
                pass
            runtime.pty_master_fd = None

        if runtime.pty_slave_fd is not None:
            try:
                os.close(runtime.pty_slave_fd)
            except OSError:
                pass
            runtime.pty_slave_fd = None

        if runtime.local_process is not None:
            try:
                if runtime.local_process.poll() is None:
                    runtime.local_process.terminate()
            except Exception:
                pass
            runtime.local_process = None

        if runtime.ssh_channel is not None:
            try:
                runtime.ssh_channel.close()
            except Exception:
                pass
            runtime.ssh_channel = None

        if runtime.ssh_client is not None:
            try:
                runtime.ssh_client.close()
            except Exception:
                pass
            runtime.ssh_client = None
            self._ssh_clients.pop(runtime.session_id, None)

        if runtime.docker_socket is not None:
            try:
                runtime.docker_socket.close()
            except Exception:
                pass
            runtime.docker_socket = None

        if runtime.docker_stream is not None:
            try:
                runtime.docker_stream.close()
            except Exception:
                pass
            runtime.docker_stream = None

    async def _execute_docker_command(
        self, session: ShellSession, command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command in Docker container with streaming output."""
        try:
            container = self.docker_client.containers.get(session.target)

            # Prepare environment variables
            env_vars = (session.environment or {}).copy()

            # Execute command with streaming
            exec_result = container.exec_run(
                command,
                user=session.user or "root",
                workdir=session.working_dir or "/",
                environment=env_vars,
                stream=True,
                demux=True,  # Separate stdout and stderr
            )

            # Stream output
            for stdout, stderr in exec_result.output:
                if stdout:
                    yield ShellOutput(
                        session_id=session.session_id,
                        output=stdout.decode("utf-8", errors="replace"),
                        error=False,
                    )
                if stderr:
                    yield ShellOutput(
                        session_id=session.session_id,
                        output=stderr.decode("utf-8", errors="replace"),
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
        self, session: ShellSession, command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command via SSH with streaming output."""
        ssh = None
        try:
            # Get or create SSH client for this session
            if session.session_id not in self._ssh_clients:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                metadata = session.metadata or {}
                ssh_port = metadata.get("ssh_port", 22)
                ssh_key_path = metadata.get("ssh_key_path")

                if ssh_key_path:
                    ssh.connect(
                        session.target,
                        port=ssh_port,
                        username=session.user or "root",
                        key_filename=ssh_key_path,
                    )
                else:
                    # Note: Password should be stored securely, not in metadata
                    raise ValueError(
                        "SSH password authentication not implemented for security reasons"
                    )

                self._ssh_clients[session.session_id] = ssh
            else:
                ssh = self._ssh_clients[session.session_id]

            # Prepare command with environment and working directory
            env_str = " ".join(
                [
                    f"{k}={shlex.quote(v)}"
                    for k, v in (session.environment or {}).items()
                ]
            )
            full_command = (
                f"cd {shlex.quote(session.working_dir or '/')} && {env_str} {command}"
            )

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
        self, session: ShellSession, command: str
    ) -> AsyncIterator[ShellOutput]:
        """Execute command locally with streaming output."""
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(session.environment or {})

            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=session.working_dir or "/",
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
                        output=line.decode("utf-8", errors="replace"),
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

            interactive_runtime = self._interactive_sessions.pop(session_id, None)
            if interactive_runtime:
                self._cleanup_interactive_runtime(interactive_runtime)

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

    async def check_package_installed(
        self, package_name: str, package_manager: str = "auto"
    ) -> tuple[bool, str]:
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
        yes_to_prompts: bool = True,
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
