"""MCP server implementation for iTerm2 controller using the official MCP Python SDK."""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional, Union, Any

import iterm2
from mcp.server.fastmcp import FastMCP, Context, Image

from core.layouts import LayoutManager, LayoutType
from core.session import ItermSession
from core.terminal import ItermTerminal

# Global references for resources (set during lifespan)
_terminal: Optional[ItermTerminal] = None
_logger: Optional[logging.Logger] = None


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

        # Set global references for resources
        global _terminal, _logger
        _terminal = terminal
        _logger = logger

        # Yield the initialized components
        yield {
            "connection": connection,
            "terminal": terminal,
            "layout_manager": layout_manager,
            "logger": logger,
            "log_dir": log_dir
        }
    
    finally:
        # Clean up resources
        logger.info("Shutting down iTerm MCP server...")
        # Note: iTerm2 Connection doesn't have a close method
        # It gets closed automatically when the context manager exits
        # Just log that we're done
        logger.info("iTerm MCP server shutdown completed")


# Create an MCP server
mcp = FastMCP(
    name="iTerm2 Controller",
    instructions="Control iTerm2 terminal sessions, execute commands, and capture outputs",
    lifespan=iterm_lifespan,
    dependencies=["iterm2", "asyncio"]
)


# SESSION MANAGEMENT TOOLS

@mcp.tool()
async def list_sessions(ctx: Context) -> str:
    """List all available terminal sessions."""
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    logger.info("Listing all active sessions")
    sessions = list(terminal.sessions.values())
    result = []
    
    for session in sessions:
        result.append({
            "id": session.id,
            "name": session.name,
            "persistent_id": session.persistent_id
        })
    
    logger.info(f"Found {len(result)} active sessions")
    return json.dumps(result, indent=2)


@mcp.tool()
async def focus_session(session_identifier: str, ctx: Context) -> str:
    """Focus on a specific terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Focusing session: {session_identifier}")
        
        # Try finding by ID
        session = await terminal.get_session_by_id(session_identifier)
        
        # Try finding by name if not found by ID
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
            
        # Try finding by persistent ID if still not found
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            logger.warning(f"No session found with identifier: {session_identifier}")
            return f"No session found with identifier: {session_identifier}"
        
        logger.info(f"Found session: {session.name} (ID: {session.id})")
        
        # Focus the session with proper error handling
        try:
            await terminal.focus_session(session.id)
            logger.info(f"Successfully focused on session: {session.name}")
            return f"Focused on session: {session.name} (ID: {session.id})"
        except Exception as focus_error:
            logger.error(f"Error focusing session: {str(focus_error)}")
            return f"Error focusing session: {str(focus_error)}"
    except Exception as e:
        logger.error(f"Error in focus_session: {str(e)}")
        await ctx.error(f"Error in focus_session: {str(e)}")
        return f"Error in focus_session: {str(e)}"


@mcp.tool()
async def create_layout(
    layout_type: str, 
    ctx: Context,
    session_names: Optional[List[str]] = None
) -> str:
    """Create a new terminal layout with named sessions.
    
    Args:
        layout_type: The layout type (single, horizontal, vertical, quad)
        session_names: Optional list of names for sessions (defaults to generic names)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    layout_manager = ctx.request_context.lifespan_context["layout_manager"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        # Convert layout type string to enum
        layout_type_enum = None
        if layout_type.lower() == "single":
            layout_type_enum = LayoutType.SINGLE
        elif layout_type.lower() == "horizontal":
            layout_type_enum = LayoutType.HORIZONTAL_SPLIT
        elif layout_type.lower() == "vertical":
            layout_type_enum = LayoutType.VERTICAL_SPLIT
        elif layout_type.lower() == "quad":
            layout_type_enum = LayoutType.QUAD
        else:
            error_msg = f"Invalid layout type: {layout_type}. Choose from: single, horizontal, vertical, quad"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Create the layout (pass session_names as pane_names)
        logger.info(f"Creating {layout_type} layout with panes: {session_names}")
        sessions = await layout_manager.create_layout(
            layout_type=layout_type_enum,
            pane_names=session_names
        )
        
        # Return information about created sessions
        result = []
        for session_name, session_id in sessions.items():
            session = await terminal.get_session_by_id(session_id)
            if session:
                result.append({
                    "id": session.id,
                    "name": session.name,
                    "persistent_id": session.persistent_id
                })
        
        logger.info(f"Successfully created layout with {len(result)} panes")
        return json.dumps(result, indent=2)
    except Exception as e:
        error_msg = f"Error creating layout: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


# COMMAND EXECUTION TOOLS

@mcp.tool()
async def write_to_terminal(
    session_identifier: str, 
    command: str,
    ctx: Context,
    wait_for_prompt: bool = False,
    execute: bool = True
) -> str:
    """Write a command to a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
        command: The command to write
        wait_for_prompt: Whether to wait for the command prompt to appear
        execute: Whether to execute the command by sending Enter after it (set to False to just type without executing)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Writing to session: {session_identifier}, command: {command[:20]}..., execute: {execute}")
        
        # Find the session
        session = None
        try:
            session = await terminal.get_session_by_id(session_identifier)
        except Exception as e:
            logger.error(f"Error finding session by ID: {str(e)}")
        
        if not session:
            try:
                session = await terminal.get_session_by_name(session_identifier)
            except Exception as e:
                logger.error(f"Error finding session by name: {str(e)}")
        
        if not session:
            try:
                session = await terminal.get_session_by_persistent_id(session_identifier)
            except Exception as e:
                logger.error(f"Error finding session by persistent ID: {str(e)}")
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Check if session has is_processing attribute
        if not hasattr(session, 'is_processing'):
            logger.warning(f"Session {session.name} does not have is_processing attribute")
            # Add a default attribute
            session.is_processing = False
        
        # Send the command with execute option
        try:
            if execute:
                # Use smart encoding for command execution
                await session.execute_command(command, use_encoding=True)
                logger.info(f"Command executed (with encoding) in session: {session.name}")
            else:
                # Just type the text without executing
                await session.send_text(command, execute=False)
                logger.info(f"Command typed in session: {session.name}")
        except Exception as send_error:
            error_msg = f"Error sending command: {str(send_error)}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Wait for prompt if requested and if we're executing the command
        if wait_for_prompt and execute:
            await ctx.info("Waiting for command to complete...")
            try:
                # Simple prompt detection by waiting and checking if processing is done
                max_wait = 10  # maximum seconds to wait
                for i in range(max_wait * 2):  # Check every 0.5 seconds
                    # Report progress to the client
                    await ctx.report_progress(i, max_wait * 2)
                    
                    await asyncio.sleep(0.5)
                    if hasattr(session, 'is_processing') and not session.is_processing:
                        logger.info(f"Command completed after {i*0.5} seconds")
                        break
                    
                if hasattr(session, 'is_processing') and session.is_processing:
                    logger.warning(f"Command still processing after {max_wait} seconds")
                    await ctx.warning("Command is still running after timeout")
            except Exception as wait_error:
                logger.error(f"Error waiting for prompt: {str(wait_error)}")
                await ctx.error(f"Error waiting for prompt: {str(wait_error)}")
        
        action = "executed" if execute else "typed"
        return f"Command {action} in session: {session.name}"
    except Exception as e:
        error_msg = f"Error in write_to_terminal: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def read_terminal_output(
    session_identifier: str,
    ctx: Context,
    max_lines: Optional[int] = None
) -> str:
    """Read output from a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
        max_lines: Maximum number of lines to read (default: session's max_lines)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Reading output from session: {session_identifier}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Get the screen contents
        output = await session.get_screen_contents(max_lines=max_lines)
        logger.info(f"Read {len(output.splitlines())} lines from session {session.name}")
        return output
    except Exception as e:
        error_msg = f"Error reading terminal output: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def send_control_character(
    session_identifier: str,
    control_char: str,
    ctx: Context
) -> str:
    """Send a control character to a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
        control_char: Control character to send ('c' for Ctrl+C, 'd' for Ctrl+D, etc.)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Sending control character Ctrl+{control_char.upper()} to session: {session_identifier}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Send the control character
        await session.send_control_character(control_char)
        logger.info(f"Control character Ctrl+{control_char.upper()} sent to session: {session.name}")
        return f"Control character Ctrl+{control_char.upper()} sent to session: {session.name}"
    except Exception as e:
        error_msg = f"Error sending control character: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def send_special_key(
    session_identifier: str,
    key: str,
    ctx: Context
) -> str:
    """Send a special key to a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
        key: Special key to send ('enter', 'return', 'tab', 'escape', 'up', 'down', etc.)
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Sending special key '{key}' to session: {session_identifier}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Send the special key
        await session.send_special_key(key)
        logger.info(f"Special key '{key}' sent to session: {session.name}")
        return f"Special key '{key}' sent to session: {session.name}"
    except Exception as e:
        error_msg = f"Error sending special key: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def check_session_status(
    session_identifier: str,
    ctx: Context
) -> str:
    """Check if a session is currently processing a command.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Checking status of session: {session_identifier}")
        
        # Find the session with error handling
        session = None
        try:
            session = await terminal.get_session_by_id(session_identifier)
        except Exception as e:
            logger.error(f"Error finding session by ID: {str(e)}")
        
        if not session:
            try:
                session = await terminal.get_session_by_name(session_identifier)
            except Exception as e:
                logger.error(f"Error finding session by name: {str(e)}")
        
        if not session:
            try:
                session = await terminal.get_session_by_persistent_id(session_identifier)
            except Exception as e:
                logger.error(f"Error finding session by persistent ID: {str(e)}")
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Check for required attributes
        if not hasattr(session, "is_processing"):
            logger.warning(f"Session {session.name} does not have is_processing attribute")
            session.is_processing = False
        
        # Check processing status
        status = {
            "name": session.name,
            "id": session.id,
            "persistent_id": session.persistent_id,
            "is_processing": getattr(session, "is_processing", False),
            "is_monitoring": getattr(session, "is_monitoring", False)
        }
        
        logger.info(f"Session status: {json.dumps(status)}")
        return json.dumps(status, indent=2)
    except Exception as e:
        error_msg = f"Error checking session status: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


# ADVANCED FEATURES

@mcp.tool()
async def get_session_by_persistent_id(
    persistent_id: str,
    ctx: Context
) -> str:
    """Get a session by its persistent ID (useful for reconnection).
    
    Args:
        persistent_id: The persistent ID of the session
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Getting session by persistent ID: {persistent_id}")
        
        # Find the session by persistent ID
        session = await terminal.get_session_by_persistent_id(persistent_id)
        
        if not session:
            error_msg = f"No session found with persistent ID: {persistent_id}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Return session info
        info = {
            "name": session.name,
            "id": session.id,
            "persistent_id": session.persistent_id,
            "is_processing": getattr(session, "is_processing", False),
            "is_monitoring": getattr(session, "is_monitoring", False)
        }
        
        logger.info(f"Found session: {session.name} (ID: {session.id})")
        return json.dumps(info, indent=2)
    except Exception as e:
        error_msg = f"Error getting session by persistent ID: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def set_session_max_lines(
    session_identifier: str,
    max_lines: int,
    ctx: Context
) -> str:
    """Set the maximum number of lines to retrieve for a session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
        max_lines: Maximum number of lines to retrieve
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Setting max lines for session {session_identifier} to {max_lines}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Set max lines
        session.set_max_lines(max_lines)
        logger.info(f"Set max lines to {max_lines} for session: {session.name}")
        return f"Set max lines to {max_lines} for session: {session.name}"
    except Exception as e:
        error_msg = f"Error setting max lines: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def start_monitoring_session(
    session_identifier: str,
    ctx: Context
) -> str:
    """Start real-time monitoring for a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Starting monitoring for session: {session_identifier}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Start monitoring if not already active
        if session.is_monitoring:
            return f"Session {session.name} is already being monitored"
        
        # Start monitoring
        await session.start_monitoring(update_interval=0.2)
        
        # Wait for monitoring to initialize
        await asyncio.sleep(2)
        
        if session.is_monitoring:
            logger.info(f"Successfully started monitoring for session: {session.name}")
            return f"Started monitoring for session: {session.name}"
        else:
            error_msg = f"Failed to start monitoring for session: {session.name}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"Error starting monitoring: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def stop_monitoring_session(
    session_identifier: str,
    ctx: Context
) -> str:
    """Stop real-time monitoring for a terminal session.
    
    Args:
        session_identifier: Session name, ID, or persistent ID
    """
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info(f"Stopping monitoring for session: {session_identifier}")
        
        # Find the session
        session = await terminal.get_session_by_id(session_identifier)
        if not session:
            session = await terminal.get_session_by_name(session_identifier)
        if not session:
            session = await terminal.get_session_by_persistent_id(session_identifier)
            
        if not session:
            error_msg = f"No session found with identifier: {session_identifier}"
            logger.warning(error_msg)
            await ctx.error(error_msg)
            return error_msg
        
        # Stop monitoring if active
        if not session.is_monitoring:
            return f"Session {session.name} is not being monitored"
        
        # Stop monitoring with the async method
        await session.stop_monitoring()
        
        logger.info(f"Successfully stopped monitoring for session: {session.name}")
        return f"Stopped monitoring for session: {session.name}"
    except Exception as e:
        error_msg = f"Error stopping monitoring: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


@mcp.tool()
async def list_persistent_sessions(ctx: Context) -> str:
    """List all persistent sessions available for reconnection."""
    terminal = ctx.request_context.lifespan_context["terminal"]
    logger = ctx.request_context.lifespan_context["logger"]
    
    try:
        logger.info("Listing persistent sessions")
        
        if not hasattr(terminal, "log_manager"):
            error_msg = "Log manager not available"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return error_msg
            
        # Get persistent sessions
        persistent_sessions = terminal.log_manager.list_persistent_sessions()
        
        logger.info(f"Found {len(persistent_sessions)} persistent sessions")
        return json.dumps(persistent_sessions, indent=2)
    except Exception as e:
        error_msg = f"Error listing persistent sessions: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return error_msg


# RESOURCES

@mcp.resource("terminal://{session_id}/output")
async def get_terminal_output(session_id: str) -> str:
    """Get the output from a terminal session."""
    terminal = _terminal
    logger = _logger
    
    try:
        logger.info(f"Getting output for session: {session_id}")
        
        # Find the session by ID
        session = await terminal.get_session_by_id(session_id)
        
        if not session:
            error_msg = f"No session found with ID: {session_id}"
            logger.warning(error_msg)
            return error_msg
            
        # Get screen contents
        output = await session.get_screen_contents()
        logger.info(f"Retrieved {len(output.splitlines())} lines from session {session.name}")
        return output
    except Exception as e:
        logger.error(f"Error getting terminal output: {str(e)}")
        return f"Error getting terminal output: {str(e)}"


@mcp.resource("terminal://{session_id}/info")
async def get_terminal_info(session_id: str) -> str:
    """Get information about a terminal session."""
    terminal = _terminal
    logger = _logger
    
    try:
        logger.info(f"Getting info for session: {session_id}")
        
        # Find the session by ID
        session = await terminal.get_session_by_id(session_id)
        
        if not session:
            error_msg = f"No session found with ID: {session_id}"
            logger.warning(error_msg)
            return error_msg
            
        # Collect session info
        info = {
            "name": session.name,
            "id": session.id,
            "persistent_id": session.persistent_id,
            "is_processing": getattr(session, "is_processing", False),
            "is_monitoring": getattr(session, "is_monitoring", False),
            "max_lines": session.max_lines
        }
        
        logger.info(f"Retrieved info for session {session.name}")
        return json.dumps(info, indent=2)
    except Exception as e:
        logger.error(f"Error getting terminal info: {str(e)}")
        return f"Error getting terminal info: {str(e)}"


@mcp.resource("terminal://sessions")
async def list_all_sessions() -> str:
    """Get a list of all terminal sessions."""
    terminal = _terminal
    logger = _logger
    
    try:
        logger.info("Listing all sessions as resource")
        sessions = list(terminal.sessions.values())
        result = []
        
        for session in sessions:
            result.append({
                "id": session.id,
                "name": session.name,
                "persistent_id": session.persistent_id,
                "is_processing": getattr(session, "is_processing", False),
                "is_monitoring": getattr(session, "is_monitoring", False)
            })
        
        logger.info(f"Found {len(result)} sessions")
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        return f"Error listing sessions: {str(e)}"


# PROMPTS

@mcp.prompt("monitor_terminal")
def monitor_terminal_prompt(session_name: str) -> str:
    """Prompt for monitoring a terminal session.
    
    Args:
        session_name: The name of the session to monitor
    """
    return f"""
You're monitoring the terminal session named "{session_name}".

Watch the output and help me understand what's happening.
If you see any errors or important information, please highlight them.
"""


@mcp.prompt("execute_command")
def execute_command_prompt(command: str) -> str:
    """Prompt for executing a command and analyzing the output.
    
    Args:
        command: The command to execute
    """
    return f"""
You're working with a terminal session. I'll run this command and show you the output:

```
{command}
```

Please analyze the output and explain what it means.
"""


def main():
    """Run the MCP server."""
    import sys
    import os
    
    # This handler will be used if our parent process doesn't catch the KeyboardInterrupt
    try:
        # Run the server with default handlers
        mcp.run()
    except KeyboardInterrupt:
        # If our parent set the clean exit flag, we don't need to do anything special
        if os.environ.get("ITERM_MCP_CLEAN_EXIT"):
            # Let the parent handle the exit
            return
        
        # Otherwise, we need to exit forcefully
        print("\nServer stopped by user", file=sys.stderr)
        # Use os._exit which doesn't run cleanup code or threading shutdown
        os._exit(0)
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        # Only print stack trace for non-keyboard interrupts
        import traceback
        traceback.print_exc()
        # Exit with error code
        sys.exit(1)


if __name__ == "__main__":
    main()