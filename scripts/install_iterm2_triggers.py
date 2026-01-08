#!/usr/bin/env python3
"""
Install iTerm2 triggers and scripts for Claude response capture.

This script:
1. Creates symlink to the capture script in iTerm2 Scripts directory
2. Outputs trigger configurations you can add to your iTerm2 profile

Usage:
    python install_iterm2_triggers.py
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CAPTURE_SCRIPT = SCRIPT_DIR / "iterm2_capture_response.py"
ITERM2_SCRIPTS_DIR = Path.home() / "Library" / "Application Support" / "iTerm2" / "Scripts"


def install_script():
    """Install the capture script to iTerm2 Scripts directory."""
    print("Installing iTerm2 capture script...")

    # Create Scripts directory if needed
    ITERM2_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # Create symlink (use try/except to avoid TOCTOU race condition)
    target = ITERM2_SCRIPTS_DIR / "capture_claude_response.py"

    try:
        target.unlink()
        print(f"  Removed existing: {target}")
    except FileNotFoundError:
        pass  # File didn't exist, that's fine

    target.symlink_to(CAPTURE_SCRIPT)
    print(f"  Created symlink: {target} -> {CAPTURE_SCRIPT}")


def print_trigger_config():
    """Print the trigger configurations for iTerm2."""
    print()
    print("=" * 70)
    print("iTerm2 TRIGGER CONFIGURATION")
    print("=" * 70)
    print()
    print("Add these triggers in: Preferences > Profiles > Advanced > Triggers")
    print()
    print("-" * 70)
    print("TRIGGER 1: Capture Claude Responses (via Script Function)")
    print("-" * 70)
    print("  Regex:     ^⏺ ")
    print("  Action:    Invoke Script Function")
    print("  Parameter: capture_claude_response_rpc(session.id)")
    print("  Instant:   No")
    print()
    print("-" * 70)
    print("TRIGGER 2: Set Mark on Response Start")
    print("-" * 70)
    print("  Regex:     ^⏺ ")
    print("  Action:    Set Mark")
    print("  Parameter: (leave empty)")
    print("  Instant:   No")
    print()
    print("-" * 70)
    print("TRIGGER 3: Capture Output (for Toolbelt sidebar)")
    print("-" * 70)
    print("  Regex:     ^⏺ (.+)")
    print("  Action:    Capture Output")
    print("  Parameter: (leave empty or set double-click action)")
    print("  Instant:   No")
    print()
    print("-" * 70)
    print("TRIGGER 4: Highlight Errors (red dots)")
    print("-" * 70)
    print("  Regex:     ^⏺.*([Ee]rror|[Ff]ailed|Exception)")
    print("  Action:    Highlight Text")
    print("  Parameter: (choose red color)")
    print("  Instant:   No")
    print()
    print("-" * 70)
    print("TRIGGER 5: Post Notification on Error")
    print("-" * 70)
    print("  Regex:     ^⏺.*([Ee]rror|[Ff]ailed|Exception)")
    print("  Action:    Post Notification")
    print("  Parameter: Claude Error")
    print("  Instant:   No")
    print()
    print("=" * 70)
    print("NAVIGATION")
    print("=" * 70)
    print()
    print("After adding triggers, you can navigate between marks with:")
    print("  - Cmd+Shift+Up   : Jump to previous mark")
    print("  - Cmd+Shift+Down : Jump to next mark")
    print()
    print("View captured output in: View > Show Toolbelt > Captured Output")
    print()


def print_dashboard_info():
    """Print info about the dashboard integration."""
    print("=" * 70)
    print("DASHBOARD INTEGRATION")
    print("=" * 70)
    print()
    print("The capture script posts responses to: http://localhost:9999/api/db/responses")
    print()
    print("Query endpoints available:")
    print("  GET  /api/db/responses     - List captured responses")
    print("  GET  /api/db/responses?type=error  - Filter by type")
    print("  GET  /api/db/responses?agent=X     - Filter by agent")
    print("  GET  /api/db/stats         - Aggregated statistics")
    print("  GET  /api/db/search?q=text - Full-text search")
    print()
    print("Start the dashboard with the MCP tool: start_telemetry_dashboard")
    print()


def check_iterm2_api():
    """Check if iTerm2 Python API is installed."""
    try:
        import iterm2
        print(f"iTerm2 Python API: installed (version {iterm2.__version__})")
        return True
    except ImportError:
        print("iTerm2 Python API: NOT INSTALLED")
        print()
        print("Install with: pip install iterm2")
        return False


def main():
    print()
    print("iTerm2 Claude Response Capture - Installation")
    print("=" * 70)
    print()

    # Check prerequisites
    print("Checking prerequisites...")
    api_ok = check_iterm2_api()

    if not api_ok:
        print()
        print("Please install the iTerm2 Python API first:")
        print("  pip install iterm2")
        print()
        sys.exit(1)

    print()

    # Install script
    install_script()

    # Print configurations
    print_trigger_config()
    print_dashboard_info()

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("1. Open iTerm2 Preferences > Profiles > Advanced > Triggers")
    print("2. Add the triggers shown above")
    print("3. Enable the capture script: Scripts > capture_claude_response.py")
    print("4. Start the dashboard: start_telemetry_dashboard (via MCP)")
    print("5. Use Claude and watch responses get captured!")
    print()


if __name__ == "__main__":
    main()
