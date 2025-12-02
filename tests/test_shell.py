"""
Unit tests for the shell module.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from hiveden.shell.manager import ShellManager
from hiveden.pkgs.base import PackageManager
from hiveden.shell.models import (
    ShellSessionCreate,
    ShellType,
    ShellCommand,
    PackageCheckRequest,
)


class TestShellManager:
    """Test cases for ShellManager."""
    
    @pytest.fixture
    def shell_manager(self):
        """Create a ShellManager instance for testing."""
        return ShellManager()
    
    def test_create_local_session(self, shell_manager):

        """Test creating a local shell session."""
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost",
            user="root",
            working_dir="/tmp"
        )
        
        session = shell_manager.create_session(request)
        
        assert session.session_id is not None
        assert session.shell_type == ShellType.LOCAL
        assert session.target == "localhost"
        assert session.user == "root"
        assert session.working_dir == "/tmp"
        assert session.active is True
    
    @patch('docker.from_env')
    def test_create_docker_session_success(self, mock_docker, shell_manager):
        """Test creating a Docker shell session successfully."""
        # Mock Docker client
        mock_container = Mock()
        mock_container.status = "running"
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        shell_manager.docker_client = mock_client
        
        request = ShellSessionCreate(
            shell_type=ShellType.DOCKER,
            target="test-container",
            user="root",
            working_dir="/app"
        )
        
        session = shell_manager.create_session(request)
        
        assert session.session_id is not None
        assert session.shell_type == ShellType.DOCKER
        assert session.target == "test-container"
        assert session.active is True
    
    @patch('docker.from_env')
    def test_create_docker_session_not_running(self, mock_docker, shell_manager):
        """Test creating a Docker shell session for a stopped container."""
        # Mock Docker client
        mock_container = Mock()
        mock_container.status = "exited"
        mock_client = Mock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client
        
        shell_manager.docker_client = mock_client
        
        request = ShellSessionCreate(
            shell_type=ShellType.DOCKER,
            target="stopped-container",
            user="root"
        )
        
        with pytest.raises(ValueError, match="is not running"):
            shell_manager.create_session(request)
    
    def test_get_session(self, shell_manager):
        """Test getting a session by ID."""
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost"
        )
        
        session = shell_manager.create_session(request)
        retrieved = shell_manager.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_nonexistent_session(self, shell_manager):
        """Test getting a session that doesn't exist."""
        retrieved = shell_manager.get_session("nonexistent-id")
        assert retrieved is None
    
    def test_list_sessions(self, shell_manager):
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(3):
            request = ShellSessionCreate(
                shell_type=ShellType.LOCAL,
                target="localhost",
                working_dir=f"/tmp/test{i}"
            )
            shell_manager.create_session(request)
        
        sessions = shell_manager.list_sessions(active_only=True)
        assert len(sessions) == 3
        assert all(s.active for s in sessions)
    
    def test_close_session(self, shell_manager):
        """Test closing a session."""
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost"
        )
        
        session = shell_manager.create_session(request)
        shell_manager.close_session(session.session_id)
        
        # Session should still exist but be inactive
        retrieved = shell_manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.active is False
    
    @pytest.mark.asyncio
    async def test_execute_local_command(self, shell_manager):
        """Test executing a local command."""
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost",
            working_dir="/tmp"
        )
        
        session = shell_manager.create_session(request)
        
        outputs = []
        async for output in shell_manager.execute_command_stream(session.session_id, "echo 'test'"):
            outputs.append(output)
        
        # Should have at least one output
        assert len(outputs) > 0
        
        # Last output should have exit code
        assert outputs[-1].exit_code is not None
        
        # Should have successful exit code
        assert outputs[-1].exit_code == 0
    
    @pytest.mark.asyncio
    async def test_execute_command_invalid_session(self, shell_manager):
        """Test executing a command with invalid session."""
        with pytest.raises(ValueError, match="not found"):
            async for _ in shell_manager.execute_command_stream("invalid-id", "echo test"):
                pass
    
    @pytest.mark.asyncio
    async def test_check_package_installed(self, shell_manager):
        """Test checking if a package is installed."""
        # This test will depend on the actual system
        # We'll just verify it doesn't crash
        is_installed, message = await shell_manager.check_package_installed("bash", "auto")
        
        assert isinstance(is_installed, bool)
        assert isinstance(message, str)
        assert "bash" in message.lower()
    
    def test_detect_package_manager(self, shell_manager):
        """Test package manager detection."""
        pm = shell_manager._detect_package_manager()
        
        # Should return a PackageManager instance
        assert isinstance(pm, PackageManager)


class TestShellModels:
    """Test cases for shell models."""
    
    def test_shell_session_create_docker(self):
        """Test creating a Docker session request."""
        request = ShellSessionCreate(
            shell_type=ShellType.DOCKER,
            target="my-container",
            user="app",
            working_dir="/app",
            docker_command="/bin/sh"
        )
        
        assert request.shell_type == ShellType.DOCKER
        assert request.target == "my-container"
        assert request.user == "app"
        assert request.docker_command == "/bin/sh"
    
    def test_shell_session_create_ssh(self):
        """Test creating an SSH session request."""
        request = ShellSessionCreate(
            shell_type=ShellType.SSH,
            target="192.168.1.100",
            user="root",
            ssh_port=2222,
            ssh_key_path="/root/.ssh/id_rsa"
        )
        
        assert request.shell_type == ShellType.SSH
        assert request.target == "192.168.1.100"
        assert request.ssh_port == 2222
        assert request.ssh_key_path == "/root/.ssh/id_rsa"
    
    def test_shell_session_create_defaults(self):
        """Test default values in session creation."""
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost"
        )
        
        assert request.user == "root"
        assert request.working_dir == "/"
        assert request.environment == {}
    
    def test_package_check_request(self):
        """Test package check request model."""
        request = PackageCheckRequest(
            package_name="nginx",
            package_manager="apt"
        )
        
        assert request.package_name == "nginx"
        assert request.package_manager == "apt"
    
    def test_shell_command(self):
        """Test shell command model."""
        command = ShellCommand(
            command="ls -la",
            session_id="test-session"
        )
        
        assert command.command == "ls -la"
        assert command.session_id == "test-session"


@pytest.mark.asyncio
class TestShellIntegration:
    """Integration tests for shell functionality."""
    
    @pytest.fixture
    def shell_manager(self):
        """Create a ShellManager instance for testing."""
        return ShellManager()
    
    async def test_full_local_session_lifecycle(self, shell_manager):
        """Test complete lifecycle of a local session."""
        # Create session
        request = ShellSessionCreate(
            shell_type=ShellType.LOCAL,
            target="localhost",
            working_dir="/tmp"
        )
        session = shell_manager.create_session(request)
        
        # Execute command
        outputs = []
        async for output in shell_manager.execute_command_stream(session.session_id, "pwd"):
            outputs.append(output)
        
        # Verify output
        assert len(outputs) > 0
        assert any("/tmp" in o.output for o in outputs if o.output)
        
        # Close session
        shell_manager.close_session(session.session_id)
        
        # Verify session is inactive
        retrieved = shell_manager.get_session(session.session_id)
        assert retrieved.active is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
