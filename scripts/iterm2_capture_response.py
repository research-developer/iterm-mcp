#!/usr/bin/env python3
"""
iTerm2 Python script for capturing Claude responses with color detection.

This script registers with iTerm2 and can be called from triggers via
"Invoke Script Function" action.

Installation:
1. Copy to ~/Library/Application Support/iTerm2/Scripts/
2. Or symlink: ln -s /path/to/this/file ~/Library/Application\ Support/iTerm2/Scripts/

Usage in iTerm2 Trigger:
- Regex: ^⏺
- Action: Invoke Script Function
- Parameter: capture_claude_response(session.id)
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Tuple

import iterm2

# Configuration
DASHBOARD_API_URL = "http://localhost:9999/api/db/responses"
LOG_FILE = None  # Set to a path to enable file logging, e.g., "/tmp/iterm2_capture.log"

# Color detection constants
# These RGB values correspond to common terminal colors
COLOR_GREEN_THRESHOLD = (0, 180, 0)  # Approximate green for success
COLOR_RED_THRESHOLD = (180, 0, 0)    # Approximate red for error
COLOR_YELLOW_THRESHOLD = (180, 180, 0)  # Approximate yellow for warning

# The bullet character we're looking for
BULLET_CHAR = "⏺"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if LOG_FILE:
    handler = logging.FileHandler(LOG_FILE)
    logger.addHandler(handler)


def classify_color(r: int, g: int, b: int) -> str:
    """
    Classify an RGB color into response type.

    Returns:
        'success' (green), 'error' (red), 'warning' (yellow), 'neutral' (white/other)
    """
    # Normalize to 0-255 if needed
    if isinstance(r, float):
        r, g, b = int(r * 255), int(g * 255), int(b * 255)

    # Check for green (success)
    if g > 150 and g > r * 1.5 and g > b * 1.5:
        return "success"

    # Check for red (error)
    if r > 150 and r > g * 1.5 and r > b * 1.5:
        return "error"

    # Check for yellow (warning/in-progress)
    if r > 150 and g > 150 and b < 100:
        return "warning"

    # Default to neutral (white/other)
    return "neutral"


def extract_tool_name(first_line: str) -> Optional[str]:
    """
    Extract tool name from a line like "⏺ iterm-html-dashboard - read_sessions (MCP)"

    Returns tool name or None if not a tool call.
    """
    if " - " in first_line and "(" in first_line:
        # Format: "⏺ tool-name - action (type)"
        parts = first_line.split(" - ", 1)
        if len(parts) >= 1:
            tool_part = parts[0].replace(BULLET_CHAR, "").strip()
            return tool_part
    return None


def is_tool_call(first_line: str) -> bool:
    """Check if this line represents a tool call."""
    # Tool calls have format: "⏺ name(" or "⏺ name - action (MCP)"
    clean = first_line.replace(BULLET_CHAR, "").strip()
    # Check for "word(" pattern (tool invocation)
    if "(" in clean:
        before_paren = clean.split("(")[0].strip()
        # Should be a single word or word-with-dashes
        if " " not in before_paren or " - " in clean:
            return True
    return False


async def get_response_content(
    session: iterm2.Session,
    start_line: int,
) -> Tuple[str, str, Optional[str]]:
    """
    Capture response content from start_line until blank line.

    Returns:
        (first_line, full_content, response_type)
    """
    contents = await session.async_get_screen_contents()
    lines = []
    first_line = ""
    response_type = "neutral"

    # Read from start_line forward until blank line
    for i in range(start_line, contents.number_of_lines):
        line = contents.line(i)
        text = line.string.rstrip()

        if i == start_line:
            first_line = text
            # Try to detect color from the first character (the bullet)
            # Note: This requires style information which may not be available
            # in all iTerm2 API versions

        if not text:  # Blank line - stop capturing
            break

        lines.append(text)

    full_content = "\n".join(lines)

    # Classify based on content if we couldn't get color
    if is_tool_call(first_line):
        response_type = "tool"

    return first_line, full_content, response_type


async def find_bullet_line(session: iterm2.Session) -> Optional[int]:
    """
    Find the line number of the most recent bullet character.

    Searches backwards from the cursor position.
    """
    contents = await session.async_get_screen_contents()
    cursor = contents.cursor_coord

    # Search backwards from cursor
    for i in range(cursor.y, -1, -1):
        line = contents.line(i)
        if BULLET_CHAR in line.string:
            return i

    return None


async def post_to_dashboard(
    agent_name: Optional[str],
    session_id: str,
    response_type: str,
    first_line: str,
    full_content: str,
    tool_name: Optional[str] = None,
) -> bool:
    """Post captured response to dashboard API."""
    try:
        data = {
            "agent_name": agent_name,
            "session_id": session_id,
            "response_type": response_type,
            "first_line": first_line,
            "full_content": full_content,
            "tool_name": tool_name,
        }

        req = urllib.request.Request(
            DASHBOARD_API_URL,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            logger.info(f"Posted to dashboard: {result}")
            return result.get("success", False)

    except urllib.error.URLError as e:
        logger.warning(f"Could not post to dashboard (server may not be running): {e}")
        return False
    except Exception as e:
        logger.error(f"Error posting to dashboard: {e}")
        return False


async def capture_claude_response(session_id: str) -> str:
    """
    Main function called by iTerm2 trigger.

    Captures the Claude response starting from the bullet character,
    detects color/type, and posts to the dashboard API.
    """
    try:
        connection = await iterm2.Connection.async_create()
        app = await iterm2.async_get_app(connection)

        # Find the session
        session = app.get_session_by_id(session_id)
        if not session:
            return f"Session not found: {session_id}"

        # Find the bullet line
        bullet_line = await find_bullet_line(session)
        if bullet_line is None:
            return "No bullet character found"

        # Get the response content
        first_line, full_content, response_type = await get_response_content(
            session, bullet_line
        )

        # Extract tool name if applicable
        tool_name = extract_tool_name(first_line) if response_type == "tool" else None

        # Try to get agent name from session name or window title
        agent_name = None
        # Convention: session names may contain agent info
        # This is a placeholder - customize based on your naming convention

        # Post to dashboard
        success = await post_to_dashboard(
            agent_name=agent_name,
            session_id=session_id,
            response_type=response_type,
            first_line=first_line,
            full_content=full_content,
            tool_name=tool_name,
        )

        status = "posted" if success else "logged locally"
        return f"Captured {response_type} response ({status}): {first_line[:50]}..."

    except Exception as e:
        logger.error(f"Error in capture_claude_response: {e}")
        return f"Error: {e}"


async def main(connection: iterm2.Connection):
    """Main entry point for iTerm2 script."""

    # Register the RPC function
    @iterm2.RPC
    async def capture_claude_response_rpc(session_id: str) -> str:
        """RPC wrapper for capture_claude_response."""
        return await capture_claude_response(session_id)

    # Register with iTerm2
    await capture_claude_response_rpc.async_register(connection)

    logger.info("Claude response capture script registered with iTerm2")

    # Keep the script running
    async with connection:
        await connection.async_run_until_complete()


if __name__ == "__main__":
    # When run directly (not as iTerm2 script), test the functions
    print("iTerm2 Claude Response Capture Script")
    print("=====================================")
    print()
    print("To install:")
    print("  1. Copy to ~/Library/Application Support/iTerm2/Scripts/")
    print("  2. Or run: Scripts > capture_claude_response.py from iTerm2 menu")
    print()
    print("To use with triggers:")
    print("  Regex: ^⏺ ")
    print("  Action: Invoke Script Function")
    print("  Parameter: capture_claude_response_rpc(session.id)")
    print()

    # Run as iTerm2 script
    iterm2.run_forever(main)
