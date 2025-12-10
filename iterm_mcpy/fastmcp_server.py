"""MCP server implementation for iTerm2 controller using the official MCP Python SDK.

This version supports parallel multi-session operations with agent/team management.
"""

import asyncio
import json
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Any

import iterm2
from mcp.server.fastmcp import FastMCP, Context

from core.layouts import LayoutManager, LayoutType
from core.session import ItermSession
from core.terminal import ItermTerminal
from core.agents import AgentRegistry, CascadingMessage
from core.models import (
    SessionTarget,
    SessionMessage,
    WriteToSessionsRequest,
    WriteResult,
    WriteToSessionsResponse,
    ReadTarget,
    ReadSessionsRequest,
    ReadSessionsResponse,
    SessionOutput,
    CreateSessionsRequest,
    CreatedSession,
    CreateSessionsResponse,
    CascadeMessageRequest,
    CascadeResult,
    CascadeMessageResponse,
    RegisterAgentRequest,
    CreateTeamRequest,
    SetActiveSessionRequest,
    PlaybookCommandResult,
    OrchestrateRequest,
    OrchestrateResponse,
)

# Global references for resources (set during lifespan)
_terminal: Optional[ItermTerminal] = None
_logger: Optional[logging.Logger] = None
_agent_registry: Optional[AgentRegistry] = None


@asynccontextmanager
async def iterm_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage the lifecycle of iTerm2 connections and resources.

    Args:
        server: The FastMCP server instance

    Yields:
        A dictionary containing initialized resources
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.expanduser("~/.iterm-mcp.log")),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger("iterm-mcp-server")
    logger.info("Initializing iTerm2 connection...")

    connection = None
    terminal = None
    layout_manager = None
    agent_registry = None

    try:
        # Initialize iTerm2 connection
        try:
            connection = await iterm2.Connection.async_create()
            logger.info("iTerm2 connection established successfully")
        except Exception as conn_error:
            logger.error(f"Failed to establish iTerm2 connection: {str(conn_error)}")
            raise

        # Initialize terminal controller
        logger.info("Initializing iTerm terminal controller...")
        log_dir = os.path.expanduser("~/.iterm_mcp_logs")
        terminal = ItermTerminal(
            connection=connection,
            log_dir=log_dir,
            enable_logging=True,
            default_max_lines=100,
            max_snapshot_lines=1000
        )

        try:
            await terminal.initialize()
            logger.info("iTerm terminal controller initialized successfully")
        except Exception as term_error:
            logger.error(f"Failed to initialize iTerm terminal controller: {str(term_error)}")
            raise

        # Initialize layout manager
        logger.info("Initializing layout manager...")
        layout_manager = LayoutManager(terminal)
        logger.info("Layout manager initialized successfully")

        # Initialize agent registry
        logger.info("Initializing agent registry...")
        agent_registry = AgentRegistry()
        logger.info("Agent registry initialized successfully")

        # Set global references for resources
        global _terminal, _logger, _agent_registry
        _terminal = terminal
        _logger = logger
        _agent_registry = agent_registry

        # Yield the initialized components
        yield {
            "connection": connection,
            "terminal": terminal,
            "layout_manager": layout_manager,
            "agent_registry": agent_registry,
            "logger": logger,
            "log_dir": log_dir
        }

    finally:
        # Clean up resources
        logger.info("Shutting down iTerm MCP server...")
        logger.info("iTerm MCP server shutdown completed")


# Create an MCP server
mcp = FastMCP(
    name="iTerm2 Controller",
    instructions="Control iTerm2 terminal sessions with parallel multi-agent orchestration",
    lifespan=iterm_lifespan,
    dependencies=["iterm2", "asyncio", "pydantic"]
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def resolve_session(
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    session_id: Optional[str] = None,
    name: Optional[str] = None,
    agent: Optional[str] = None,
    team: Optional[str] = None
) -> List[ItermSession]:
    """Resolve session identifiers to actual sessions.

    Returns list of sessions matching the criteria.
    If no criteria provided, returns the active session.
    """
    sessions = []

    # If team specified, get all agents in team
    if team:
        team_agents = agent_registry.list_agents(team=team)
        for a in team_agents:
            session = await terminal.get_session_by_id(a.session_id)
            if session:
                sessions.append(session)
        return sessions

    # If agent specified, get that agent's session
    if agent:
        a = agent_registry.get_agent(agent)
        if a:
            session = await terminal.get_session_by_id(a.session_id)
            if session:
                sessions.append(session)
        return sessions

    # If session_id specified
    if session_id:
        session = await terminal.get_session_by_id(session_id)
        if session:
            sessions.append(session)
        return sessions

    # If name specified
    if name:
        session = await terminal.get_session_by_name(name)
        if session:
            sessions.append(session)
        return sessions

    # Default: use active session
    active_session_id = agent_registry.active_session
    if active_session_id:
        session = await terminal.get_session_by_id(active_session_id)
        if session:
            sessions.append(session)

    return sessions


def check_condition(content: str, condition: Optional[str]) -> bool:
    """Check if content matches a regex condition."""
    if not condition:
        return True
    try:
        return bool(re.search(condition, content))
    except re.error:
        return False


def ensure_model(model_cls, payload):
    """Validate or coerce an incoming payload into a Pydantic model."""

    if isinstance(payload, model_cls):
        return payload
    return model_cls.model_validate(payload)


async def resolve_target_sessions(
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    targets: Optional[List[SessionTarget]] = None,
) -> List[ItermSession]:
    """Resolve a list of session targets to unique sessions."""

    if not targets:
        return await resolve_session(terminal, agent_registry)

    sessions: List[ItermSession] = []
    seen = set()

    for target in targets:
        resolved = await resolve_session(
            terminal,
            agent_registry,
            session_id=target.session_id,
            name=target.name,
            agent=target.agent,
            team=target.team,
        )
        for session in resolved:
            if session.id not in seen:
                sessions.append(session)
                seen.add(session.id)

    return sessions


async def execute_create_sessions(
    create_request: CreateSessionsRequest,
    terminal: ItermTerminal,
    layout_manager: LayoutManager,
    agent_registry: AgentRegistry,
    logger: logging.Logger,
) -> CreateSessionsResponse:
    """Create sessions based on a CreateSessionsRequest."""

    try:
        layout_type = LayoutType[create_request.layout.upper()]
    except KeyError as exc:
        raise ValueError(
            f"Invalid layout type: {create_request.layout}. Use one of: {[lt.name for lt in LayoutType]}"
        ) from exc

    pane_names = [cfg.name or f"Session-{idx}" for idx, cfg in enumerate(create_request.sessions)]
    logger.info(f"Creating layout {layout_type.name} with panes: {pane_names}")

    sessions_map = await layout_manager.create_layout(layout_type=layout_type, pane_names=pane_names)
    created: List[CreatedSession] = []

    for pane_name, session_id in sessions_map.items():
        session = await terminal.get_session_by_id(session_id)
        if not session:
            continue

        config = next((cfg for cfg in create_request.sessions if cfg.name == pane_name), None)

        agent_name = None
        if config and config.agent:
            teams = [config.team] if config.team else []
            agent_registry.register_agent(
                name=config.agent,
                session_id=session.id,
                teams=teams,
            )
            agent_name = config.agent

        if config and config.command:
            await session.execute_command(config.command)

        if config and config.monitor:
            await session.start_monitoring(update_interval=0.2)

        created.append(
            CreatedSession(
                session_id=session.id,
                name=session.name,
                agent=agent_name,
                persistent_id=session.persistent_id,
            )
        )

    if created and not agent_registry.active_session:
        agent_registry.active_session = created[0].session_id

    return CreateSessionsResponse(sessions=created, window_id=create_request.window_id or "")


async def execute_write_request(
    write_request: WriteToSessionsRequest,
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    logger: logging.Logger,
) -> WriteToSessionsResponse:
    """Send messages according to WriteToSessionsRequest and return structured results."""

    results: List[WriteResult] = []

    async def send_to_session(session: ItermSession, message: SessionMessage) -> WriteResult:
        result = WriteResult(session_id=session.id, session_name=session.name)

        if message.condition:
            output = await session.get_screen_contents()
            if not check_condition(output, message.condition):
                result.skipped = True
                result.skipped_reason = "condition_not_met"
                return result

        agent = agent_registry.get_agent_by_session(session.id)
        if write_request.skip_duplicates and agent:
            if agent_registry.was_message_sent(message.content, agent.name):
                result.skipped = True
                result.skipped_reason = "duplicate"
                return result

        try:
            if message.execute:
                await session.execute_command(message.content)
            else:
                await session.send_text(message.content, execute=False)

            if agent:
                agent_registry.record_message_sent(message.content, [agent.name])
            result.success = True
        except Exception as exc:
            result.error = str(exc)

        return result

    tasks: List[Any] = []

    for message in write_request.messages:
        sessions = await resolve_target_sessions(terminal, agent_registry, message.targets)
        if not sessions:
            results.append(
                WriteResult(
                    session_id="",
                    session_name=None,
                    skipped=True,
                    skipped_reason="no_match",
                )
            )
            continue

        for session in sessions:
            if write_request.parallel:
                tasks.append(send_to_session(session, message))
            else:
                results.append(await send_to_session(session, message))

    if write_request.parallel and tasks:
        for response in await asyncio.gather(*tasks):
            results.append(response)

    sent_count = sum(1 for r in results if r.success)
    skipped_count = sum(1 for r in results if r.skipped)
    error_count = sum(1 for r in results if not r.success and not r.skipped)

    logger.info(f"Delivered {sent_count}/{len(results)} messages (skipped={skipped_count}, errors={error_count})")

    return WriteToSessionsResponse(
        results=results,
        sent_count=sent_count,
        skipped_count=skipped_count,
        error_count=error_count,
    )


async def execute_read_request(
    read_request: ReadSessionsRequest,
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    logger: logging.Logger,
) -> ReadSessionsResponse:
    """Read outputs according to ReadSessionsRequest."""

    outputs: List[SessionOutput] = []

    async def read_from_session(session: ItermSession, max_lines: Optional[int]) -> SessionOutput:
        content = await session.get_screen_contents(max_lines=max_lines)

        if read_request.filter_pattern:
            try:
                pattern = re.compile(read_request.filter_pattern)
                lines = content.split("\n")
                filtered = [line for line in lines if pattern.search(line)]
                content = "\n".join(filtered)
            except re.error as regex_err:
                logger.error(f"Invalid filter_pattern '{read_request.filter_pattern}': {regex_err}")

        agent = agent_registry.get_agent_by_session(session.id)
        line_count = len(content.split("\n")) if content else 0
        truncated = bool(max_lines and line_count >= max_lines)

        return SessionOutput(
            session_id=session.id,
            name=session.name,
            agent=agent.name if agent else None,
            content=content,
            line_count=line_count,
            truncated=truncated,
        )

    tasks: List[Any] = []

    targets = read_request.targets or [ReadTarget()]
    for target in targets:
        sessions = await resolve_target_sessions(
            terminal,
            agent_registry,
            [
                SessionTarget(
                    session_id=target.session_id,
                    name=target.name,
                    agent=target.agent,
                    team=target.team,
                )
            ] if any([target.session_id, target.name, target.agent, target.team]) else None,
        )

        for session in sessions:
            if read_request.parallel:
                tasks.append(read_from_session(session, target.max_lines))
            else:
                outputs.append(await read_from_session(session, target.max_lines))

    if read_request.parallel and tasks:
        outputs.extend(await asyncio.gather(*tasks))

    logger.info(f"Read output from {len(outputs)} sessions")
    return ReadSessionsResponse(outputs=outputs, total_sessions=len(outputs))


async def execute_cascade_request(
    cascade_request: CascadeMessageRequest,
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    logger: logging.Logger,
) -> CascadeMessageResponse:
    """Execute a cascade delivery and return structured results."""

    cascade = CascadingMessage(
        broadcast=cascade_request.broadcast,
        teams=cascade_request.teams,
        agents=cascade_request.agents,
    )

    message_targets = agent_registry.resolve_cascade_targets(cascade)
    results: List[CascadeResult] = []
    delivered = 0
    skipped = 0

    for message, agent_names in message_targets.items():
        if cascade_request.skip_duplicates:
            agent_names = agent_registry.filter_unsent_recipients(message, agent_names)

        delivered_agents = []
        for agent_name in agent_names:
            agent = agent_registry.get_agent(agent_name)
            if not agent:
                continue

            session = await terminal.get_session_by_id(agent.session_id)
            if not session:
                results.append(
                    CascadeResult(
                        agent=agent_name,
                        session_id="",
                        message_type="unknown",
                        delivered=False,
                        skipped_reason="session_not_found",
                    )
                )
                skipped += 1
                continue

            message_type = "broadcast"
            if cascade_request.agents.get(agent_name, None) == message:
                message_type = "agent"
            elif any(agent.is_member_of(team) and cascade_request.teams.get(team) == message for team in cascade_request.teams):
                message_type = "team"

            if cascade_request.execute:
                await session.execute_command(message)
            else:
                await session.send_text(message, execute=False)

            results.append(
                CascadeResult(
                    agent=agent_name,
                    session_id=session.id,
                    message_type=message_type,
                    delivered=True,
                )
            )
            delivered_agents.append(agent_name)
            delivered += 1

        if delivered_agents:
            agent_registry.record_message_sent(message, delivered_agents)

    logger.info(f"Cascade: delivered={delivered}, skipped={skipped}")
    return CascadeMessageResponse(results=results, delivered_count=delivered, skipped_count=skipped)


# ============================================================================
# SESSION MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def list_sessions(ctx: Context) -> str:
    """List all available terminal sessions with agent info."""
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    logger.info("Listing all active sessions")
    sessions = list(terminal.sessions.values())
    result = []

    for session in sessions:
        agent = agent_registry.get_agent_by_session(session.id)
        result.append({
            "id": session.id,
            "name": session.name,
            "persistent_id": session.persistent_id,
            "agent": agent.name if agent else None,
            "teams": agent.teams if agent else []
        })

    logger.info(f"Found {len(result)} active sessions")
    return json.dumps(result, indent=2)


@mcp.tool()
async def set_active_session(request: SetActiveSessionRequest, ctx: Context) -> str:
    """Set the active session for subsequent operations."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        req = ensure_model(SetActiveSessionRequest, request)
        sessions = await resolve_session(
            terminal,
            agent_registry,
            session_id=req.session_id,
            name=req.name,
            agent=req.agent,
        )
        if not sessions:
            return "No matching session found"

        session = sessions[0]
        agent_registry.active_session = session.id
        logger.info(f"Set active session to: {session.name} ({session.id})")
        return f"Active session set to: {session.name} ({session.id})"
    except Exception as e:
        logger.error(f"Error setting active session: {e}")
        return f"Error: {e}"


@mcp.tool()
async def focus_session(request: SetActiveSessionRequest, ctx: Context) -> str:
    """Focus on a specific terminal session."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        req = ensure_model(SetActiveSessionRequest, request)
        sessions = await resolve_session(
            terminal,
            agent_registry,
            session_id=req.session_id,
            name=req.name,
            agent=req.agent,
        )
        if not sessions:
            return "No matching session found"

        session = sessions[0]
        await terminal.focus_session(session.id)
        logger.info(f"Focused on session: {session.name}")
        return f"Focused on session: {session.name} ({session.id})"
    except Exception as e:
        logger.error(f"Error focusing session: {e}")
        return f"Error: {e}"


@mcp.tool()
async def create_sessions(request: CreateSessionsRequest, ctx: Context) -> str:
    """Create new terminal sessions with optional agent registration."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    layout_manager = ctx.request_context.lifespan_context["layout_manager"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        create_request = ensure_model(CreateSessionsRequest, request)
        result = await execute_create_sessions(create_request, terminal, layout_manager, agent_registry, logger)
        logger.info(f"Created {len(result.sessions)} sessions")
        return result.model_dump_json(indent=2)
    except Exception as e:
        logger.error(f"Error creating sessions: {e}")
        return f"Error: {e}"


# ============================================================================
# COMMAND EXECUTION TOOLS (Array-based)
# ============================================================================

@mcp.tool()
async def write_to_sessions(request: WriteToSessionsRequest, ctx: Context) -> str:
    """Write messages to one or more sessions using the gRPC-aligned schema."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        write_request = ensure_model(WriteToSessionsRequest, request)
        result = await execute_write_request(write_request, terminal, agent_registry, logger)
        return result.model_dump_json(indent=2)
    except Exception as e:
        logger.error(f"Error in write_to_sessions: {e}")
        return f"Error: {e}"


@mcp.tool()
async def read_sessions(request: ReadSessionsRequest, ctx: Context) -> str:
    """Read output from one or more sessions."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        read_request = ensure_model(ReadSessionsRequest, request)
        result = await execute_read_request(read_request, terminal, agent_registry, logger)
        return result.model_dump_json(indent=2)
    except Exception as e:
        logger.error(f"Error in read_sessions: {e}")
        return f"Error: {e}"


@mcp.tool()
async def send_cascade_message(request: CascadeMessageRequest, ctx: Context) -> str:
    """Send cascading messages to agents/teams."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        cascade_request = ensure_model(CascadeMessageRequest, request)
        result = await execute_cascade_request(cascade_request, terminal, agent_registry, logger)
        return result.model_dump_json(indent=2)
    except Exception as e:
        logger.error(f"Error in send_cascade_message: {e}")
        return f"Error: {e}"


# ============================================================================
# ORCHESTRATION TOOLS
# ============================================================================

@mcp.tool()
async def orchestrate_playbook(request: OrchestrateRequest, ctx: Context) -> str:
    """Execute a high-level playbook (layout + commands + cascade + reads)."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    layout_manager = ctx.request_context.lifespan_context["layout_manager"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        orchestration_request = ensure_model(OrchestrateRequest, request)
        playbook = orchestration_request.playbook

        response = OrchestrateResponse()

        if playbook.layout:
            response.layout = await execute_create_sessions(playbook.layout, terminal, layout_manager, agent_registry, logger)

        command_results: List[PlaybookCommandResult] = []
        for command in playbook.commands:
            write_request = WriteToSessionsRequest(
                messages=command.messages,
                parallel=command.parallel,
                skip_duplicates=command.skip_duplicates,
            )
            write_result = await execute_write_request(write_request, terminal, agent_registry, logger)
            command_results.append(PlaybookCommandResult(name=command.name, write_result=write_result))

        response.commands = command_results

        if playbook.cascade:
            response.cascade = await execute_cascade_request(playbook.cascade, terminal, agent_registry, logger)

        if playbook.reads:
            response.reads = await execute_read_request(playbook.reads, terminal, agent_registry, logger)

        logger.info(
            "Playbook completed: layout=%s, commands=%s, cascade=%s, reads=%s",
            bool(response.layout),
            len(response.commands),
            bool(response.cascade),
            bool(response.reads),
        )

        return response.model_dump_json(indent=2, exclude_none=True)
    except Exception as e:
        logger.error(f"Error orchestrating playbook: {e}")
        return f"Error: {e}"


# ============================================================================
# CONTROL & STATUS TOOLS
# ============================================================================

@mcp.tool()
async def send_control_character(control_char: str, target: SessionTarget, ctx: Context) -> str:
    """Send a control character to session(s)."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        target_model = ensure_model(SessionTarget, target)
        sessions = await resolve_target_sessions(terminal, agent_registry, [target_model])
        if not sessions:
            return "No matching sessions found"

        results = []
        for session in sessions:
            await session.send_control_character(control_char)
            results.append(f"{session.name}: Ctrl+{control_char.upper()} sent")

        logger.info(f"Sent Ctrl+{control_char.upper()} to {len(sessions)} sessions")
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Error sending control character: {e}")
        return f"Error: {e}"


@mcp.tool()
async def send_special_key(
    key: str,
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Send a special key to a session.

    Args:
        key: Special key ('enter', 'tab', 'escape', 'up', 'down', etc.)
        session_id: Target session ID (optional)
        agent: Target agent name (optional)
        name: Target session name (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent)
        if not sessions:
            return "No matching session found"

        session = sessions[0]
        await session.send_special_key(key)
        logger.info(f"Sent '{key}' to session: {session.name}")
        return f"Special key '{key}' sent to session: {session.name}"
    except Exception as e:
        logger.error(f"Error sending special key: {e}")
        return f"Error: {e}"


@mcp.tool()
async def check_session_status(request: SetActiveSessionRequest, ctx: Context) -> str:
    """Check status of a session."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        req = ensure_model(SetActiveSessionRequest, request)
        sessions = await resolve_session(
            terminal,
            agent_registry,
            session_id=req.session_id,
            name=req.name,
            agent=req.agent,
        )
        if not sessions:
            return "No matching session found"

        session = sessions[0]
        agent_obj = agent_registry.get_agent_by_session(session.id)

        status = {
            "name": session.name,
            "id": session.id,
            "persistent_id": session.persistent_id,
            "agent": agent_obj.name if agent_obj else None,
            "teams": agent_obj.teams if agent_obj else [],
            "is_processing": getattr(session, "is_processing", False),
            "is_monitoring": getattr(session, "is_monitoring", False),
            "is_active": session.id == agent_registry.active_session
        }

        logger.info(f"Status for session: {session.name}")
        return json.dumps(status, indent=2)
    except Exception as e:
        logger.error(f"Error checking session status: {e}")
        return f"Error: {e}"


# ============================================================================
# AGENT & TEAM MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
async def register_agent(request: RegisterAgentRequest, ctx: Context) -> str:
    """Register an agent for a session."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        req = ensure_model(RegisterAgentRequest, request)
        session = await terminal.get_session_by_id(req.session_id)
        if not session:
            return "No matching session found. Provide a valid session_id."

        agent = agent_registry.register_agent(
            name=req.name,
            session_id=session.id,
            teams=req.teams,
            metadata=req.metadata,
        )

        logger.info(f"Registered agent '{agent.name}' for session {session.name}")

        return json.dumps({
            "agent": agent.name,
            "session_id": agent.session_id,
            "session_name": session.name,
            "teams": agent.teams,
            "metadata": agent.metadata,
        }, indent=2)
    except Exception as e:
        logger.error(f"Error registering agent: {e}")
        return f"Error: {e}"


@mcp.tool()
async def list_agents(ctx: Context, team: Optional[str] = None) -> str:
    """List all registered agents.

    Args:
        team: Filter by team name (optional)
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        agents = agent_registry.list_agents(team=team)
        result = [
            {
                "name": a.name,
                "session_id": a.session_id,
                "teams": a.teams
            }
            for a in agents
        ]

        logger.info(f"Listed {len(result)} agents" + (f" in team '{team}'" if team else ""))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return f"Error: {e}"


@mcp.tool()
async def remove_agent(
    agent_name: str,
    ctx: Context
) -> str:
    """Remove an agent registration.

    Args:
        agent_name: Name of the agent to remove
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        if agent_registry.remove_agent(agent_name):
            logger.info(f"Removed agent '{agent_name}'")
            return f"Agent '{agent_name}' removed successfully"
        else:
            return f"Agent '{agent_name}' not found"
    except Exception as e:
        logger.error(f"Error removing agent: {e}")
        return f"Error: {e}"


@mcp.tool()
async def create_team(request: CreateTeamRequest, ctx: Context) -> str:
    """Create a new team."""

    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        req = ensure_model(CreateTeamRequest, request)
        team = agent_registry.create_team(
            name=req.name,
            description=req.description,
            parent_team=req.parent_team,
        )

        logger.info(f"Created team '{team.name}'")

        return json.dumps({
            "name": team.name,
            "description": team.description,
            "parent_team": team.parent_team
        }, indent=2)
    except Exception as e:
        logger.error(f"Error creating team: {e}")
        return f"Error: {e}"


@mcp.tool()
async def list_teams(ctx: Context) -> str:
    """List all teams."""
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        teams = agent_registry.list_teams()
        result = [
            {
                "name": t.name,
                "description": t.description,
                "parent_team": t.parent_team,
                "member_count": len(agent_registry.list_agents(team=t.name))
            }
            for t in teams
        ]

        logger.info(f"Listed {len(result)} teams")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return f"Error: {e}"


@mcp.tool()
async def remove_team(
    team_name: str,
    ctx: Context
) -> str:
    """Remove a team.

    Args:
        team_name: Name of the team to remove
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        if agent_registry.remove_team(team_name):
            logger.info(f"Removed team '{team_name}'")
            return f"Team '{team_name}' removed successfully"
        else:
            return f"Team '{team_name}' not found"
    except Exception as e:
        logger.error(f"Error removing team: {e}")
        return f"Error: {e}"


@mcp.tool()
async def assign_agent_to_team(
    agent_name: str,
    team_name: str,
    ctx: Context
) -> str:
    """Add an agent to a team.

    Args:
        agent_name: Agent name
        team_name: Team name
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        if agent_registry.assign_to_team(agent_name, team_name):
            logger.info(f"Added agent '{agent_name}' to team '{team_name}'")
            return f"Agent '{agent_name}' added to team '{team_name}'"
        else:
            return f"Failed to add agent to team (agent not found or already member)"
    except Exception as e:
        logger.error(f"Error assigning agent to team: {e}")
        return f"Error: {e}"


@mcp.tool()
async def remove_agent_from_team(
    agent_name: str,
    team_name: str,
    ctx: Context
) -> str:
    """Remove an agent from a team.

    Args:
        agent_name: Agent name
        team_name: Team name
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        if agent_registry.remove_from_team(agent_name, team_name):
            logger.info(f"Removed agent '{agent_name}' from team '{team_name}'")
            return f"Agent '{agent_name}' removed from team '{team_name}'"
        else:
            return f"Failed to remove agent from team (agent not found or not a member)"
    except Exception as e:
        logger.error(f"Error removing agent from team: {e}")
        return f"Error: {e}"


# ============================================================================
# MONITORING TOOLS
# ============================================================================

@mcp.tool()
async def start_monitoring_session(
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Start real-time monitoring for a session.

    Args:
        session_id: Target session ID (optional)
        agent: Target agent name (optional)
        name: Target session name (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent)
        if not sessions:
            return "No matching session found"

        session = sessions[0]

        if session.is_monitoring:
            return f"Session {session.name} is already being monitored"

        await session.start_monitoring(update_interval=0.2)
        await asyncio.sleep(2)

        if session.is_monitoring:
            logger.info(f"Started monitoring for session: {session.name}")
            return f"Started monitoring for session: {session.name}"
        else:
            return f"Failed to start monitoring for session: {session.name}"
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        return f"Error: {e}"


@mcp.tool()
async def stop_monitoring_session(
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Stop monitoring for a session.

    Args:
        session_id: Target session ID (optional)
        agent: Target agent name (optional)
        name: Target session name (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent)
        if not sessions:
            return "No matching session found"

        session = sessions[0]

        if not session.is_monitoring:
            return f"Session {session.name} is not being monitored"

        await session.stop_monitoring()
        logger.info(f"Stopped monitoring for session: {session.name}")
        return f"Stopped monitoring for session: {session.name}"
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        return f"Error: {e}"


# ============================================================================
# RESOURCES
# ============================================================================

@mcp.resource("terminal://{session_id}/output")
async def get_terminal_output(session_id: str) -> str:
    """Get output from a terminal session."""
    if _terminal is None or _logger is None:
        raise RuntimeError("Server not initialized. Please wait for initialization to complete.")

    terminal = _terminal
    logger = _logger

    try:
        session = await terminal.get_session_by_id(session_id)
        if not session:
            return f"No session found with ID: {session_id}"

        output = await session.get_screen_contents()
        return output
    except Exception as e:
        logger.error(f"Error getting terminal output: {e}")
        return f"Error: {e}"


@mcp.resource("terminal://{session_id}/info")
async def get_terminal_info(session_id: str) -> str:
    """Get information about a terminal session."""
    if _terminal is None or _logger is None:
        raise RuntimeError("Server not initialized. Please wait for initialization to complete.")

    terminal = _terminal
    agent_registry = _agent_registry
    logger = _logger

    try:
        session = await terminal.get_session_by_id(session_id)
        if not session:
            return f"No session found with ID: {session_id}"

        agent = agent_registry.get_agent_by_session(session.id)

        info = {
            "name": session.name,
            "id": session.id,
            "persistent_id": session.persistent_id,
            "agent": agent.name if agent else None,
            "teams": agent.teams if agent else [],
            "is_processing": getattr(session, "is_processing", False),
            "is_monitoring": getattr(session, "is_monitoring", False),
            "max_lines": session.max_lines
        }

        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error(f"Error getting terminal info: {e}")
        return f"Error: {e}"


@mcp.resource("terminal://sessions")
async def list_all_sessions_resource() -> str:
    """Get a list of all terminal sessions."""
    if _terminal is None or _logger is None:
        raise RuntimeError("Server not initialized. Please wait for initialization to complete.")

    terminal = _terminal
    agent_registry = _agent_registry
    logger = _logger

    try:
        sessions = list(terminal.sessions.values())
        result = []

        for session in sessions:
            agent = agent_registry.get_agent_by_session(session.id)
            result.append({
                "id": session.id,
                "name": session.name,
                "persistent_id": session.persistent_id,
                "agent": agent.name if agent else None,
                "teams": agent.teams if agent else [],
                "is_processing": getattr(session, "is_processing", False),
                "is_monitoring": getattr(session, "is_monitoring", False)
            })

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return f"Error: {e}"


@mcp.resource("agents://all")
async def list_all_agents_resource() -> str:
    """Get a list of all registered agents."""
    agent_registry = _agent_registry
    logger = _logger

    try:
        agents = agent_registry.list_agents()
        result = [
            {
                "name": a.name,
                "session_id": a.session_id,
                "teams": a.teams
            }
            for a in agents
        ]
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return f"Error: {e}"


@mcp.resource("teams://all")
async def list_all_teams_resource() -> str:
    """Get a list of all teams."""
    agent_registry = _agent_registry
    logger = _logger

    try:
        teams = agent_registry.list_teams()
        result = [
            {
                "name": t.name,
                "description": t.description,
                "parent_team": t.parent_team,
                "member_count": len(agent_registry.list_agents(team=t.name))
            }
            for t in teams
        ]
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return f"Error: {e}"


# ============================================================================
# PROMPTS
# ============================================================================

@mcp.prompt("orchestrate_agents")
def orchestrate_agents_prompt(task: str) -> str:
    """Prompt for orchestrating multiple agents.

    Args:
        task: The task to orchestrate
    """
    return f"""
You're orchestrating multiple Claude agents through iTerm2 sessions.

Task: {task}

Use the following tools to coordinate:
- create_sessions: Create new sessions with agents
- write_to_sessions: Send commands to multiple sessions
- read_sessions: Read output from sessions
- send_cascade_message: Send hierarchical messages to teams/agents

Remember:
- Use teams for logical groupings
- Cascade messages from broad to specific
- Check for duplicates to avoid redundant work
"""


@mcp.prompt("monitor_team")
def monitor_team_prompt(team_name: str) -> str:
    """Prompt for monitoring a team of agents.

    Args:
        team_name: The team to monitor
    """
    return f"""
You're monitoring the '{team_name}' team of agents.

Use read_sessions with team='{team_name}' to check all members.
Watch for:
- Error messages
- Completion signals
- Progress indicators

Coordinate responses as needed using write_to_sessions or send_cascade_message.
"""


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the MCP server."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        if os.environ.get("ITERM_MCP_CLEAN_EXIT"):
            return
        print("\nServer stopped by user", file=sys.stderr)
        os._exit(0)
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
