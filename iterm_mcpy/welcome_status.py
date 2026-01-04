"""Welcome status display for iTerm2 sessions.

This module provides a welcome script that shows service status
when new sessions are started in a repository context.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import iterm2
    ITERM2_AVAILABLE = True
except ImportError:
    ITERM2_AVAILABLE = False

from core.services import (
    ServiceConfig,
    ServiceManager,
    ServicePriority,
    get_service_manager,
)


class WelcomeStatusDisplay:
    """Displays service status in iTerm2 sessions.

    Uses the iTerm2 Python API to:
    1. Find the frontmost visible window
    2. Locate idle tabs in repository subdirectories
    3. Display service status information
    """

    def __init__(
        self,
        service_manager: Optional[ServiceManager] = None,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the welcome status display.

        Args:
            service_manager: ServiceManager instance (uses global if not provided)
            logger: Optional logger instance
        """
        self.service_manager = service_manager or get_service_manager()
        self.logger = logger or logging.getLogger("iterm-mcp.welcome")

    async def find_idle_session_in_repo(
        self,
        connection: "iterm2.Connection",
        repo_path: str
    ) -> Optional["iterm2.Session"]:
        """Find an idle session whose cwd is within the repo.

        Args:
            connection: iTerm2 connection
            repo_path: Path to the repository

        Returns:
            Session if found, None otherwise
        """
        if not ITERM2_AVAILABLE:
            self.logger.warning("iTerm2 module not available")
            return None

        try:
            app = await iterm2.async_get_app(connection)
            if not app:
                return None

            # Get windows in front-to-back order
            for window in app.windows:
                # Check each tab in the window
                for tab in window.tabs:
                    for session in tab.sessions:
                        # Check if session is idle
                        try:
                            is_processing = session.is_processing
                            if is_processing:
                                continue
                        except Exception:
                            # If we can't determine, assume busy
                            continue

                        # Get session's current working directory
                        try:
                            cwd = await session.async_get_variable("path")
                            if cwd and self._is_subdirectory(cwd, repo_path):
                                return session
                        except Exception as e:
                            self.logger.debug(f"Could not get cwd for session: {e}")
                            continue

        except Exception as e:
            self.logger.error(f"Error finding idle session: {e}")

        return None

    def _is_subdirectory(self, cwd: str, repo_path: str) -> bool:
        """Check if cwd is within repo_path.

        Args:
            cwd: Current working directory
            repo_path: Repository path

        Returns:
            True if cwd is within or equal to repo_path
        """
        try:
            cwd_path = Path(cwd).resolve()
            repo_path_obj = Path(repo_path).resolve()
            return cwd_path == repo_path_obj or repo_path_obj in cwd_path.parents
        except Exception:
            return False

    async def display_status(
        self,
        session: "iterm2.Session",
        repo_path: str,
        min_priority: Optional[ServicePriority] = None
    ) -> bool:
        """Display service status in a session.

        Args:
            session: iTerm2 session to display in
            repo_path: Repository path for context
            min_priority: Minimum priority level to show

        Returns:
            True if status was displayed successfully
        """
        if not ITERM2_AVAILABLE:
            return False

        try:
            # Get services for this repo
            services = self.service_manager.get_merged_services(repo_path, min_priority)

            if not services:
                # No services configured
                return True

            # Check status of each service
            running_services: List[ServiceConfig] = []
            stopped_services: List[ServiceConfig] = []

            for service in services:
                is_running = await self.service_manager.check_service_running(service)
                if is_running:
                    running_services.append(service)
                else:
                    stopped_services.append(service)

            # Build status message
            lines = [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"  📦 Service Status for {os.path.basename(repo_path)}",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ]

            if running_services:
                lines.append("")
                lines.append("  ✅ Running:")
                for s in running_services:
                    lines.append(f"     • {s.effective_display_name} ({s.priority.value})")

            if stopped_services:
                lines.append("")
                lines.append("  ⚠️  Not Running:")
                for s in stopped_services:
                    icon = "❗" if s.priority in (ServicePriority.REQUIRED, ServicePriority.PREFERRED) else "⚪"
                    lines.append(f"     {icon} {s.effective_display_name} ({s.priority.value})")

            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                f"  {datetime.now().strftime('%H:%M:%S')}",
                "",
            ])

            message = "\n".join(lines)

            # Display in the session using ANSI escape for color (optional)
            await session.async_send_text(f"echo '{message}'\n")

            return True

        except Exception as e:
            self.logger.error(f"Error displaying status: {e}")
            return False

    async def show_welcome(
        self,
        connection: "iterm2.Connection",
        repo_path: str
    ) -> bool:
        """Show welcome status in an appropriate session.

        Finds the frontmost idle session in the repo and displays status.

        Args:
            connection: iTerm2 connection
            repo_path: Repository path

        Returns:
            True if welcome was displayed
        """
        session = await self.find_idle_session_in_repo(connection, repo_path)
        if not session:
            self.logger.debug(f"No idle session found for {repo_path}")
            return False

        return await self.display_status(session, repo_path)


def generate_initial_text_command(repo_path: str) -> str:
    """Generate the Initial Text command for iTerm profile.

    This command is run when a new session starts with the profile.
    It displays service status for the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Shell command string
    """
    # Escape the path for shell
    escaped_path = repo_path.replace("'", "'\\''")

    return f"""
# iTerm MCP Welcome Status
python3 -c "
import asyncio
import sys
sys.path.insert(0, '{escaped_path}')
try:
    import iterm2
    from iterm_mcpy.welcome_status import WelcomeStatusDisplay
    from core.services import get_service_manager

    async def show_status():
        conn = await iterm2.Connection.async_create()
        sm = get_service_manager()
        sm.load_global_config()
        wd = WelcomeStatusDisplay(sm)
        await wd.show_welcome(conn, '{escaped_path}')

    asyncio.run(show_status())
except Exception as e:
    print(f'[iterm-mcp] Welcome status: {{e}}')
" 2>/dev/null || true
unsetopt correct correctall 2>/dev/null
setopt NO_CORRECT NO_CORRECT_ALL 2>/dev/null
"""


async def run_welcome_status(repo_path: str) -> None:
    """Run the welcome status display.

    Called from the Initial Text in iTerm profile.

    Args:
        repo_path: Repository path
    """
    if not ITERM2_AVAILABLE:
        print("[iterm-mcp] iTerm2 module not available")
        return

    try:
        connection = await iterm2.Connection.async_create()
        service_manager = get_service_manager()
        service_manager.load_global_config()

        display = WelcomeStatusDisplay(service_manager)
        await display.show_welcome(connection, repo_path)

    except Exception as e:
        print(f"[iterm-mcp] Welcome status error: {e}")


def main():
    """Entry point for welcome status script."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: welcome_status.py <repo_path>")
        sys.exit(1)

    repo_path = sys.argv[1]
    asyncio.run(run_welcome_status(repo_path))


if __name__ == "__main__":
    main()
