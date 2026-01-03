"""Message handlers for terminal operations.

This module provides the default message handlers that integrate
the typed message-based communication with the iTerm terminal backend.

These handlers can be used directly or serve as examples for custom handlers.
"""

import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

from .messaging import (
    message_handler,
    topic_handler,
    TerminalCommand,
    TerminalOutput,
    TerminalReadRequest,
    TerminalReadResponse,
    ControlCharacterMessage,
    SpecialKeyMessage,
    SessionStatusRequest,
    SessionStatusResponse,
    SessionListRequest,
    SessionListResponse,
    FocusSessionMessage,
    BroadcastNotification,
    AgentTaskRequest,
    AgentTaskResponse,
    WaitForAgentMessage,
    WaitForAgentResponse,
    ErrorMessage,
)
from .models import SessionTarget, ReadTarget

if TYPE_CHECKING:
    from .terminal import ItermTerminal
    from .agents import AgentRegistry

logger = logging.getLogger(__name__)


class TerminalMessageHandlers:
    """Handlers for terminal operation messages.

    This class registers message handlers that interact with the
    iTerm terminal backend. It must be initialized with references
    to the terminal and agent registry.

    Example:
        terminal = ItermTerminal()
        registry = AgentRegistry()
        router = MessageRouter()

        handlers = TerminalMessageHandlers(terminal, registry, router)
        handlers.register_all()

        # Now messages can be routed
        response = await router.send(TerminalCommand(...))
    """

    def __init__(
        self,
        terminal: "ItermTerminal",
        agent_registry: "AgentRegistry",
    ):
        """Initialize handlers with backend references.

        Args:
            terminal: The iTerm terminal instance
            agent_registry: The agent registry for session lookups
        """
        self.terminal = terminal
        self.agent_registry = agent_registry

    async def resolve_session(self, target: SessionTarget) -> Optional[str]:
        """Resolve a SessionTarget to a session ID.

        Args:
            target: The session target specification

        Returns:
            Session ID if found, None otherwise
        """
        # Direct session ID
        if target.session_id:
            return target.session_id

        # By session name
        if target.name:
            session = self.terminal.get_session_by_name(target.name)
            if session:
                return session.session_id

        # By agent name
        if target.agent:
            agent = self.agent_registry.get_agent(target.agent)
            if agent:
                return agent.session_id

        # By team (returns first member)
        if target.team:
            agents = self.agent_registry.list_agents(team=target.team)
            if agents:
                return agents[0].session_id

        return None

    async def handle_terminal_command(
        self,
        message: TerminalCommand
    ) -> TerminalOutput:
        """Handle a terminal command execution request.

        Args:
            message: The terminal command message

        Returns:
            TerminalOutput with execution results
        """
        start_time = time.time()

        session_id = await self.resolve_session(message.session_target)
        if not session_id:
            return TerminalOutput(
                sender="terminal-service",
                session_id="",
                output="Error: Could not resolve session target",
                correlation_id=message.message_id,
            )

        session = self.terminal.get_session(session_id)
        if not session:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: Session {session_id} not found",
                correlation_id=message.message_id,
            )

        try:
            # Send the command
            await session.send_text(message.command, execute=message.execute)

            # If waiting for completion, poll for output
            output = ""
            if message.wait_for_completion and message.execute:
                await asyncio.sleep(0.5)  # Brief delay for command to start
                output = await session.get_screen_contents()
            else:
                output = await session.get_screen_contents()

            duration = time.time() - start_time

            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                session_name=session.name,
                output=output,
                duration=duration,
                line_count=output.count("\n") + 1 if output else 0,
                correlation_id=message.message_id,
            )

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: {str(e)}",
                correlation_id=message.message_id,
            )

    async def handle_terminal_read(
        self,
        message: TerminalReadRequest
    ) -> TerminalReadResponse:
        """Handle a terminal read request.

        Args:
            message: The read request message

        Returns:
            TerminalReadResponse with output from sessions
        """
        outputs = []

        targets = message.targets or []
        if not targets:
            # Read from active session
            active = self.agent_registry.active_session
            if active:
                targets = [ReadTarget(session_id=active)]

        for target in targets:
            session_id = None

            if target.session_id:
                session_id = target.session_id
            elif target.name:
                session = self.terminal.get_session_by_name(target.name)
                if session:
                    session_id = session.session_id
            elif target.agent:
                agent = self.agent_registry.get_agent(target.agent)
                if agent:
                    session_id = agent.session_id

            if session_id:
                session = self.terminal.get_session(session_id)
                if session:
                    try:
                        content = await session.get_screen_contents(
                            max_lines=target.max_lines or message.max_lines
                        )

                        # Apply filter pattern if specified
                        if message.filter_pattern:
                            import re
                            pattern = re.compile(message.filter_pattern)
                            lines = content.split("\n")
                            filtered = [l for l in lines if pattern.search(l)]
                            content = "\n".join(filtered)

                        outputs.append({
                            "session_id": session_id,
                            "name": session.name,
                            "content": content,
                            "line_count": content.count("\n") + 1 if content else 0,
                        })
                    except Exception as e:
                        outputs.append({
                            "session_id": session_id,
                            "error": str(e),
                        })

        return TerminalReadResponse(
            sender="terminal-service",
            outputs=outputs,
            total_sessions=len(outputs),
            correlation_id=message.message_id,
        )

    async def handle_control_character(
        self,
        message: ControlCharacterMessage
    ) -> TerminalOutput:
        """Handle a control character send request.

        Args:
            message: The control character message

        Returns:
            TerminalOutput confirming the action
        """
        session_id = await self.resolve_session(message.session_target)
        if not session_id:
            return TerminalOutput(
                sender="terminal-service",
                session_id="",
                output="Error: Could not resolve session target",
                correlation_id=message.message_id,
            )

        session = self.terminal.get_session(session_id)
        if not session:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: Session {session_id} not found",
                correlation_id=message.message_id,
            )

        try:
            await session.send_control_character(message.character)
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                session_name=session.name,
                output=f"Sent Ctrl+{message.character.upper()}",
                correlation_id=message.message_id,
            )
        except Exception as e:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: {str(e)}",
                correlation_id=message.message_id,
            )

    async def handle_special_key(
        self,
        message: SpecialKeyMessage
    ) -> TerminalOutput:
        """Handle a special key send request.

        Args:
            message: The special key message

        Returns:
            TerminalOutput confirming the action
        """
        session_id = await self.resolve_session(message.session_target)
        if not session_id:
            return TerminalOutput(
                sender="terminal-service",
                session_id="",
                output="Error: Could not resolve session target",
                correlation_id=message.message_id,
            )

        session = self.terminal.get_session(session_id)
        if not session:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: Session {session_id} not found",
                correlation_id=message.message_id,
            )

        try:
            await session.send_special_key(message.key)
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                session_name=session.name,
                output=f"Sent {message.key} key",
                correlation_id=message.message_id,
            )
        except Exception as e:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: {str(e)}",
                correlation_id=message.message_id,
            )

    async def handle_session_status(
        self,
        message: SessionStatusRequest
    ) -> SessionStatusResponse:
        """Handle a session status request.

        Args:
            message: The status request message

        Returns:
            SessionStatusResponse with session state
        """
        session_id = await self.resolve_session(message.session_target)
        if not session_id:
            return SessionStatusResponse(
                sender="terminal-service",
                session_id="",
                is_processing=False,
                correlation_id=message.message_id,
            )

        session = self.terminal.get_session(session_id)
        if not session:
            return SessionStatusResponse(
                sender="terminal-service",
                session_id=session_id,
                is_processing=False,
                correlation_id=message.message_id,
            )

        agent = self.agent_registry.get_agent_by_session(session_id)

        return SessionStatusResponse(
            sender="terminal-service",
            session_id=session_id,
            session_name=session.name,
            agent=agent.name if agent else None,
            is_processing=session.is_processing,
            is_at_prompt=not session.is_processing,
            correlation_id=message.message_id,
        )

    async def handle_session_list(
        self,
        message: SessionListRequest
    ) -> SessionListResponse:
        """Handle a session list request.

        Args:
            message: The list request message

        Returns:
            SessionListResponse with available sessions
        """
        sessions = []

        for session in self.terminal.list_sessions():
            agent = None
            if message.include_agents:
                agent = self.agent_registry.get_agent_by_session(session.session_id)

            # Apply team filter
            if message.team_filter and agent:
                if message.team_filter not in agent.teams:
                    continue

            session_info = {
                "session_id": session.session_id,
                "name": session.name,
                "is_processing": session.is_processing,
            }

            if agent and message.include_agents:
                session_info["agent"] = agent.name
                session_info["teams"] = agent.teams

            sessions.append(session_info)

        return SessionListResponse(
            sender="terminal-service",
            sessions=sessions,
            total_count=len(sessions),
            correlation_id=message.message_id,
        )

    async def handle_focus_session(
        self,
        message: FocusSessionMessage
    ) -> TerminalOutput:
        """Handle a focus session request.

        Args:
            message: The focus request message

        Returns:
            TerminalOutput confirming the action
        """
        session_id = await self.resolve_session(message.session_target)
        if not session_id:
            return TerminalOutput(
                sender="terminal-service",
                session_id="",
                output="Error: Could not resolve session target",
                correlation_id=message.message_id,
            )

        try:
            await self.terminal.focus_session(session_id)
            self.agent_registry.active_session = session_id

            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Focused session {session_id}",
                correlation_id=message.message_id,
            )
        except Exception as e:
            return TerminalOutput(
                sender="terminal-service",
                session_id=session_id,
                output=f"Error: {str(e)}",
                correlation_id=message.message_id,
            )

    async def handle_wait_for_agent(
        self,
        message: WaitForAgentMessage
    ) -> WaitForAgentResponse:
        """Handle a wait for agent request.

        Args:
            message: The wait request message

        Returns:
            WaitForAgentResponse with wait results
        """
        start_time = time.time()
        agent = self.agent_registry.get_agent(message.target_agent)

        if not agent:
            return WaitForAgentResponse(
                sender="terminal-service",
                agent=message.target_agent,
                completed=False,
                timed_out=True,
                elapsed=0.0,
                correlation_id=message.message_id,
            )

        session = self.terminal.get_session(agent.session_id)
        if not session:
            return WaitForAgentResponse(
                sender="terminal-service",
                agent=message.target_agent,
                completed=False,
                timed_out=True,
                elapsed=0.0,
                correlation_id=message.message_id,
            )

        # Poll for completion
        while True:
            elapsed = time.time() - start_time
            if elapsed >= message.timeout:
                output = None
                if message.include_output:
                    output = await session.get_screen_contents()

                return WaitForAgentResponse(
                    sender="terminal-service",
                    agent=message.target_agent,
                    completed=False,
                    timed_out=True,
                    elapsed=elapsed,
                    output=output,
                    correlation_id=message.message_id,
                )

            if not session.is_processing:
                output = None
                if message.include_output:
                    output = await session.get_screen_contents()

                return WaitForAgentResponse(
                    sender="terminal-service",
                    agent=message.target_agent,
                    completed=True,
                    timed_out=False,
                    elapsed=elapsed,
                    output=output,
                    correlation_id=message.message_id,
                )

            await asyncio.sleep(0.5)

    def register_all(self, router: "MessageRouter") -> None:
        """Register all handlers with a message router.

        Args:
            router: The message router to register with
        """
        from .messaging import MessageRouter

        router.register_handler(TerminalCommand, self.handle_terminal_command)
        router.register_handler(TerminalReadRequest, self.handle_terminal_read)
        router.register_handler(ControlCharacterMessage, self.handle_control_character)
        router.register_handler(SpecialKeyMessage, self.handle_special_key)
        router.register_handler(SessionStatusRequest, self.handle_session_status)
        router.register_handler(SessionListRequest, self.handle_session_list)
        router.register_handler(FocusSessionMessage, self.handle_focus_session)
        router.register_handler(WaitForAgentMessage, self.handle_wait_for_agent)

        logger.info("Registered all terminal message handlers")


# ============================================================================
# EXAMPLE TOPIC HANDLERS
# ============================================================================


@topic_handler("agent.status")
async def log_agent_status(notification: BroadcastNotification) -> None:
    """Log agent status updates."""
    logger.info(
        f"Agent status update from {notification.sender}: {notification.payload}"
    )


@topic_handler("command.executed")
async def log_command_execution(notification: BroadcastNotification) -> None:
    """Log command execution events."""
    logger.debug(
        f"Command executed by {notification.sender}: {notification.payload}"
    )
