"""WebSocket handler for shell sessions."""

import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
import logging

from hiveden.shell.manager import ShellManager
from hiveden.shell.models import ShellCommand, ShellSessionCreate

logger = logging.getLogger(__name__)


class ShellWebSocketHandler:
    """Handles WebSocket connections for shell sessions."""

    def __init__(self, shell_manager: ShellManager):
        self.shell_manager = shell_manager
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        """Accept WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            session_id: Optional session ID to associate with connection
        """
        await websocket.accept()
        if session_id:
            self.active_connections[session_id] = websocket
            logger.info(f"WebSocket connected for session {session_id}")

    def disconnect(self, session_id: str):
        """Disconnect WebSocket.
        
        Args:
            session_id: Session ID to disconnect
        """
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session {session_id}")

    async def handle_session(self, websocket: WebSocket, session_id: str):
        """Handle WebSocket messages for a shell session.
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID
        """
        await self.connect(websocket, session_id)
        
        try:
            # Verify session exists
            session = self.shell_manager.get_session(session_id)
            if not session:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Session {session_id} not found"
                })
                await websocket.close()
                return
            
            # Send session info
            await websocket.send_json({
                "type": "session_info",
                "data": jsonable_encoder(session.dict())
            })
            
            # Send initial prompt
            await self._send_prompt(websocket, session_id)
            
            command_buffer = ""
            
            # Handle incoming messages
            while True:
                try:
                    # Receive message from client
                    data = await websocket.receive_json()
                    message_type = data.get("type")
                    
                    if message_type == "command":
                        # Execute command and stream output
                        command = data.get("command", "")
                        await self._execute_and_stream(websocket, session_id, command)
                        await self._send_prompt(websocket, session_id)

                    elif message_type == "input":
                        # Handle interactive input (xterm.js style)
                        # content usually comes in 'data' or 'input' field
                        content = data.get("data") or data.get("input") or ""
                        
                        # Echo input back to client so they see what they type
                        # (Local echo is often disabled in term libraries connected to WS)
                        await websocket.send_json({
                            "type": "output",
                            "data": {
                                "session_id": session_id,
                                "output": content,
                                "error": False
                            }
                        })
                        
                        command_buffer += content
                        
                        # Check for Enter key (Carriage Return)
                        if "\r" in content:
                            # Extract command (remove newlines)
                            cmd = command_buffer.strip()
                            command_buffer = ""
                            
                            # If we have a command, execute it
                            if cmd:
                                # Add a newline before execution output to look clean
                                await websocket.send_json({
                                    "type": "output",
                                    "data": {
                                        "session_id": session_id,
                                        "output": "\n",
                                        "error": False
                                    }
                                })
                                await self._execute_and_stream(websocket, session_id, cmd)
                                await self._send_prompt(websocket, session_id)
                            else:
                                # Just enter pressed (empty command), show prompt again
                                await websocket.send_json({
                                    "type": "output",
                                    "data": {
                                        "session_id": session_id,
                                        "output": "\n",
                                        "error": False
                                    }
                                })
                                await self._send_prompt(websocket, session_id)
                    
                    elif message_type == "ping":
                        # Respond to ping
                        await websocket.send_json({"type": "pong"})
                    
                    elif message_type == "close":
                        # Close session
                        self.shell_manager.close_session(session_id)
                        await websocket.send_json({
                            "type": "session_closed",
                            "session_id": session_id
                        })
                        break
                    
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown message type: {message_type}"
                        })
                
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for session {session_id}")
                    break
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
        
        finally:
            self.disconnect(session_id)

    async def _execute_and_stream(self, websocket: WebSocket, session_id: str, command: str):
        """Execute command and stream output to WebSocket.
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID
            command: Command to execute
        """
        try:
            # Send command acknowledgment
            await websocket.send_json({
                "type": "command_started",
                "command": command
            })
            
            # Execute command and stream output
            async for output in self.shell_manager.execute_command_stream(session_id, command):
                await websocket.send_json({
                    "type": "output",
                    "data": jsonable_encoder(output.dict())
                })
            
            # Send command completion
            await websocket.send_json({
                "type": "command_completed",
                "command": command
            })
        
        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error executing command: {str(e)}"
            })

    async def handle_package_install(self, websocket: WebSocket, package_name: str, package_manager: str = "auto"):
        """Handle package installation with real-time output.
        
        Args:
            websocket: WebSocket connection
            package_name: Package to install
            package_manager: Package manager to use
        """
        await self.connect(websocket)
        
        try:
            # Send installation started message
            await websocket.send_json({
                "type": "install_started",
                "package": package_name,
                "package_manager": package_manager
            })
            
            # Stream installation output
            async for output in self.shell_manager.install_package_stream(package_name, package_manager):
                await websocket.send_json({
                    "type": "output",
                    "data": jsonable_encoder(output.dict())
                })
            
            # Send installation completed
            await websocket.send_json({
                "type": "install_completed",
                "package": package_name
            })
        
        except Exception as e:
            logger.error(f"Error installing package: {str(e)}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error installing package: {str(e)}"
            })
        
        finally:
            await websocket.close()

    async def _send_prompt(self, websocket: WebSocket, session_id: str):
        """Send a shell prompt to the client."""
        session = self.shell_manager.get_session(session_id)
        if session:
            prompt_suffix = "# " if session.user == "root" else "$ "
            prompt = f"{session.user}@{session.target}:{session.working_dir}{prompt_suffix}"
            await websocket.send_json({
                "type": "output",
                "data": {
                    "session_id": session_id,
                    "output": prompt,
                    "error": False
                }
            })
