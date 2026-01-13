#!/usr/bin/env python3
"""Direct entry point for iTerm MCP server - use this for Claude Desktop/Code.

Usage:
    # stdio mode (default, for Claude Desktop spawning)
    python run_server.py

    # HTTP daemon mode (singleton server for multiple clients)
    python run_server.py --transport streamable-http --port 12345

    # SSE mode (legacy HTTP)
    python run_server.py --transport sse --port 12345
"""

import argparse
import sys
import os

# Add the project root to the path so imports work
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the server directly
from iterm_mcpy.fastmcp_server import mcp


def main():
    parser = argparse.ArgumentParser(
        description="iTerm MCP Server - Control iTerm2 via Model Context Protocol"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio for Claude Desktop, use streamable-http for daemon mode)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=12345,
        help="Port for HTTP transports (default: 12345)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for HTTP transports (default: 127.0.0.1)"
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        print("Starting iTerm MCP server (stdio mode)...", file=sys.stderr)
        mcp.run(transport="stdio")
    else:
        # Configure host/port for HTTP transports
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        print(f"Starting iTerm MCP server ({args.transport} mode)...", file=sys.stderr)
        print(f"  Endpoint: http://{args.host}:{args.port}/mcp", file=sys.stderr)
        print(f"  Press Ctrl+C to stop", file=sys.stderr)

        mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
