"""MCP server implementation for iTerm2 controller."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

import iterm2
from mcp.server.fastmcp import FastMCP, Context, Image

from ..core.layouts import LayoutManager, LayoutType
from ..core.session import ItermSession
from ..core.terminal import ItermTerminal


class ItermMCPServer:
    """MCP server for iTerm2 terminal controller."""

    def __init__(self):
        """Initialize the MCP server."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(os.path.expanduser("~/.iterm-mcp.log")),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("iterm-mcp-server")

        # Create FastMCP server
        self.mcp = FastMCP(
            name="iTerm2 Controller",
            instructions="Control iTerm2 terminal sessions, execute commands, and capture outputs"
        )

        # Set terminal and layout manager to None initially
        # They will be initialized when the controller starts
        self.terminal: Optional[ItermTerminal] = None
        self.layout_manager: Optional[LayoutManager] = None
        self.connection: Optional[iterm2.Connection] = None
        
        # Configure log directory
        self.log_dir = os.path.expanduser("~/.iterm_mcp_logs")

        # Initialize MCP tools
        self.setup_tools()
        self.setup_resources()
        self.setup_prompts()

    async def initialize(self):
        """Initialize the iTerm2 connection and services."""
        try:
            # Initialize connection to iTerm2
            self.connection = await iterm2.Connection.async_create()

            # Initialize terminal and layout manager
            self.terminal = ItermTerminal(
                connection=self.connection,
                log_dir=self.log_dir,
                enable_logging=True,
                default_max_lines=100,  # Increased for better usability
                max_snapshot_lines=1000
            )
            await self.terminal.initialize()

            self.layout_manager = LayoutManager(self.terminal)

            self.logger.info(f"iTerm2 controller initialized. Logs saved to: {self.log_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize iTerm2 connection: {str(e)}")
            return False

    def setup_tools(self):
        """Set up MCP tools."""
        # Session management tools
        @self.mcp.tool()
        async def list_sessions(ctx: Context) -> str:
            """List all available terminal sessions."""
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            sessions = list(self.terminal.sessions.values())
            result = []
            
            for session in sessions:
                result.append({
                    "id": session.id,
                    "name": session.name,
                    "persistent_id": session.persistent_id
                })
                
            return json.dumps(result, indent=2)
            
        @self.mcp.tool()
        async def focus_session(session_identifier: str, ctx: Context) -> str:
            """Focus on a specific terminal session.
            
            Args:
                session_identifier: Session name, ID, or persistent ID
            """
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
            
            # Try finding by ID
            session = await self.terminal.get_session_by_id(session_identifier)
            
            # Try finding by name if not found by ID
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
                
            # Try finding by persistent ID if still not found
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Focus the session
            await self.terminal.focus_session(session.id)
            return f"Focused on session: {session.name} (ID: {session.id})"
            
        @self.mcp.tool()
        async def create_layout(
            layout_type: str, 
            ctx: Context,
            pane_names: Optional[List[str]] = None
        ) -> str:
            """Create a new terminal layout with named sessions.
            
            Args:
                layout_type: The layout type (single, horizontal, vertical, quad)
                pane_names: Optional list of names for panes (defaults to generic names)
            """
            if not self.terminal or not self.layout_manager:
                await self.initialize()
                
            if not self.terminal or not self.layout_manager:
                return "Failed to initialize iTerm2 connection"
                
            try:
                # Convert layout type string to enum
                layout_type_enum = None
                if layout_type.lower() == "single":
                    layout_type_enum = LayoutType.SINGLE
                elif layout_type.lower() == "horizontal":
                    layout_type_enum = LayoutType.HORIZONTAL
                elif layout_type.lower() == "vertical":
                    layout_type_enum = LayoutType.VERTICAL
                elif layout_type.lower() == "quad":
                    layout_type_enum = LayoutType.QUAD
                else:
                    return f"Invalid layout type: {layout_type}. Choose from: single, horizontal, vertical, quad"
                    
                # Create the layout
                sessions = await self.layout_manager.create_layout(
                    layout_type=layout_type_enum,
                    pane_names=pane_names
                )
                
                # Return information about created sessions
                result = []
                for session in sessions:
                    result.append({
                        "id": session.id,
                        "name": session.name,
                        "persistent_id": session.persistent_id
                    })
                    
                return json.dumps(result, indent=2)
            except Exception as e:
                self.logger.error(f"Error creating layout: {str(e)}")
                return f"Error creating layout: {str(e)}"
                
        # Command execution tools
        @self.mcp.tool()
        async def write_to_terminal(
            session_identifier: str, 
            command: str,
            ctx: Context,
            wait_for_prompt: bool = False
        ) -> str:
            """Write a command to a terminal session.
            
            Args:
                session_identifier: Session name, ID, or persistent ID
                command: The command to write
                wait_for_prompt: Whether to wait for the command prompt to appear
            """
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Add a newline if not present
            if not command.endswith("\n"):
                command += "\n"
                
            # Send the command
            await session.send_text(command)
            
            # Wait for prompt if requested
            if wait_for_prompt:
                # Simple prompt detection by waiting and checking if processing is done
                max_wait = 10  # maximum seconds to wait
                for _ in range(max_wait * 2):  # Check every 0.5 seconds
                    await asyncio.sleep(0.5)
                    if not session.is_processing:
                        break
                        
            return f"Command sent to session: {session.name}"
            
        @self.mcp.tool()
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
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Get the screen contents
            output = await session.get_screen_contents(max_lines=max_lines)
            return output
            
        @self.mcp.tool()
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
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Send the control character
            await session.send_control_character(control_char)
            return f"Control character Ctrl+{control_char.upper()} sent to session: {session.name}"
            
        @self.mcp.tool()
        async def check_session_status(
            session_identifier: str,
            ctx: Context
        ) -> str:
            """Check if a session is currently processing a command.
            
            Args:
                session_identifier: Session name, ID, or persistent ID
            """
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Check processing status
            status = {
                "name": session.name,
                "id": session.id,
                "persistent_id": session.persistent_id,
                "is_processing": session.is_processing
            }
            
            return json.dumps(status, indent=2)
            
        # Advanced features
        @self.mcp.tool()
        async def get_session_by_persistent_id(
            persistent_id: str,
            ctx: Context
        ) -> str:
            """Get a session by its persistent ID (useful for reconnection).
            
            Args:
                persistent_id: The persistent ID of the session
            """
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session by persistent ID
            session = await self.terminal.get_session_by_persistent_id(persistent_id)
            
            if not session:
                return f"No session found with persistent ID: {persistent_id}"
                
            # Return session info
            info = {
                "name": session.name,
                "id": session.id,
                "persistent_id": session.persistent_id,
                "is_processing": session.is_processing
            }
            
            return json.dumps(info, indent=2)
            
        @self.mcp.tool()
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
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_name(session_identifier)
            if not session:
                session = await self.terminal.get_session_by_persistent_id(session_identifier)
                
            if not session:
                return f"No session found with identifier: {session_identifier}"
                
            # Set max lines
            session.set_max_lines(max_lines)
            
            return f"Set max lines to {max_lines} for session: {session.name}"
            
        @self.mcp.tool()
        async def list_persistent_sessions(
            ctx: Context
        ) -> str:
            """List all persistent sessions available for reconnection."""
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            if not hasattr(self.terminal, "log_manager"):
                return "Log manager not available"
                
            # Get persistent sessions
            persistent_sessions = self.terminal.log_manager.list_persistent_sessions()
            return json.dumps(persistent_sessions, indent=2)

    def setup_resources(self):
        """Set up MCP resources."""
        @self.mcp.resource("iterm://sessions")
        async def get_sessions() -> str:
            """Get a list of all current sessions."""
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            sessions = list(self.terminal.sessions.values())
            result = []
            
            for session in sessions:
                result.append({
                    "id": session.id,
                    "name": session.name,
                    "persistent_id": session.persistent_id,
                    "is_processing": session.is_processing
                })
                
            return json.dumps(result, indent=2)
            
        @self.mcp.resource("iterm://session/{session_id}/output")
        async def get_session_output(session_id: str) -> str:
            """Get output from a specific session.
            
            Args:
                session_id: The ID of the session
            """
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            # Find the session
            session = await self.terminal.get_session_by_id(session_id)
            
            if not session:
                return f"No session found with ID: {session_id}"
                
            # Get the screen contents
            output = await session.get_screen_contents()
            return output
            
        @self.mcp.resource("iterm://persistent-sessions")
        async def get_persistent_sessions() -> str:
            """Get a list of all persistent sessions."""
            if not self.terminal:
                await self.initialize()
                
            if not self.terminal:
                return "Failed to initialize iTerm2 connection"
                
            if not hasattr(self.terminal, "log_manager"):
                return "Log manager not available"
                
            # Get persistent sessions
            persistent_sessions = self.terminal.log_manager.list_persistent_sessions()
            return json.dumps(persistent_sessions, indent=2)

    def setup_prompts(self):
        """Set up MCP prompts."""
        @self.mcp.prompt("execute-command")
        def execute_command_prompt(command: str) -> str:
            """Create a prompt to execute a command and analyze its output."""
            return f"""
You're working with a terminal session. I'll run this command and show you the output:

```
{command}
```

Please analyze the output and explain what it means.
"""

        @self.mcp.prompt("monitor-session")
        def monitor_session_prompt(session_name: str) -> str:
            """Create a prompt to monitor a terminal session."""
            return f"""
You're monitoring the terminal session named "{session_name}".

Watch the output and help me understand what's happening.
If you see any errors or important information, please highlight them.
"""

    def run(self):
        """Run the MCP server."""
        try:
            # Initialize connection
            asyncio.run(self.initialize())
            
            # Run FastMCP server
            self.mcp.run()
        except KeyboardInterrupt:
            print("Server stopped by user")
        except Exception as e:
            print(f"Error running server: {e}")


def main():
    """Main entry point for the MCP server."""
    server = ItermMCPServer()
    server.run()


if __name__ == "__main__":
    main()