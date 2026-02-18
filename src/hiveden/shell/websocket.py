"""WebSocket handler for shell sessions."""

import json
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
import logging

from hiveden.shell.manager import ShellManager
from hiveden.jobs.manager import JobManager
from hiveden.services.logs import LogService

logger = logging.getLogger(__name__)


class ShellWebSocketHandler:
    """Handles WebSocket connections for shell sessions."""

    def __init__(self, shell_manager: ShellManager):
        self.shell_manager = shell_manager
        self.active_connections: dict[str, WebSocket] = {}
        self.job_manager = JobManager()

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

    async def handle_job_monitoring(self, websocket: WebSocket, job_id: str):
        """Handle WebSocket for job monitoring.

        Args:
            websocket: WebSocket connection
            job_id: Job ID to monitor
        """
        await websocket.accept()
        logger.info(f"WebSocket connected for job {job_id}")

        try:
            # Send initial job info if needed
            job = self.job_manager.get_job(job_id)
            if not job:
                await websocket.send_json(
                    {"type": "error", "message": f"Job {job_id} not found"}
                )
                await websocket.close()
                return

            await websocket.send_json(
                {
                    "type": "job_info",
                    "data": jsonable_encoder(job.dict(exclude={"logs"})),
                }
            )

            # Subscribe to job logs
            async for log in self.job_manager.subscribe(job_id):
                await websocket.send_json(
                    {"type": "log", "data": jsonable_encoder(log)}
                )

            # Send completion message
            # Refresh job status to get final state
            job = self.job_manager.get_job(job_id)
            await websocket.send_json(
                {
                    "type": "job_completed",
                    "data": jsonable_encoder(job.dict(exclude={"logs"})),
                }
            )

        except Exception as e:
            logger.error(f"Error monitoring job {job_id}: {str(e)}")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except:
                pass
        finally:
            try:
                await websocket.close()
            except:
                pass

    async def handle_session(self, websocket: WebSocket, session_id: str):
        """Handle WebSocket messages for a shell session.

        Args:
            websocket: WebSocket connection
            session_id: Session ID
        """
        await self.connect(websocket, session_id)

        output_task: Optional[asyncio.Task] = None

        try:
            # Verify session exists
            session = self.shell_manager.get_session(session_id)
            if not session:
                await websocket.send_json(
                    {"type": "error", "message": f"Session {session_id} not found"}
                )
                await websocket.close()
                return

            # Send session info
            await websocket.send_json(
                {"type": "session_info", "data": jsonable_encoder(session.dict())}
            )

            await self.shell_manager.start_interactive_session(
                session_id=session_id,
                cols=120,
                rows=30,
            )
            output_task = asyncio.create_task(
                self._forward_interactive_output(websocket, session_id)
            )

            # Handle incoming messages
            while True:
                try:
                    # Receive message from client
                    data = await websocket.receive_json()
                    message_type = data.get("type")

                    if message_type == "command":
                        command = data.get("command", "")
                        if command:
                            await websocket.send_json(
                                {"type": "command_started", "command": command}
                            )
                            await self.shell_manager.send_interactive_input(
                                session_id,
                                command,
                            )
                            await self.shell_manager.send_interactive_input(
                                session_id,
                                "\n",
                            )
                            await websocket.send_json(
                                {"type": "command_completed", "command": command}
                            )

                    elif message_type == "input":
                        content = data.get("data") or data.get("input") or ""
                        if content:
                            await self.shell_manager.send_interactive_input(
                                session_id,
                                content,
                            )

                    elif message_type == "resize":
                        cols = data.get("cols") or data.get("columns") or 120
                        rows = data.get("rows") or data.get("height") or 30
                        await self.shell_manager.resize_interactive_session(
                            session_id,
                            cols=int(cols),
                            rows=int(rows),
                        )

                    elif message_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif message_type == "close":
                        self.shell_manager.close_session(session_id)
                        await websocket.send_json(
                            {"type": "session_closed", "session_id": session_id}
                        )
                        break

                    else:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Unknown message type: {message_type}",
                            }
                        )

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for session {session_id}")
                    break
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid JSON"}
                    )
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    try:
                        await websocket.send_json({"type": "error", "message": str(e)})
                    except Exception:
                        break

        finally:
            if output_task:
                output_task.cancel()
                await asyncio.gather(output_task, return_exceptions=True)
            await self.shell_manager.stop_interactive_session(session_id)
            self.disconnect(session_id)

    async def _forward_interactive_output(self, websocket: WebSocket, session_id: str):
        """Forward interactive shell stream to the websocket client."""
        try:
            async for output in self.shell_manager.stream_interactive_output(
                session_id
            ):
                await websocket.send_json(
                    {"type": "output", "data": jsonable_encoder(output.dict())}
                )
        except Exception as e:
            logger.error(f"Error streaming interactive output: {str(e)}")
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
            except Exception:
                pass

    async def _execute_and_stream(
        self, websocket: WebSocket, session_id: str, command: str
    ):
        """Execute command and stream output to WebSocket.

        Args:
            websocket: WebSocket connection
            session_id: Session ID
            command: Command to execute
        """
        try:
            # Send command acknowledgment
            await websocket.send_json({"type": "command_started", "command": command})

            # Execute command and stream output
            async for output in self.shell_manager.execute_command_stream(
                session_id, command
            ):
                await websocket.send_json(
                    {"type": "output", "data": jsonable_encoder(output.dict())}
                )

            # Send command completion
            await websocket.send_json({"type": "command_completed", "command": command})

        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            await websocket.send_json(
                {"type": "error", "message": f"Error executing command: {str(e)}"}
            )

    async def handle_package_install(
        self, websocket: WebSocket, package_name: str, package_manager: str = "auto"
    ):
        """Handle package installation with real-time output.

        Args:
            websocket: WebSocket connection
            package_name: Package to install
            package_manager: Package manager to use
        """
        await self.connect(websocket)

        try:
            LogService().info(
                actor="user",
                action="pkgs.install",
                message=f"Started installing package {package_name}",
                module="pkgs",
                metadata={"package": package_name, "manager": package_manager},
            )

            # Send installation started message
            await websocket.send_json(
                {
                    "type": "install_started",
                    "package": package_name,
                    "package_manager": package_manager,
                }
            )

            # Stream installation output
            async for output in self.shell_manager.install_package_stream(
                package_name, package_manager
            ):
                await websocket.send_json(
                    {"type": "output", "data": jsonable_encoder(output.dict())}
                )

            LogService().info(
                actor="user",
                action="pkgs.install.complete",
                message=f"Completed installation of package {package_name}",
                module="pkgs",
                metadata={"package": package_name},
            )

            # Send installation completed
            await websocket.send_json(
                {"type": "install_completed", "package": package_name}
            )

        except Exception as e:
            LogService().error(
                actor="user",
                action="pkgs.install.error",
                message=f"Error installing package {package_name}",
                module="pkgs",
                error_details=str(e),
                metadata={"package": package_name},
            )
            logger.error(f"Error installing package: {str(e)}")
            await websocket.send_json(
                {"type": "error", "message": f"Error installing package: {str(e)}"}
            )

        finally:
            await websocket.close()
