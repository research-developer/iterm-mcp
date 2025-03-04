#!/usr/bin/env python3
"""
Install the iTerm MCP server in Claude Desktop.

This script installs the iTerm MCP server in Claude Desktop,
making it available for use with the Claude AI.
"""

import os
import subprocess
import sys
import socket
import json
import signal
from pathlib import Path
from typing import Optional, Tuple


def is_server_running() -> bool:
    """Check if the iTerm MCP server is already running.
    
    Returns:
        bool: True if the server is running, False otherwise
    """
    # The server uses port range 12340-12349
    for port in range(12340, 12350):
        try:
            # Try to connect to the server port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    return True
        except:
            pass
    return False


def start_server() -> Optional[subprocess.Popen]:
    """Start the iTerm MCP server in the background.
    
    Returns:
        Optional[subprocess.Popen]: Process object if server started, None otherwise
    """
    try:
        # Start the server in the background
        process = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach from parent process
        )
        
        # Wait a moment for the server to start
        import time
        time.sleep(2)
        
        # Check if process is still running and server is accessible
        if process.poll() is None and is_server_running():
            return process
        else:
            # Server didn't start properly, try to clean up
            try:
                process.terminate()
            except:
                pass
            return None
    except Exception as e:
        print(f"Error starting server: {e}")
        return None


def check_error_for_server_status(error_msg: str) -> bool:
    """Check if an error message indicates the server is not running.
    
    Args:
        error_msg: The error message to check
        
    Returns:
        bool: True if the error indicates the server is not running
    """
    server_missing_patterns = [
        "no close frame received or sent",
        "connection refused",
        "failed to connect",
        "connection error",
        "WebSocket connection failed",
        "could not connect to server",
        "socket hang up",
        "ECONNREFUSED"
    ]
    
    error_msg = error_msg.lower()
    return any(pattern in error_msg for pattern in server_missing_patterns)


def install_claude_desktop_config() -> Tuple[bool, str]:
    """Install the iTerm MCP server in Claude Desktop configuration.
    
    Returns:
        Tuple[bool, str]: Success status and message
    """
    try:
        # Get the Claude Desktop configuration path
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        
        if not config_path.exists():
            return False, f"Error: Claude Desktop configuration file not found at {config_path}"
            
        # Read the existing configuration
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Ensure mcpServers section exists
        if 'mcpServers' not in config:
            config['mcpServers'] = {}
            
        # Use the current Python interpreter path
        python_path = sys.executable
        
        # Add or update our server configuration using module-based approach
        config['mcpServers']['iTerm Terminal Controller'] = {
            "command": python_path,
            "args": [
                "-m",
                "server.main"
            ]
        }
        
        # Write the updated configuration
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        return True, "Configuration updated successfully"
    except Exception as e:
        return False, f"Error updating configuration: {str(e)}"


def main():
    """Install the iTerm MCP server in Claude Desktop."""
    print("iTerm MCP Server Installer")
    print("--------------------------")
    
    # Install the configuration
    success, message = install_claude_desktop_config()
    if not success:
        print(message)
        return 1
    
    # Check if the server is already running
    server_running = is_server_running()
    
    if server_running:
        print("✅ iTerm MCP Server is already running")
    else:
        print("❌ iTerm MCP Server is not running")
        print("IMPORTANT: Remember to start the server before using it with Claude Desktop:")
        print("  python -m server.main")
        print("")
        print("To start it now, run the server in a separate terminal window.")
    
    print("\n✅ Configuration installed successfully in Claude Desktop")
    print("You can now use the 'iTerm Terminal Controller' in Claude Desktop")
    print("\nIf you encounter connection errors when using the controller, run:")
    print("  python -m server.main")
    print("\nMake sure to keep the server running while using the controller.")
    return 0


def handle_server_error(error_msg):
    """Handle error messages that indicate the server might not be running.
    
    Args:
        error_msg: The error message from Claude Desktop
    """
    if check_error_for_server_status(error_msg):
        print("\n❌ Server connection error detected")
        print("It appears the iTerm MCP server is not running")
        
        if is_server_running():
            print("However, the server port seems to be active.")
            print("This may indicate a different issue with the connection.")
            print("Try restarting the server:")
            print("  1. Kill the existing server: pkill -f 'python -m server.main'")
            print("  2. Start a new server: python -m server.main")
        else:
            print("Starting the server now...")
            server_process = start_server()
            
            if server_process and is_server_running():
                print("✅ iTerm MCP Server started successfully")
                print("Please try your request again in Claude Desktop")
            else:
                print("❌ Failed to automatically start the server")
                print("Please run the server manually in a new terminal window:")
                print("  python -m server.main")
    else:
        print(f"Unknown error: {error_msg}")
        print("If this persists, check the server logs for more information")


if __name__ == "__main__":
    # If an error message is passed as the first argument, handle it
    if len(sys.argv) > 1 and sys.argv[1] == "--check-error":
        if len(sys.argv) > 2:
            handle_server_error(" ".join(sys.argv[2:]))
        else:
            print("Usage: python install_claude_desktop.py --check-error 'error message'")
    else:
        sys.exit(main())