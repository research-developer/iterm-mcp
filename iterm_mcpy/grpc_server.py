"""gRPC server implementation for iTerm2 controller."""

import asyncio
import logging
import os
from concurrent import futures
from typing import Optional

import grpc
import iterm2

from core.layouts import LayoutManager, LayoutType
from core.terminal import ItermTerminal
from protos import iterm_mcp_pb2
from protos import iterm_mcp_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iterm-grpc-server")


class ITermService(iterm_mcp_pb2_grpc.ITermServiceServicer):
    """Implementation of the ITermService gRPC service."""

    def __init__(self):
        self.terminal: Optional[ItermTerminal] = None
        self.layout_manager: Optional[LayoutManager] = None
        self.connection: Optional[iterm2.Connection] = None
        self.log_dir = os.path.expanduser("~/.iterm_mcp_logs")

    async def initialize(self):
        """Initialize the iTerm2 connection and services."""
        if self.terminal:
            return True

        try:
            logger.info("Initializing iTerm2 connection...")
            self.connection = await iterm2.Connection.async_create()
            
            self.terminal = ItermTerminal(
                connection=self.connection,
                log_dir=self.log_dir,
                enable_logging=True,
                default_max_lines=100,
                max_snapshot_lines=1000
            )
            await self.terminal.initialize()
            
            self.layout_manager = LayoutManager(self.terminal)
            logger.info("iTerm2 controller initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return False

    async def ListSessions(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Failed to initialize iTerm2 connection")
            return iterm_mcp_pb2.SessionList()

        sessions = list(self.terminal.sessions.values())
        pb_sessions = []
        for s in sessions:
            pb_sessions.append(iterm_mcp_pb2.Session(
                id=s.id,
                name=s.name,
                persistent_id=s.persistent_id,
                is_processing=getattr(s, 'is_processing', False)
            ))
        return iterm_mcp_pb2.SessionList(sessions=pb_sessions)

    async def FocusSession(self, request, context):
        if not await self.initialize():
            return iterm_mcp_pb2.StatusResponse(success=False, message="Failed to initialize")

        identifier = request.identifier
        session = await self._find_session(identifier)

        if not session:
            return iterm_mcp_pb2.StatusResponse(
                success=False,
                message=f"Session not found: {identifier}"
            )

        try:
            await self.terminal.focus_session(session.id)
            return iterm_mcp_pb2.StatusResponse(
                success=True,
                message=f"Focused session: {session.name}"
            )
        except Exception as e:
            return iterm_mcp_pb2.StatusResponse(success=False, message=str(e))

    async def CreateLayout(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            return iterm_mcp_pb2.SessionList()

        layout_type_map = {
            "single": LayoutType.SINGLE,
            "horizontal": LayoutType.HORIZONTAL_SPLIT,
            "vertical": LayoutType.VERTICAL_SPLIT,
            "quad": LayoutType.QUAD
        }

        layout_enum = layout_type_map.get(request.layout_type.lower())
        if not layout_enum:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f"Invalid layout type: {request.layout_type}")
            return iterm_mcp_pb2.SessionList()

        try:
            sessions = await self.layout_manager.create_layout(
                layout_type=layout_enum,
                pane_names=list(request.session_names)
            )

            pb_sessions = []
            for _, session_id in sessions.items():
                s = await self.terminal.get_session_by_id(session_id)
                if s:
                    pb_sessions.append(iterm_mcp_pb2.Session(
                        id=s.id,
                        name=s.name,
                        persistent_id=s.persistent_id,
                        is_processing=getattr(s, 'is_processing', False)
                    ))
            return iterm_mcp_pb2.SessionList(sessions=pb_sessions)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return iterm_mcp_pb2.SessionList()

    async def WriteToTerminal(self, request, context):
        if not await self.initialize():
            return iterm_mcp_pb2.StatusResponse(success=False, message="Failed to initialize")

        session = await self._find_session(request.session_identifier)
        if not session:
            return iterm_mcp_pb2.StatusResponse(
                success=False,
                message=f"Session not found: {request.session_identifier}"
            )

        command = request.command
        if not command.endswith("\n"):
            command += "\n"

        try:
            await session.send_text(command)
            
            if request.wait_for_prompt:
                # Simple wait logic
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if hasattr(session, 'is_processing') and not session.is_processing:
                        break
            
            return iterm_mcp_pb2.StatusResponse(success=True, message="Command sent")
        except Exception as e:
            return iterm_mcp_pb2.StatusResponse(success=False, message=str(e))

    async def ReadTerminalOutput(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            return iterm_mcp_pb2.TerminalOutput()

        session = await self._find_session(request.session_identifier)
        if not session:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return iterm_mcp_pb2.TerminalOutput()

        # Validate max_lines: must be None or a positive integer
        if request.max_lines is not None and request.max_lines <= 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("max_lines must be a positive integer or None")
            return iterm_mcp_pb2.TerminalOutput()

        output = await session.get_screen_contents(
            max_lines=request.max_lines if request.max_lines is not None else None
        )
        return iterm_mcp_pb2.TerminalOutput(output=output)

    async def SendControlCharacter(self, request, context):
        if not await self.initialize():
            return iterm_mcp_pb2.StatusResponse(success=False, message="Failed to initialize")

        session = await self._find_session(request.session_identifier)
        if not session:
            return iterm_mcp_pb2.StatusResponse(
                success=False, 
                message=f"Session not found: {request.session_identifier}"
            )

        try:
            await session.send_control_character(request.control_char)
            return iterm_mcp_pb2.StatusResponse(success=True, message="Control char sent")
        except Exception as e:
            return iterm_mcp_pb2.StatusResponse(success=False, message=str(e))

    async def CheckSessionStatus(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            return iterm_mcp_pb2.SessionStatus()

        session = await self._find_session(request.identifier)
        if not session:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return iterm_mcp_pb2.SessionStatus()

        return iterm_mcp_pb2.SessionStatus(
            name=session.name,
            id=session.id,
            persistent_id=session.persistent_id,
            is_processing=getattr(session, 'is_processing', False)
        )

    async def _find_session(self, identifier):
        if not self.terminal:
            return None
        
        session = await self.terminal.get_session_by_id(identifier)
        if not session:
            session = await self.terminal.get_session_by_name(identifier)
        if not session:
            session = await self.terminal.get_session_by_persistent_id(identifier)
        return session


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    iterm_mcp_pb2_grpc.add_ITermServiceServicer_to_server(ITermService(), server)
    server.add_insecure_port('[::]:50051')
    logger.info("Starting gRPC server on port 50051...")
    await server.start()
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Stopping server...")
        await server.stop(0)

if __name__ == '__main__':
    asyncio.run(serve())
