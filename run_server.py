#!/Users/preston/miniconda3/envs/mcp/bin/python
"""Direct entry point for iTerm MCP server - use this for Claude Desktop/Code."""

import sys
import os

# Add the project root to the path so imports work
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the server directly
from iterm_mcpy.fastmcp_server import mcp

if __name__ == "__main__":
    mcp.run()
