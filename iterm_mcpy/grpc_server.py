"""gRPC server implementation for iTerm2 controller."""

import asyncio
import logging
import os
from typing import Optional

import grpc
import iterm2

from core.agents import AgentRegistry
from core.layouts import LayoutManager, LayoutType
from core.terminal import ItermTerminal
from iterm_mcpy import iterm_mcp_pb2
from iterm_mcpy import iterm_mcp_pb2_grpc

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
        self._init_lock = asyncio.Lock()
        self.agent_registry: AgentRegistry = AgentRegistry()

    async def initialize(self):
        """Initialize the iTerm2 connection and services.

        Uses double-check locking pattern to prevent race conditions when
        multiple concurrent gRPC requests arrive before initialization completes.
        """
        # First check without lock (fast path)
        if self.terminal:
            return True

        # Acquire lock for initialization
        async with self._init_lock:
            # Double-check after acquiring lock
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
                # Reset state on initialization failure to allow retry
                self.terminal = None
                self.connection = None
                return False

    async def ListSessions(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Failed to initialize iTerm2 connection")
            return iterm_mcp_pb2.SessionList()

        sessions = list(self.terminal.sessions.values())
        pb_sessions = []
        for s in sessions:
            agent = self.agent_registry.get_agent_by_session(s.id)
            pb_sessions.append(iterm_mcp_pb2.Session(
                id=s.id,
                name=s.name,
                persistent_id=s.persistent_id,
                is_processing=getattr(s, 'is_processing', False),
                agent=agent.name if agent else ""
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

    async def CreateSessions(self, request, context):
        if not await self.initialize():
            context.set_code(grpc.StatusCode.INTERNAL)
            return iterm_mcp_pb2.CreateSessionsResponse()

        layout_type_map = {
            "single": LayoutType.SINGLE,
            "horizontal": LayoutType.HORIZONTAL_SPLIT,
            "vertical": LayoutType.VERTICAL_SPLIT,
            "quad": LayoutType.QUAD
        }

        layout_enum = layout_type_map.get(request.layout.lower(), LayoutType.SINGLE) if request.layout else LayoutType.SINGLE

        session_configs = list(request.sessions)
        pane_names = [cfg.name for cfg in session_configs]
        pane_hierarchy = [
            {
                "name": cfg.name,
                "team": cfg.team,
                "agent": cfg.agent,
            }
            for cfg in session_configs
        ]

        try:
            sessions_map = await self.layout_manager.create_layout(
                layout_type=layout_enum,
                pane_names=pane_names,
                pane_hierarchy=pane_hierarchy,
            )

            created_sessions = []
            created_items = list(sessions_map.items())

            for idx, (pane_name, session_id) in enumerate(created_items):
                session = await self.terminal.get_session_by_id(session_id)
                if not session:
                    continue

                cfg = session_configs[idx] if idx < len(session_configs) else None
                agent_name = ""
                team_name = ""

                if cfg:
                    team_name = cfg.team
                    if team_name and not self.agent_registry.get_team(team_name):
                        self.agent_registry.create_team(team_name)

                    if cfg.agent:
                        teams = [team_name] if team_name else []
                        self.agent_registry.register_agent(
                            name=cfg.agent,
                            session_id=session.id,
                            teams=teams,
                        )
                        agent_name = cfg.agent

                    if cfg.command:
                        await session.execute_command(cfg.command)

                created_sessions.append(iterm_mcp_pb2.CreatedSession(
                    session_id=session.id,
                    name=session.name,
                    agent=agent_name,
                    persistent_id=session.persistent_id,
                ))

            if created_sessions and not self.agent_registry.active_session:
                self.agent_registry.active_session = created_sessions[0].session_id

            return iterm_mcp_pb2.CreateSessionsResponse(sessions=created_sessions)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return iterm_mcp_pb2.CreateSessionsResponse()

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

        # Validate max_lines: 0 means use default, negative is invalid, positive is explicit
        if request.max_lines < 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("max_lines must be a non-negative integer (0 for default)")
            return iterm_mcp_pb2.TerminalOutput()

        # In proto3, int32 defaults to 0 when unset, so treat 0 as None (use default)
        max_lines = None if request.max_lines == 0 else request.max_lines
        output = await session.get_screen_contents(max_lines=max_lines)
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
        if not session:
            agent = self.agent_registry.get_agent(identifier)
            if agent:
                session = await self.terminal.get_session_by_id(agent.session_id)
        return session


async def serve():
    server = grpc.aio.server()
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
