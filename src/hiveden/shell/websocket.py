"""WebSocket handler for shell sessions."""

import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
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
                "data": session.dict()
            })
            
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
                    "data": output.dict()
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
                    "data": output.dict()
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
