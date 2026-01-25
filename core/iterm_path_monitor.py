"""iTerm2 path monitoring and session variable integration.

This module provides the iTerm2 Python API integration for monitoring
session path variables and applying visual styling based on repo configuration.

Uses iTerm2's VariableMonitor to detect path changes and EachSessionOnceMonitor
to automatically handle new sessions.

Key iTerm2 variables used:
- `path` - Current working directory
- `id` - Session identifier
- `user.*` - User-defined variables for custom state
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import iterm2

from .agent_hooks import (
    AgentHookManager,
    HookActionResult,
    SessionStyle,
    get_agent_hook_manager,
)

logger = logging.getLogger("iterm-mcp.path_monitor")


class PathMonitor:
    """Monitors iTerm2 session path variables for directory changes.

    Uses iTerm2's VariableMonitor to detect when the `path` variable changes,
    then triggers agent hooks for team assignment and styling.
    """

    def __init__(
        self,
        connection: "iterm2.Connection",
        hook_manager: Optional[AgentHookManager] = None,
        on_style_change: Optional[Callable[[str, SessionStyle], Coroutine[Any, Any, None]]] = None,
    ):
        """Initialize the PathMonitor.

        Args:
            connection: Active iTerm2 connection.
            hook_manager: AgentHookManager instance. Uses global if not provided.
            on_style_change: Callback when styling should be applied.
        """
        self.connection = connection
        self.hook_manager = hook_manager or get_agent_hook_manager()
        self.on_style_change = on_style_change

        # Track active monitoring tasks per session
        self._monitor_tasks: Dict[str, asyncio.Task] = {}

        # Track if monitoring is active
        self._is_running = False

    async def start(self) -> None:
        """Start monitoring all sessions for path changes.

        Uses EachSessionOnceMonitor to automatically handle existing
        and future sessions.
        """
        import iterm2

        self._is_running = True

        async def monitor_session(session_id: str) -> None:
            """Monitor a single session for path changes."""
            try:
                async with iterm2.VariableMonitor(
                    self.connection,
                    iterm2.VariableScopes.SESSION,
                    "path",
                    session_id
                ) as mon:
                    while self._is_running:
                        new_path = await mon.async_get()
                        await self._handle_path_change(session_id, new_path)
            except asyncio.CancelledError:
                logger.debug(f"Path monitor cancelled for session {session_id}")
            except Exception as e:
                logger.error(f"Error monitoring session {session_id}: {e}")

        async def on_session(session_id: str) -> None:
            """Called once per session (existing and new)."""
            logger.info(f"Starting path monitor for session {session_id}")
            task = asyncio.create_task(monitor_session(session_id))
            self._monitor_tasks[session_id] = task

        # Start monitoring all sessions
        await iterm2.EachSessionOnceMonitor.async_foreach_session_create_task(
            self.connection,
            on_session
        )

    async def stop(self) -> None:
        """Stop all path monitoring."""
        self._is_running = False

        # Cancel all monitoring tasks
        for session_id, task in self._monitor_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    # Task cancellation is expected during shutdown; ignore.
                    pass

        self._monitor_tasks.clear()
        logger.info("Path monitoring stopped")

    async def _handle_path_change(
        self,
        session_id: str,
        new_path: str
    ) -> HookActionResult:
        """Handle a path change in a session.

        Args:
            session_id: The iTerm session ID.
            new_path: The new working directory.

        Returns:
            HookActionResult from the hook manager.
        """
        logger.debug(f"Path changed in {session_id}: {new_path}")

        # Get agent name if registered
        agent_name = await self._get_agent_name(session_id)

        # Process through hook manager
        result = await self.hook_manager.on_path_changed(
            session_id, new_path, agent_name
        )

        # Apply styling if configured
        if result.style_applied and self.on_style_change:
            repo_root = self.hook_manager.find_repo_root(new_path)
            if repo_root:
                repo_config = self.hook_manager.load_repo_config(repo_root)
                if repo_config and repo_config.style:
                    await self.on_style_change(session_id, repo_config.style)

        # Handle team assignment
        if result.team_assigned:
            await self._assign_to_team(session_id, agent_name, result.team_assigned)

        # Handle session ID pass-through
        if result.session_id_passed:
            await self._set_session_id_variable(session_id, new_path)

        return result

    async def _get_agent_name(self, session_id: str) -> Optional[str]:
        """Get the agent name for a session if registered.

        Args:
            session_id: The iTerm session ID.

        Returns:
            Agent name if found, None otherwise.
        """
        if self.hook_manager.agent_registry:
            agent = self.hook_manager.agent_registry.get_agent_by_session(session_id)
            if agent:
                return agent.name
        return None

    async def _assign_to_team(
        self,
        session_id: str,
        agent_name: Optional[str],
        team_name: str
    ) -> None:
        """Assign an agent to a team.

        Args:
            session_id: The iTerm session ID.
            agent_name: The agent's name (if known).
            team_name: The team to assign to.
        """
        if not self.hook_manager.agent_registry:
            logger.warning("No agent registry available for team assignment")
            return

        registry = self.hook_manager.agent_registry

        # Ensure team exists using public API
        team = registry.get_team(team_name)
        if not team:
            registry.create_team(team_name, "Auto-created for repo")

        # If we know the agent, add to team using public API
        if agent_name:
            agent = registry.get_agent(agent_name)
            if agent and team_name not in agent.teams:
                registry.assign_to_team(agent_name, team_name)
                logger.info(f"Assigned agent {agent_name} to team {team_name}")

    async def _set_session_id_variable(
        self,
        session_id: str,
        path: str
    ) -> None:
        """Set the session ID as an iTerm2 user variable.

        This allows the session ID to be passed to Claude Code via
        environment variable or shell integration.

        Args:
            session_id: The iTerm session ID.
            path: Current working directory.
        """
        import iterm2

        try:
            app = await iterm2.async_get_app(self.connection)

            # Find the session
            session = app.get_session_by_id(session_id)
            if session:
                # Set user variable for session ID
                await session.async_set_variable(
                    "user.claude_session_id",
                    session_id
                )

                # Also set repo-specific env var name if configured
                repo_root = self.hook_manager.find_repo_root(path)
                if repo_root:
                    repo_config = self.hook_manager.load_repo_config(repo_root)
                    if repo_config:
                        env_var_name = repo_config.claude_session_id_env
                        await session.async_set_variable(
                            f"user.{env_var_name.lower()}",
                            session_id
                        )

                logger.debug(f"Set session ID variable for {session_id}")

        except Exception as e:
            logger.error(f"Failed to set session ID variable: {e}")


async def apply_session_style(
    connection: "iterm2.Connection",
    session_id: str,
    style: SessionStyle,
    repo_name: Optional[str] = None,
    team_name: Optional[str] = None,
) -> bool:
    """Apply visual styling to a session.

    Args:
        connection: Active iTerm2 connection.
        session_id: The iTerm session ID.
        style: SessionStyle configuration to apply.
        repo_name: Optional repo name for badge interpolation.
        team_name: Optional team name for badge interpolation.

    Returns:
        True if styling was applied successfully.
    """
    import iterm2

    try:
        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found")
            return False

        # Use LocalWriteOnlyProfile to apply changes to this session only
        # without affecting the underlying profile (per-session styling)
        profile = iterm2.LocalWriteOnlyProfile()

        # Apply background color
        if style.background_color:
            color = iterm2.Color(
                style.background_color.r,
                style.background_color.g,
                style.background_color.b,
                style.background_color.a
            )
            profile.set_background_color(color)

        # Apply tab color
        if style.tab_color:
            color = iterm2.Color(
                style.tab_color.r,
                style.tab_color.g,
                style.tab_color.b,
            )
            profile.set_tab_color(color)
            profile.set_use_tab_color(True)

        # Apply cursor color
        if style.cursor_color:
            color = iterm2.Color(
                style.cursor_color.r,
                style.cursor_color.g,
                style.cursor_color.b,
            )
            profile.set_cursor_color(color)

        # Apply background image
        if style.background_image:
            profile.set_background_image_location(style.background_image)

        # Apply badge
        if style.badge:
            badge_text = style.badge
            # Interpolate variables
            if repo_name:
                badge_text = badge_text.replace("{repo}", repo_name)
            if team_name:
                badge_text = badge_text.replace("{team}", team_name)
            profile.set_badge_text(badge_text)

        # Apply the profile changes to this session only
        await session.async_set_profile_properties(profile)

        # Apply profile if specified (full profile switch)
        if style.profile:
            profiles = await iterm2.PartialProfile.async_query(connection)
            for p in profiles:
                if p.name == style.profile:
                    await session.async_set_profile(p)
                    break

        logger.info(f"Applied styling to session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply styling to {session_id}: {e}")
        return False


async def get_session_path(
    connection: "iterm2.Connection",
    session_id: str
) -> Optional[str]:
    """Get the current working directory for a session.

    Args:
        connection: Active iTerm2 connection.
        session_id: The iTerm session ID.

    Returns:
        Current path if available, None otherwise.
    """
    import iterm2

    try:
        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)

        if session:
            return await session.async_get_variable("path")

    except Exception as e:
        logger.error(f"Failed to get path for {session_id}: {e}")

    return None


async def set_user_variable(
    connection: "iterm2.Connection",
    session_id: str,
    name: str,
    value: str
) -> bool:
    """Set a user variable on a session.

    User variables can be accessed as environment variables or in
    badge/title templates.

    Args:
        connection: Active iTerm2 connection.
        session_id: The iTerm session ID.
        name: Variable name (will be prefixed with "user.")
        value: Variable value.

    Returns:
        True if set successfully.
    """
    import iterm2

    try:
        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)

        if session:
            var_name = f"user.{name}" if not name.startswith("user.") else name
            await session.async_set_variable(var_name, value)
            return True

    except Exception as e:
        logger.error(f"Failed to set variable {name} on {session_id}: {e}")

    return False


async def get_user_variable(
    connection: "iterm2.Connection",
    session_id: str,
    name: str
) -> Optional[str]:
    """Get a user variable from a session.

    Args:
        connection: Active iTerm2 connection.
        session_id: The iTerm session ID.
        name: Variable name.

    Returns:
        Variable value if found, None otherwise.
    """
    import iterm2

    try:
        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)

        if session:
            var_name = f"user.{name}" if not name.startswith("user.") else name
            return await session.async_get_variable(var_name)

    except Exception as e:
        logger.error(f"Failed to get variable {name} from {session_id}: {e}")

    return None
