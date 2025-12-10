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
from typing import AsyncIterator, Dict, List, Optional, Union, Any

import iterm2
from mcp.server.fastmcp import FastMCP, Context

from core.layouts import LayoutManager, LayoutType
from core.session import ItermSession
from core.terminal import ItermTerminal
from core.agents import AgentRegistry, CascadingMessage, SendTarget

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

    # If team specified, get all agents in team (optionally filtered by agent)
    if team:
        team_agents = agent_registry.list_agents(team=team)

        if agent:
            team_agents = [a for a in team_agents if a.name == agent]
            if not team_agents:
                return []

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
async def set_active_session(
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Set the active session for subsequent operations.

    Args:
        session_id: Direct session ID
        agent: Agent name
        name: Session name
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent)
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
async def focus_session(
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Focus on a specific terminal session.

    Args:
        session_id: Direct session ID
        agent: Agent name
        name: Session name
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent)
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
async def create_sessions(
    layout_type: str,
    ctx: Context,
    session_configs: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Create new terminal sessions with optional agent registration.

    Args:
        layout_type: Layout type (single, horizontal, vertical, quad)
        session_configs: Optional list of session configurations:
            - name: Session name (required)
            - agent: Agent name to register (optional)
            - team: Team to assign agent to (optional)
            - command: Initial command to run (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    layout_manager = ctx.request_context.lifespan_context["layout_manager"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        # Convert layout type
        layout_map = {
            "single": LayoutType.SINGLE,
            "horizontal": LayoutType.HORIZONTAL_SPLIT,
            "vertical": LayoutType.VERTICAL_SPLIT,
            "quad": LayoutType.QUAD
        }
        layout_type_enum = layout_map.get(layout_type.lower())
        if not layout_type_enum:
            return f"Invalid layout type: {layout_type}. Use: single, horizontal, vertical, quad"

        # Extract session names from configs
        session_names = None
        pane_hierarchy = None
        if session_configs:
            session_names = [c.get("name") for c in session_configs]
            pane_hierarchy = [
                {
                    "name": c.get("name"),
                    "team": c.get("team") or (c.get("team_path")[-1] if c.get("team_path") and len(c.get("team_path")) > 0 else None),
                    "agent": c.get("agent"),
                    "team_path": c.get("team_path"),
                }
                for c in session_configs
            ]

        # Create the layout
        logger.info(f"Creating {layout_type} layout with sessions: {session_names}")
        sessions_map = await layout_manager.create_layout(
            layout_type=layout_type_enum,
            pane_names=session_names,
            pane_hierarchy=pane_hierarchy,
        )

        result = []

        created_items = list(sessions_map.items())

        # Process each created session
        for idx, (session_name, session_id) in enumerate(created_items):
            session = await terminal.get_session_by_id(session_id)
            if not session:
                continue

            session_info = {
                "session_id": session.id,
                "name": session.name,
                "persistent_id": session.persistent_id,
                "agent": None,
                "team": None
            }

            # Find matching config (preserve ordering fallback)
            if session_configs:
                config = session_configs[idx] if idx < len(session_configs) else {}
                if config:
                    # Register agent if specified
                    agent_name = config.get("agent")
                    team_name = config.get("team") or (config.get("team_path")[-1] if config.get("team_path") else None)

                    # Materialize team hierarchy (parent chain) if provided
                    team_path = config.get("team_path") or ([] if not team_name else [team_name])
                    parent_team = None
                    for t_name in team_path:
                        if t_name and not agent_registry.get_team(t_name):
                            agent_registry.create_team(name=t_name, parent_team=parent_team)
                        parent_team = t_name

                    if agent_name:
                        teams = [team_name] if team_name else []
                        agent_registry.register_agent(
                            name=agent_name,
                            session_id=session.id,
                            teams=teams
                        )
                        session_info["agent"] = agent_name
                        session_info["team"] = team_name

                    # Execute initial command
                    command = config.get("command")
                    if command:
                        await session.execute_command(command)

            result.append(session_info)

        # Set first session as active if none set
        if result and not agent_registry.active_session:
            agent_registry.active_session = result[0]["session_id"]

        logger.info(f"Created {len(result)} sessions")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error creating sessions: {e}")
        return f"Error: {e}"


# ============================================================================
# COMMAND EXECUTION TOOLS (Array-based)
# ============================================================================

@mcp.tool()
async def write_to_sessions(
    messages: List[Dict[str, Any]],
    ctx: Context,
    parallel: bool = True,
    skip_duplicates: bool = True
) -> str:
    """Write messages to one or more sessions.

    Args:
        messages: List of message objects:
            - content: Text to send (required)
            - session_id: Target session ID (optional)
            - name: Target session name (optional)
            - agent: Target agent name (optional)
            - team: Target team (sends to all members) (optional)
            - condition: Regex pattern - only send if session output matches (optional)
            - execute: Whether to press Enter (default: true)
        parallel: Execute sends in parallel (default: true)
        skip_duplicates: Skip if message already sent to target (default: true)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    results = []

    async def send_to_session(session: ItermSession, content: str, execute: bool, condition: Optional[str]) -> Dict:
        """Send message to a single session."""
        result = {
            "session_id": session.id,
            "name": session.name,
            "delivered": False,
            "skipped_reason": None
        }

        # Check condition if specified
        if condition:
            output = await session.get_screen_contents()
            if not check_condition(output, condition):
                result["skipped_reason"] = "condition_not_met"
                return result

        # Check for duplicates
        agent = agent_registry.get_agent_by_session(session.id)
        if skip_duplicates and agent:
            if agent_registry.was_message_sent(content, agent.name):
                result["skipped_reason"] = "duplicate"
                return result

        # Send the message
        if execute:
            await session.execute_command(content)
        else:
            await session.send_text(content, execute=False)

        # Record message sent
        if agent:
            agent_registry.record_message_sent(content, [agent.name])

        result["delivered"] = True
        return result

    try:
        tasks = []

        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue

            execute = msg.get("execute", True)
            condition = msg.get("condition")

            # Resolve target sessions
            sessions = await resolve_session(
                terminal, agent_registry,
                session_id=msg.get("session_id"),
                name=msg.get("name"),
                agent=msg.get("agent"),
                team=msg.get("team")
            )

            if not sessions:
                results.append({
                    "content": content[:50],
                    "error": "No matching sessions found"
                })
                continue

            # Create tasks for each session
            for session in sessions:
                if parallel:
                    tasks.append(send_to_session(session, content, execute, condition))
                else:
                    result = await send_to_session(session, content, execute, condition)
                    results.append(result)

        # Execute parallel tasks
        if parallel and tasks:
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in parallel_results:
                if isinstance(r, Exception):
                    results.append({"error": str(r)})
                else:
                    results.append(r)

        delivered = sum(1 for r in results if r.get("delivered"))
        logger.info(f"Delivered {delivered}/{len(results)} messages")

        return json.dumps({
            "results": results,
            "delivered_count": delivered,
            "total_count": len(results)
        }, indent=2)
    except Exception as e:
        logger.error(f"Error in write_to_sessions: {e}")
        return f"Error: {e}"


@mcp.tool()
async def read_sessions(
    ctx: Context,
    targets: Optional[List[Dict[str, Any]]] = None,
    parallel: bool = True,
    filter_pattern: Optional[str] = None
) -> str:
    """Read output from one or more sessions.

    Args:
        targets: List of target specifications (optional, uses active session if empty):
            - session_id: Direct session ID (optional)
            - name: Session name (optional)
            - agent: Agent name (optional)
            - team: Team name (reads all members) (optional)
            - max_lines: Override default max lines (optional)
        parallel: Read sessions in parallel (default: true)
        filter_pattern: Regex pattern to filter output lines (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    results = []

    async def read_from_session(session: ItermSession, max_lines: Optional[int]) -> Dict:
        """Read output from a single session."""
        output = await session.get_screen_contents(max_lines=max_lines)

        # Apply filter if specified
        if filter_pattern:
            try:
                pattern = re.compile(filter_pattern)
                lines = output.split("\n")
                filtered_lines = [l for l in lines if pattern.search(l)]
                output = "\n".join(filtered_lines)
            except re.error as regex_err:
                logger.error(f"Invalid filter_pattern '{filter_pattern}': {regex_err}")

        agent = agent_registry.get_agent_by_session(session.id)

        return {
            "session_id": session.id,
            "name": session.name,
            "agent": agent.name if agent else None,
            "content": output,
            "line_count": len(output.split("\n"))
        }

    try:
        # If no targets, use active session
        if not targets:
            targets = [{}]

        tasks = []

        for target in targets:
            sessions = await resolve_session(
                terminal, agent_registry,
                session_id=target.get("session_id"),
                name=target.get("name"),
                agent=target.get("agent"),
                team=target.get("team")
            )

            max_lines = target.get("max_lines")

            for session in sessions:
                if parallel:
                    tasks.append(read_from_session(session, max_lines))
                else:
                    result = await read_from_session(session, max_lines)
                    results.append(result)

        # Execute parallel tasks
        if parallel and tasks:
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in parallel_results:
                if isinstance(r, Exception):
                    results.append({"error": str(r)})
                else:
                    results.append(r)

        logger.info(f"Read output from {len(results)} sessions")

        return json.dumps({
            "outputs": results,
            "total_sessions": len(results)
        }, indent=2)
    except Exception as e:
        logger.error(f"Error in read_sessions: {e}")
        return f"Error: {e}"


async def _deliver_cascade(
    terminal: ItermTerminal,
    agent_registry: AgentRegistry,
    cascade: CascadingMessage,
    skip_duplicates: bool,
    execute: bool,
    logger: logging.Logger,
) -> str:
    """Send a cascading message and return serialized results."""

    try:
        message_targets = agent_registry.resolve_cascade_targets(cascade)

        results = []
        delivered = 0
        skipped = 0

        for message, agent_names in message_targets.items():
            if skip_duplicates:
                agent_names = agent_registry.filter_unsent_recipients(message, agent_names)

            actually_delivered = []

            for agent_name in agent_names:
                agent = agent_registry.get_agent(agent_name)
                if not agent:
                    continue

                session = await terminal.get_session_by_id(agent.session_id)
                if not session:
                    results.append({
                        "agent": agent_name,
                        "delivered": False,
                        "skipped_reason": "session_not_found"
                    })
                    skipped += 1
                    continue

                await session.send_text(message, execute=execute)
                agent_registry.record_message_sent(message, [agent_name])
                delivered += 1
                actually_delivered.append(agent_name)

            if not actually_delivered:
                skipped += len(agent_names)

            results.append({
                "message": message,
                "targets": agent_names,
                "delivered": actually_delivered
            })

        logger.info(f"Delivered {delivered} cascading messages ({skipped} skipped)")

        return json.dumps({
            "results": results,
            "delivered": delivered,
            "skipped": skipped
        }, indent=2)
    except Exception as e:
        logger.error(f"Error sending cascading message: {e}")
        return f"Error: {e}"


@mcp.tool()
async def send_cascade_message(
    ctx: Context,
    broadcast: Optional[str] = None,
    teams: Optional[Dict[str, str]] = None,
    agents: Optional[Dict[str, str]] = None,
    skip_duplicates: bool = True,
    execute: bool = True
) -> str:
    """Send cascading messages to agents/teams.

    Messages cascade with increasing specificity:
    1. Broadcast goes to ALL agents
    2. Team messages override broadcast for team members
    3. Agent messages override both for specific agents

    Args:
        broadcast: Message sent to ALL agents (optional)
        teams: Team-specific messages {team_name: message} (optional)
        agents: Agent-specific messages {agent_name: message} (optional)
        skip_duplicates: Skip if message already sent (default: true)
        execute: Press Enter after sending (default: true)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    cascade = CascadingMessage(
        broadcast=broadcast,
        teams=teams or {},
        agents=agents or {}
    )

    return await _deliver_cascade(
        terminal=terminal,
        agent_registry=agent_registry,
        cascade=cascade,
        skip_duplicates=skip_duplicates,
        execute=execute,
        logger=logger,
    )


@mcp.tool()
async def select_panes_by_hierarchy(
    ctx: Context,
    targets: List[Dict[str, Optional[str]]],
    set_active: bool = True,
) -> str:
    """Resolve panes by team/agent hierarchy and optionally focus the first.

    Args:
        targets: List of target dicts using SendTarget fields (team/agent)
        set_active: Whether to set the first resolved session as active
    """

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    results = []
    resolved_sessions = []

    for target in targets:
        send_target = SendTarget(**target)
        team = send_target.team
        agent_name = send_target.agent

        if agent_name:
            agent = agent_registry.get_agent(agent_name)
            if not agent:
                results.append({"agent": agent_name, "team": team, "error": "unknown_agent"})
                continue

            if team and not agent.is_member_of(team):
                results.append({"agent": agent_name, "team": team, "error": "agent_not_in_team"})
                continue

            session = await terminal.get_session_by_id(agent.session_id)
            if not session:
                results.append({"agent": agent_name, "team": team, "error": "session_not_found"})
                continue

            resolved_sessions.append(session)
            results.append({
                "agent": agent_name,
                "team": team,
                "session_id": session.id,
                "session_name": session.name
            })
            continue

        if team:
            team_agents = agent_registry.list_agents(team=team)
            if not team_agents:
                results.append({"team": team, "error": "team_has_no_agents"})
                continue

            for agent in team_agents:
                session = await terminal.get_session_by_id(agent.session_id)
                if session:
                    resolved_sessions.append(session)
                    results.append({
                        "agent": agent.name,
                        "team": team,
                        "session_id": session.id,
                        "session_name": session.name
                    })

    if set_active and resolved_sessions:
        agent_registry.active_session = resolved_sessions[0].id
        logger.info(f"Active session set via hierarchy: {resolved_sessions[0].name}")

    return json.dumps({
        "resolved": results,
        "active_session": resolved_sessions[0].id if set_active and resolved_sessions else None
    }, indent=2)


@mcp.tool()
async def send_hierarchical_message(
    ctx: Context,
    targets: List[Dict[str, str]],
    broadcast: Optional[str] = None,
    skip_duplicates: bool = True,
    execute: bool = True,
) -> str:
    """Send cascading messages using hierarchical SendTarget specs."""

    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    send_targets = [SendTarget(**t) for t in targets]

    cascade = CascadingMessage(
        broadcast=broadcast,
        teams={},
        agents={},
    )

    for target in send_targets:
        if target.team and target.agent:
            agent_obj = agent_registry.get_agent(target.agent)
            if not agent_obj or not agent_obj.is_member_of(target.team):
                logger.error(f"Agent '{target.agent}' is not a member of team '{target.team}'. Skipping.")
                continue
            cascade.agents[target.agent] = target.message or broadcast or ""
        elif target.agent:
            cascade.agents[target.agent] = target.message or broadcast or ""
        elif target.team:
            cascade.teams[target.team] = target.message or broadcast or ""

    return await _deliver_cascade(
        terminal=terminal,
        agent_registry=agent_registry,
        cascade=cascade,
        skip_duplicates=skip_duplicates,
        execute=execute,
        logger=logger,
    )


# ============================================================================
# CONTROL & STATUS TOOLS
# ============================================================================

@mcp.tool()
async def send_control_character(
    control_char: str,
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None,
    team: Optional[str] = None
) -> str:
    """Send a control character to session(s).

    Args:
        control_char: Control character ('c' for Ctrl+C, 'd' for Ctrl+D, etc.)
        session_id: Target session ID (optional)
        agent: Target agent name (optional)
        name: Target session name (optional)
        team: Target team (sends to all members) (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        sessions = await resolve_session(terminal, agent_registry, session_id, name, agent, team)
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
async def check_session_status(
    ctx: Context,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    name: Optional[str] = None
) -> str:
    """Check status of a session.

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
async def register_agent(
    agent_name: str,
    ctx: Context,
    session_id: Optional[str] = None,
    session_name: Optional[str] = None,
    teams: Optional[List[str]] = None
) -> str:
    """Register an agent for a session.

    Args:
        agent_name: Unique name for the agent
        session_id: Session ID to associate (optional)
        session_name: Session name to associate (optional)
        teams: List of teams to join (optional)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        # Resolve session
        session = None
        if session_id:
            session = await terminal.get_session_by_id(session_id)
        elif session_name:
            session = await terminal.get_session_by_name(session_name)

        if not session:
            return "No matching session found. Provide session_id or session_name."

        # Register agent
        agent = agent_registry.register_agent(
            name=agent_name,
            session_id=session.id,
            teams=teams or []
        )

        logger.info(f"Registered agent '{agent_name}' for session {session.name}")

        return json.dumps({
            "agent": agent.name,
            "session_id": agent.session_id,
            "session_name": session.name,
            "teams": agent.teams
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
async def create_team(
    team_name: str,
    ctx: Context,
    description: str = "",
    parent_team: Optional[str] = None
) -> str:
    """Create a new team.

    Args:
        team_name: Unique team name
        description: Team description (optional)
        parent_team: Parent team for hierarchy (optional)
    """
    agent_registry = ctx.request_context.lifespan_context["agent_registry"]
    logger = ctx.request_context.lifespan_context["logger"]

    try:
        team = agent_registry.create_team(
            name=team_name,
            description=description,
            parent_team=parent_team
        )

        logger.info(f"Created team '{team_name}'")

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
