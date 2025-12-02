"""Shell module for Hiveden.

This module provides interactive shell capabilities for:
- Docker container exec sessions
- SSH connections to LXC containers
- Local system command execution with real-time output
"""

from hiveden.shell.manager import ShellManager
from hiveden.shell.models import ShellSession, ShellType, ShellCommand, ShellOutput

__all__ = [
    "ShellManager",
    "ShellSession",
    "ShellType",
    "ShellCommand",
    "ShellOutput",
]
