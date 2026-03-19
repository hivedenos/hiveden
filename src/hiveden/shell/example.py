#!/usr/bin/env python3
"""
Example script demonstrating the Hiveden Shell module.

This script shows how to:
1. Create a Docker shell session
2. Execute commands via WebSocket
3. Handle real-time output
4. Install packages with streaming output
"""

import asyncio
import json
import sys
from typing import Optional

try:
    import websockets
    import requests
except ImportError:
    print("Please install required packages:")
    print("  pip install websockets requests")
    sys.exit(1)


class ShellClient:
    """Simple client for Hiveden Shell API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    
    def create_docker_session(self, container_id: str, user: str = "root", working_dir: str = "/") -> dict:
        """Create a Docker shell session."""
        response = requests.post(
            f"{self.base_url}/shell/docker/{container_id}/shell",
            json={
                "user": user,
                "working_dir": working_dir
            }
        )
        response.raise_for_status()
        return response.json()["data"]
    
    def create_local_session(self, working_dir: str = "/tmp") -> dict:
        """Create a local shell session."""
        response = requests.post(
            f"{self.base_url}/shell/sessions",
            json={
                "shell_type": "local",
                "target": "localhost",
                "working_dir": working_dir
            }
        )
        response.raise_for_status()
        return response.json()["data"]
    
    def list_sessions(self) -> list:
        """List all active sessions."""
        response = requests.get(f"{self.base_url}/shell/sessions")
        response.raise_for_status()
        return response.json()["data"]
    
    def close_session(self, session_id: str):
        """Close a session."""
        response = requests.delete(f"{self.base_url}/shell/sessions/{session_id}")
        response.raise_for_status()
        return response.json()
    
    async def execute_command(self, session_id: str, command: str):
        """Execute a command and print output in real-time."""
        async with websockets.connect(f"{self.ws_url}/shell/ws/{session_id}") as ws:
            # Receive session info
            session_info = await ws.recv()
            session_data = json.loads(session_info)
            print(f"Connected to session: {session_data['data']['session_id']}")
            print(f"Shell type: {session_data['data']['shell_type']}")
            print(f"Target: {session_data['data']['target']}\n")
            
            # Send command
            await ws.send(json.dumps({
                "type": "command",
                "command": command
            }))
            
            print(f"$ {command}")
            
            # Receive output
            while True:
                message = await ws.recv()
                data = json.loads(message)
                
                if data["type"] == "output":
                    output_data = data["data"]
                    
                    # Print output
                    if output_data["output"]:
                        if output_data["error"]:
                            print(f"\033[91m{output_data['output']}\033[0m", end="")  # Red for errors
                        else:
                            print(output_data["output"], end="")
                    
                    # Check if command completed
                    if output_data.get("exit_code") is not None:
                        print(f"\n\nCommand exited with code: {output_data['exit_code']}")
                        break
                
                elif data["type"] == "command_completed":
                    print("\nCommand completed")
                    break
                
                elif data["type"] == "error":
                    print(f"\n\033[91mError: {data['message']}\033[0m")
                    break
    
    async def install_package(self, package_name: str, package_manager: str = "auto"):
        """Install a package and show real-time output."""
        url = f"{self.ws_url}/shell/ws/packages/install?package_name={package_name}&package_manager={package_manager}"
        
        async with websockets.connect(url) as ws:
            print(f"Installing package: {package_name}\n")
            
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                    
                    if data["type"] == "install_started":
                        print(f"Installation started using {data['package_manager']}")
                        print("-" * 60)
                    
                    elif data["type"] == "output":
                        output_data = data["data"]
                        if output_data["output"]:
                            if output_data["error"]:
                                print(f"\033[91m{output_data['output']}\033[0m", end="")
                            else:
                                print(output_data["output"], end="")
                    
                    elif data["type"] == "install_completed":
                        print("\n" + "-" * 60)
                        print(f"Package {package_name} installed successfully!")
                        break
                    
                    elif data["type"] == "error":
                        print(f"\n\033[91mError: {data['message']}\033[0m")
                        break
                
                except websockets.exceptions.ConnectionClosed:
                    break


async def demo_docker_shell(container_id: str):
    """Demonstrate Docker shell functionality."""
    client = ShellClient()
    
    print("=" * 60)
    print("Docker Shell Demo")
    print("=" * 60)
    
    # Create session
    print(f"\nCreating shell session for container: {container_id}")
    session = client.create_docker_session(container_id)
    session_id = session["session_id"]
    print(f"Session created: {session_id}\n")
    
    # Execute some commands
    commands = [
        "pwd",
        "ls -la",
        "echo 'Hello from Hiveden Shell!'",
        "whoami",
    ]
    
    for cmd in commands:
        await client.execute_command(session_id, cmd)
        print("\n")
        await asyncio.sleep(1)
    
    # Close session
    print(f"Closing session: {session_id}")
    client.close_session(session_id)
    print("Session closed\n")


async def demo_local_shell():
    """Demonstrate local shell functionality."""
    client = ShellClient()
    
    print("=" * 60)
    print("Local Shell Demo")
    print("=" * 60)
    
    # Create session
    print("\nCreating local shell session")
    session = client.create_local_session(working_dir="/tmp")
    session_id = session["session_id"]
    print(f"Session created: {session_id}\n")
    
    # Execute commands
    commands = [
        "pwd",
        "uname -a",
        "date",
    ]
    
    for cmd in commands:
        await client.execute_command(session_id, cmd)
        print("\n")
        await asyncio.sleep(1)
    
    # Close session
    print(f"Closing session: {session_id}")
    client.close_session(session_id)
    print("Session closed\n")


async def demo_package_install(package_name: str):
    """Demonstrate package installation."""
    client = ShellClient()
    
    print("=" * 60)
    print("Package Installation Demo")
    print("=" * 60)
    print()
    
    await client.install_package(package_name)


async def demo_list_sessions():
    """Demonstrate listing sessions."""
    client = ShellClient()
    
    print("=" * 60)
    print("Active Sessions")
    print("=" * 60)
    
    sessions = client.list_sessions()
    
    if not sessions:
        print("\nNo active sessions")
    else:
        for session in sessions:
            print(f"\nSession ID: {session['session_id']}")
            print(f"  Type: {session['shell_type']}")
            print(f"  Target: {session['target']}")
            print(f"  User: {session['user']}")
            print(f"  Working Dir: {session['working_dir']}")
            print(f"  Created: {session['created_at']}")
            print(f"  Active: {session['active']}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hiveden Shell Module Demo")
    parser.add_argument(
        "demo",
        choices=["docker", "local", "package", "list"],
        help="Demo to run"
    )
    parser.add_argument(
        "--container",
        help="Docker container ID (for docker demo)"
    )
    parser.add_argument(
        "--package",
        help="Package name (for package demo)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Hiveden API URL (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    if args.demo == "docker":
        if not args.container:
            print("Error: --container is required for docker demo")
            sys.exit(1)
        await demo_docker_shell(args.container)
    
    elif args.demo == "local":
        await demo_local_shell()
    
    elif args.demo == "package":
        if not args.package:
            print("Error: --package is required for package demo")
            sys.exit(1)
        await demo_package_install(args.package)
    
    elif args.demo == "list":
        await demo_list_sessions()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\033[91mError: {str(e)}\033[0m")
        sys.exit(1)
