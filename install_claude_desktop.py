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

    # Install the server in Claude Desktop by editing the configuration directly
    try:
        import json
        
        # Get the Claude Desktop configuration path
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        
        if not config_path.exists():
            print(f"Error: Claude Desktop configuration file not found at {config_path}")
            return 1
            
        # Read the existing configuration
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Ensure mcpServers section exists
        if 'mcpServers' not in config:
            config['mcpServers'] = {}
            
        # Use the current Python interpreter path
        python_path = sys.executable
        
        # Add or update our server configuration
        config['mcpServers']['iTerm Terminal Controller'] = {
            "command": python_path,
            "args": [
                str(SERVER_SCRIPT)
            ]
        }
        
        # Write the updated configuration
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        # Log the installation
        print(f"Installing iTerm MCP server in Claude Desktop...")
        
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