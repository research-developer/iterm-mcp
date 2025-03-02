"""Main entry point for the iTerm MCP server."""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Union

import iterm2
from modelcontextprotocol.server import Server
from modelcontextprotocol.server.stdio import StdioServerTransport
from modelcontextprotocol.types import (CallToolRequestSchema,
                                       ListToolsRequestSchema)

from ..core.layouts import LayoutManager, LayoutType
from ..core.session import ItermSession
from ..core.terminal import ItermTerminal


class ItermMcpServer:
    """iTerm2 MCP server implementation."""
    
    def __init__(self):
        """Initialize the server."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(os.path.expanduser("~/.iterm-mcp.log")),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("iterm-mcp")
        
        # Initialize MCP server
        self.server = Server(
            {
                "name": "iterm-mcp",
                "version": "0.1.0",
            },
            {
                "capabilities": {
                    "tools": {},
                },
            }
        )
        
        # Set terminal and layout manager to None initially
        # They will be initialized when the server starts
        self.terminal: Optional[ItermTerminal] = None
        self.layout_manager: Optional[LayoutManager] = None
        self.session_map: Dict[str, str] = {}  # Maps names to session IDs
        
        # Register request handlers
        self.server.set_request_handler(
            ListToolsRequestSchema, self.handle_list_tools
        )
        self.server.set_request_handler(
            CallToolRequestSchema, self.handle_call_tool
        )
    
    async def start(self):
        """Start the server."""
        # Initialize connection to iTerm2
        connection = await iterm2.Connection.async_create()
        
        # Initialize terminal and layout manager
        self.terminal = ItermTerminal(connection)
        await self.terminal.initialize()
        
        self.layout_manager = LayoutManager(self.terminal)
        
        # Connect the server to stdio
        transport = StdioServerTransport()
        await self.server.connect(transport)
    
    async def handle_list_tools(self, request: Any) -> Dict[str, Any]:
        """Handle list tools request.
        
        Args:
            request: The request object
            
        Returns:
            Response with tool definitions
        """
        return {
            "tools": [
                # Session interaction tools
                {
                    "name": "write_to_terminal",
                    "description": "Writes text to an iTerm terminal session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to run or text to write to the terminal"
                            },
                            "session_name": {
                                "type": "string",
                                "description": "Optional session name to target a specific session. If omitted, uses the current session."
                            },
                            "wait_for_completion": {
                                "type": "boolean",
                                "description": "Whether to wait for the command to complete before returning. Default is true."
                            }
                        },
                        "required": ["command"]
                    }
                },
                {
                    "name": "read_terminal_output",
                    "description": "Reads the output from an iTerm terminal session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "lines_of_output": {
                                "type": "number",
                                "description": "The number of lines of output to read."
                            },
                            "session_name": {
                                "type": "string",
                                "description": "Optional session name to target a specific session. If omitted, uses the current session."
                            }
                        },
                        "required": ["lines_of_output"]
                    }
                },
                {
                    "name": "send_control_character",
                    "description": "Sends a control character to an iTerm terminal session (e.g., Control-C)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "letter": {
                                "type": "string",
                                "description": "The letter corresponding to the control character (e.g., 'C' for Control-C)"
                            },
                            "session_name": {
                                "type": "string",
                                "description": "Optional session name to target a specific session. If omitted, uses the current session."
                            }
                        },
                        "required": ["letter"]
                    }
                },
                
                # Session management tools
                {
                    "name": "list_sessions",
                    "description": "Lists all available iTerm sessions",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "focus_session",
                    "description": "Focuses on a specific iTerm session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_name": {
                                "type": "string",
                                "description": "The name of the session to focus"
                            }
                        },
                        "required": ["session_name"]
                    }
                },
                {
                    "name": "check_session_status",
                    "description": "Checks if a terminal session is currently processing a command",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_name": {
                                "type": "string",
                                "description": "The name of the session to check"
                            }
                        },
                        "required": ["session_name"]
                    }
                },
                
                # Layout management tools
                {
                    "name": "create_layout",
                    "description": "Creates a new terminal layout with named sessions",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "layout_type": {
                                "type": "string",
                                "description": "The type of layout to create",
                                "enum": [
                                    "single", 
                                    "horizontal_split", 
                                    "vertical_split", 
                                    "quad", 
                                    "triple_right", 
                                    "triple_bottom"
                                ]
                            },
                            "pane_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Names for the panes in the layout"
                            }
                        },
                        "required": ["layout_type"]
                    }
                }
            ]
        }
    
    async def handle_call_tool(self, request: Any) -> Dict[str, Any]:
        """Handle tool call request.
        
        Args:
            request: The request object
            
        Returns:
            Response with tool result
        """
        tool_name = request.params.name
        arguments = request.params.arguments or {}
        
        self.logger.info(f"Tool call: {tool_name} - Arguments: {arguments}")
        
        try:
            if tool_name == "write_to_terminal":
                return await self._handle_write_to_terminal(arguments)
            elif tool_name == "read_terminal_output":
                return await self._handle_read_terminal_output(arguments)
            elif tool_name == "send_control_character":
                return await self._handle_send_control_character(arguments)
            elif tool_name == "list_sessions":
                return await self._handle_list_sessions(arguments)
            elif tool_name == "focus_session":
                return await self._handle_focus_session(arguments)
            elif tool_name == "check_session_status":
                return await self._handle_check_session_status(arguments)
            elif tool_name == "create_layout":
                return await self._handle_create_layout(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        except Exception as e:
            self.logger.error(f"Error handling tool call: {e}", exc_info=True)
            raise
    
    async def _handle_write_to_terminal(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle write to terminal tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        command = str(arguments.get("command", ""))
        session_name = arguments.get("session_name")
        wait_for_completion = arguments.get("wait_for_completion", True)
        
        # Get session
        session = await self._get_session(session_name)
        
        # Send text to the session
        await session.send_text(command)
        
        # Wait for completion if requested
        if wait_for_completion:
            while session.is_processing:
                await asyncio.sleep(0.1)
            
            # Get terminal output after command execution
            output = await session.get_screen_contents(50)
            lines = output.split("\n")
            output_lines = len(lines)
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"{output_lines} lines were output after sending the command to the terminal. "
                           f"Read the terminal contents to orient yourself. Never assume that the command "
                           f"was executed or that it was successful."
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Command sent to terminal (not waiting for completion). "
                           f"Use check_session_status to monitor if the command is still running."
                }]
            }
    
    async def _handle_read_terminal_output(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle read terminal output tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        lines_of_output = int(arguments.get("lines_of_output", 50))
        session_name = arguments.get("session_name")
        
        # Get session
        session = await self._get_session(session_name)
        
        # Get terminal output
        output = await session.get_screen_contents(lines_of_output)
        
        return {
            "content": [{
                "type": "text",
                "text": output
            }]
        }
    
    async def _handle_send_control_character(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send control character tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        letter = str(arguments.get("letter", ""))
        session_name = arguments.get("session_name")
        
        # Get session
        session = await self._get_session(session_name)
        
        # Send control character
        await session.send_control_character(letter)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Sent control character: Control-{letter.upper()}"
            }]
        }
    
    async def _handle_list_sessions(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle list sessions tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Get all sessions
        sessions = await self.terminal.get_sessions()
        
        # Build response
        session_info = []
        for session in sessions:
            session_info.append({
                "id": session.id,
                "name": session.name,
                "is_processing": session.is_processing
            })
            
            # Update session map
            self.session_map[session.name] = session.id
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(session_info, indent=2)
            }]
        }
    
    async def _handle_focus_session(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle focus session tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        session_name = arguments.get("session_name")
        
        # Get session
        session = await self._get_session(session_name)
        
        # Focus session
        await self.terminal.focus_session(session.id)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Focused session: {session.name}"
            }]
        }
    
    async def _handle_check_session_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check session status tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        session_name = arguments.get("session_name")
        
        # Get session
        session = await self._get_session(session_name)
        
        return {
            "content": [{
                "type": "text",
                "text": f"Session '{session.name}' status: {'BUSY' if session.is_processing else 'IDLE'}"
            }]
        }
    
    async def _handle_create_layout(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create layout tool.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        # Extract arguments
        layout_type_str = arguments.get("layout_type", "single")
        pane_names = arguments.get("pane_names", [])
        
        # Convert layout type string to enum
        try:
            layout_type = LayoutType(layout_type_str)
        except ValueError:
            layout_type = LayoutType.SINGLE
        
        # Create layout
        session_map = await self.layout_manager.create_layout(
            layout_type=layout_type,
            pane_names=pane_names
        )
        
        # Update session map
        self.session_map.update(session_map)
        
        # Build response
        layout_info = {
            "layout_type": layout_type.value,
            "sessions": list(session_map.keys())
        }
        
        return {
            "content": [{
                "type": "text",
                "text": f"Created {layout_type.value} layout with sessions: {', '.join(session_map.keys())}"
            }]
        }
    
    async def _get_session(self, session_name: Optional[str] = None) -> ItermSession:
        """Get a session by name or the current session.
        
        Args:
            session_name: Optional name of the session to get
            
        Returns:
            The session object
            
        Raises:
            ValueError: If the session is not found
        """
        if not self.terminal:
            raise RuntimeError("Terminal not initialized")
            
        # If session name is provided, try to get the session by name
        if session_name:
            # Check session map first
            if session_name in self.session_map:
                session_id = self.session_map[session_name]
                session = await self.terminal.get_session_by_id(session_id)
                if session:
                    return session
            
            # Try to get the session by name
            session = await self.terminal.get_session_by_name(session_name)
            if session:
                # Update session map
                self.session_map[session_name] = session.id
                return session
                
            # Session not found
            raise ValueError(f"Session with name '{session_name}' not found")
        
        # Get all sessions
        sessions = await self.terminal.get_sessions()
        if not sessions:
            # Create a new session if none exists
            session = await self.terminal.create_window()
            return session
        
        # Return the first session
        return sessions[0]


async def async_main():
    """Async entry point for the server."""
    server = ItermMcpServer()
    await server.start()


def main():
    """Main entry point for the server."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()