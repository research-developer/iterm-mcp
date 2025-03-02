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
            # Initialize connection to iTerm2 with proper error handling
            self.logger.info("Initializing iTerm2 connection...")
            try:
                self.connection = await iterm2.Connection.async_create()
                self.logger.info("iTerm2 connection established successfully")
            except Exception as conn_error:
                self.logger.error(f"Failed to establish iTerm2 connection: {str(conn_error)}")
                return False

            # Initialize terminal and layout manager
            self.logger.info("Initializing iTerm terminal controller...")
            self.terminal = ItermTerminal(
                connection=self.connection,
                log_dir=self.log_dir,
                enable_logging=True,
                default_max_lines=100,  # Increased for better usability
                max_snapshot_lines=1000
            )
            
            try:
                await self.terminal.initialize()
                self.logger.info("iTerm terminal controller initialized successfully")
            except Exception as term_error:
                self.logger.error(f"Failed to initialize iTerm terminal controller: {str(term_error)}")
                return False

            # Initialize layout manager
            self.logger.info("Initializing layout manager...")
            self.layout_manager = LayoutManager(self.terminal)
            self.logger.info("Layout manager initialized successfully")

            self.logger.info(f"iTerm2 controller fully initialized. Logs saved to: {self.log_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize iTerm2 controller: {str(e)}")
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
            try:
                if not self.terminal:
                    await self.initialize()
                    
                if not self.terminal:
                    return "Failed to initialize iTerm2 connection"
                
                self.logger.info(f"Focusing session: {session_identifier}")
                
                # Try finding by ID
                session = await self.terminal.get_session_by_id(session_identifier)
                
                # Try finding by name if not found by ID
                if not session:
                    session = await self.terminal.get_session_by_name(session_identifier)
                    
                # Try finding by persistent ID if still not found
                if not session:
                    session = await self.terminal.get_session_by_persistent_id(session_identifier)
                    
                if not session:
                    self.logger.warning(f"No session found with identifier: {session_identifier}")
                    return f"No session found with identifier: {session_identifier}"
                
                self.logger.info(f"Found session: {session.name} (ID: {session.id})")
                
                # Focus the session with proper error handling
                try:
                    await self.terminal.focus_session(session.id)
                    self.logger.info(f"Successfully focused on session: {session.name}")
                    return f"Focused on session: {session.name} (ID: {session.id})"
                except Exception as focus_error:
                    self.logger.error(f"Error focusing session: {str(focus_error)}")
                    return f"Error focusing session: {str(focus_error)}"
            except Exception as e:
                self.logger.error(f"Error in focus_session: {str(e)}")
                return f"Error in focus_session: {str(e)}"
            
        @self.mcp.tool()
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
                    layout_type_enum = LayoutType.HORIZONTAL_SPLIT
                elif layout_type.lower() == "vertical":
                    layout_type_enum = LayoutType.VERTICAL_SPLIT
                elif layout_type.lower() == "quad":
                    layout_type_enum = LayoutType.QUAD
                else:
                    return f"Invalid layout type: {layout_type}. Choose from: single, horizontal, vertical, quad"
                    
                # Create the layout (pass session_names as pane_names)
                sessions = await self.layout_manager.create_layout(
                    layout_type=layout_type_enum,
                    pane_names=session_names
                )
                
                # Return information about created sessions
                result = []
                for session_name, session_id in sessions.items():
                    session = await self.terminal.get_session_by_id(session_id)
                    if session:
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
            try:
                if not self.terminal:
                    await self.initialize()
                    
                if not self.terminal:
                    return "Failed to initialize iTerm2 connection"
                
                self.logger.info(f"Writing to session: {session_identifier}, command: {command[:20]}...")
                
                # Find the session
                session = None
                try:
                    session = await self.terminal.get_session_by_id(session_identifier)
                except Exception as e:
                    self.logger.error(f"Error finding session by ID: {str(e)}")
                
                if not session:
                    try:
                        session = await self.terminal.get_session_by_name(session_identifier)
                    except Exception as e:
                        self.logger.error(f"Error finding session by name: {str(e)}")
                
                if not session:
                    try:
                        session = await self.terminal.get_session_by_persistent_id(session_identifier)
                    except Exception as e:
                        self.logger.error(f"Error finding session by persistent ID: {str(e)}")
                    
                if not session:
                    self.logger.warning(f"No session found with identifier: {session_identifier}")
                    return f"No session found with identifier: {session_identifier}"
                
                # Add a newline if not present
                if not command.endswith("\n"):
                    command += "\n"
                
                # Check if session has is_processing attribute
                if not hasattr(session, 'is_processing'):
                    self.logger.warning(f"Session {session.name} does not have is_processing attribute")
                    # Add a default attribute
                    session.is_processing = False
                
                # Send the command
                try:
                    await session.send_text(command)
                    self.logger.info(f"Command sent to session: {session.name}")
                except Exception as send_error:
                    self.logger.error(f"Error sending command: {str(send_error)}")
                    return f"Error sending command: {str(send_error)}"
                
                # Wait for prompt if requested
                if wait_for_prompt:
                    try:
                        # Simple prompt detection by waiting and checking if processing is done
                        max_wait = 10  # maximum seconds to wait
                        for i in range(max_wait * 2):  # Check every 0.5 seconds
                            await asyncio.sleep(0.5)
                            if hasattr(session, 'is_processing') and not session.is_processing:
                                self.logger.info(f"Command completed after {i*0.5} seconds")
                                break
                            
                        if hasattr(session, 'is_processing') and session.is_processing:
                            self.logger.warning(f"Command still processing after {max_wait} seconds")
                    except Exception as wait_error:
                        self.logger.error(f"Error waiting for prompt: {str(wait_error)}")
                
                return f"Command sent to session: {session.name}"
            except Exception as e:
                self.logger.error(f"Error in write_to_terminal: {str(e)}")
                return f"Error in write_to_terminal: {str(e)}"
            
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
            try:
                if not self.terminal:
                    await self.initialize()
                    
                if not self.terminal:
                    return "Failed to initialize iTerm2 connection"
                
                self.logger.info(f"Checking status of session: {session_identifier}")
                
                # Find the session with error handling
                session = None
                try:
                    session = await self.terminal.get_session_by_id(session_identifier)
                except Exception as e:
                    self.logger.error(f"Error finding session by ID: {str(e)}")
                
                if not session:
                    try:
                        session = await self.terminal.get_session_by_name(session_identifier)
                    except Exception as e:
                        self.logger.error(f"Error finding session by name: {str(e)}")
                
                if not session:
                    try:
                        session = await self.terminal.get_session_by_persistent_id(session_identifier)
                    except Exception as e:
                        self.logger.error(f"Error finding session by persistent ID: {str(e)}")
                    
                if not session:
                    self.logger.warning(f"No session found with identifier: {session_identifier}")
                    return f"No session found with identifier: {session_identifier}"
                
                # Check for required attributes
                if not hasattr(session, "is_processing"):
                    self.logger.warning(f"Session {session.name} does not have is_processing attribute")
                    # Add a default attribute
                    session.is_processing = False
                
                # Check processing status
                status = {
                    "name": session.name,
                    "id": session.id,
                    "persistent_id": session.persistent_id,
                    "is_processing": getattr(session, "is_processing", False)
                }
                
                self.logger.info(f"Session status: {json.dumps(status)}")
                return json.dumps(status, indent=2)
            except Exception as e:
                self.logger.error(f"Error in check_session_status: {str(e)}")
                return f"Error in check_session_status: {str(e)}"
            
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
            # Initialize connection with proper handling
            init_result = asyncio.run(self.initialize())
            
            if not init_result:
                self.logger.error("Failed to initialize. Cannot start MCP server.")
                print("Failed to initialize iTerm2 connection. Check logs for details.")
                return
            
            # Add graceful shutdown handler
            import signal
            
            def handle_shutdown(sig, frame):
                self.logger.info(f"Received signal {sig}. Shutting down gracefully...")
                print(f"Received signal {sig}. Shutting down gracefully...")
                # Any cleanup if needed
                
            # Register signal handlers
            signal.signal(signal.SIGINT, handle_shutdown)
            signal.signal(signal.SIGTERM, handle_shutdown)
            
            # Run FastMCP server with proper exception handling
            self.logger.info("Starting MCP server...")
            try:
                self.mcp.run()
            except KeyboardInterrupt:
                self.logger.info("Server stopped by user (KeyboardInterrupt)")
                print("Server stopped by user")
            except Exception as server_error:
                self.logger.error(f"Error running MCP server: {str(server_error)}")
                print(f"Error running MCP server: {server_error}")
                
        except KeyboardInterrupt:
            self.logger.info("Initialization stopped by user")
            print("Server stopped by user during initialization")
        except Exception as e:
            self.logger.error(f"Critical error running server: {str(e)}")
            print(f"Critical error running server: {e}")


def main():
    """Main entry point for the MCP server."""
    server = ItermMCPServer()
    server.run()


if __name__ == "__main__":
    main()