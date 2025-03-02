#!/usr/bin/env python3
"""
MCP server entry point for iTerm2 controller.

This script launches the iTerm2 MCP server, which allows controlling
iTerm2 terminal sessions through the Model Context Protocol (MCP).
"""

from iterm_mcp_python.server.mcp_server import main

if __name__ == "__main__":
    main()