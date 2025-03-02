#!/usr/bin/env python3
"""
Install the iTerm MCP server in Claude Desktop.

This script installs the iTerm MCP server in Claude Desktop,
making it available for use with the Claude AI.
"""

import os
import subprocess
import sys
from pathlib import Path

# Get the absolute path to the MCP server script
SCRIPT_DIR = Path(__file__).parent.absolute()
SERVER_SCRIPT = SCRIPT_DIR / "mcp_server.py"


def main():
    """Install the iTerm MCP server in Claude Desktop."""
    # Check if the server script exists
    if not SERVER_SCRIPT.exists():
        print(f"Error: Server script not found at {SERVER_SCRIPT}")
        return 1

    # Make sure the script is executable
    os.chmod(SERVER_SCRIPT, 0o755)

    # Install the server in Claude Desktop using MCP CLI
    try:
        cmd = [
            "mcp", "install",
            str(SERVER_SCRIPT),
            "--name", "iTerm Terminal Controller"
        ]
        
        # Run the command
        print(f"Installing iTerm MCP server in Claude Desktop...")
        subprocess.run(cmd, check=True)
        
        print("Installation successful!")
        print("You can now use the iTerm Terminal Controller in Claude Desktop.")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error installing server: {e}")
        return 1
    except FileNotFoundError:
        print("Error: 'mcp' command not found. Please install the MCP CLI:")
        print("pip install 'mcp[cli]'")
        return 1


if __name__ == "__main__":
    sys.exit(main())