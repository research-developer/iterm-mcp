#!/usr/bin/env python3
"""Create a split pane layout in iTerm2."""

import asyncio
import iterm2

async def main(connection):
    """Create a horizontal split layout with two panes."""
    app = await iterm2.async_get_app(connection)
    
    # Create a new tab
    window = app.current_terminal_window
    if window is None:
        print("No current window")
        return
        
    await window.async_create_tab()
    tab = window.current_tab
    
    # Get the current session
    session = tab.current_session
    await session.async_set_name("Main")
    
    # Create a split pane
    right_session = await session.async_split_pane(vertical=True)
    await right_session.async_set_name("Claude Agent")
    
    # Run commands
    await session.async_send_text("cd /Users/preston/MCP/iterm-mcp\n")
    await session.async_send_text("python -m iterm_mcp_python.server.main\n")
    
    await right_session.async_send_text("cd /Users/preston/MCP/iterm-mcp\n")
    await right_session.async_send_text("./run_claude_agent.sh \"$(cat claude_debugging_task.txt)\"\n")

if __name__ == "__main__":
    iterm2.run_until_complete(main)