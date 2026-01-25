"""Agent lifecycle hooks for repo-based team assignment and styling.

This module provides hooks that trigger when agents start or change directories,
automatically assigning them to repo-based teams and applying visual styling.

Key features:
- Monitor session `path` variable for directory changes
- Load per-repo `.iterm/hooks.json` configuration
- Auto-assign agents to teams based on working directory
- Apply visual styling (background color, tab color, badge)
- Pass iTerm Session ID to Claude Code for consistent tracking

Configuration hierarchy:
- Global: ~/.iterm-mcp/hooks/
- Per-repo: .iterm/hooks.json (only checked if exists)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .agents import AgentRegistry


# ============================================================================
# SESSION ID PATTERNS
# ============================================================================

# Precompiled UUID pattern for efficient session ID validation
# Both iTerm session IDs and Claude session IDs use standard UUID format
# Examples: "550e8400-e29b-41d4-a716-446655440000", "f9a88c53-2c5f-405c-a2f7-0907bf35e318"
SESSION_ID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

# Pattern for finding session IDs in text (logs, output, etc.)
SESSION_ID_SEARCH_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE
)


def is_valid_session_id(session_id: str) -> bool:
    """Check if a string is a valid UUID session ID.

    Args:
        session_id: The string to validate.

    Returns:
        True if valid UUID format, False otherwise.
    """
    return bool(SESSION_ID_PATTERN.match(session_id))


def extract_session_ids(text: str) -> List[str]:
    """Extract all session IDs from text.

    Args:
        text: The text to search.

    Returns:
        List of found session IDs (lowercase).
    """
    return [match.lower() for match in SESSION_ID_SEARCH_PATTERN.findall(text)]


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================

class ColorSpec(BaseModel):
    """RGB color specification."""
    r: int = Field(..., ge=0, le=255, alias="red", description="Red component")
    g: int = Field(..., ge=0, le=255, alias="green", description="Green component")
    b: int = Field(..., ge=0, le=255, alias="blue", description="Blue component")
    a: int = Field(default=255, ge=0, le=255, alias="alpha", description="Alpha component")

    model_config = {"populate_by_name": True}


class SessionStyle(BaseModel):
    """Visual styling configuration for a session."""

    background_color: Optional[ColorSpec] = Field(
        default=None,
        description="Background color for the session"
    )
    background_image: Optional[str] = Field(
        default=None,
        description="Path to background image"
    )
    tab_color: Optional[ColorSpec] = Field(
        default=None,
        description="Tab color for visual identification"
    )
    cursor_color: Optional[ColorSpec] = Field(
        default=None,
        description="Cursor color"
    )
    badge: Optional[str] = Field(
        default=None,
        description="Badge text to display (supports variables like {team}, {repo})"
    )
    profile: Optional[str] = Field(
        default=None,
        description="iTerm2 profile name to apply"
    )


class RepoHooksConfig(BaseModel):
    """Per-repository hooks configuration (.iterm/hooks.json)."""

    team: Optional[str] = Field(
        default=None,
        description="Team name to auto-assign agents to"
    )
    style: Optional[SessionStyle] = Field(
        default=None,
        description="Visual styling to apply"
    )
    auto_services: List[str] = Field(
        default_factory=list,
        description="Services to auto-start when agent enters repo"
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set via iTerm2 variables"
    )
    on_enter: Optional[str] = Field(
        default=None,
        description="Command to run when agent enters repo"
    )
    on_exit: Optional[str] = Field(
        default=None,
        description="Command to run when agent leaves repo"
    )
    claude_session_id_env: str = Field(
        default="CLAUDE_SESSION_ID",
        description="Env var name to set with iTerm session ID"
    )
    pass_session_id: bool = Field(
        default=True,
        description="Whether to pass iTerm session ID to Claude Code"
    )


class GlobalHooksConfig(BaseModel):
    """Global hooks configuration (~/.iterm-mcp/hooks/config.json)."""

    enabled: bool = Field(default=True, description="Master switch for hooks")
    monitor_path_changes: bool = Field(
        default=True,
        description="Monitor session path variable for directory changes"
    )
    auto_team_assignment: bool = Field(
        default=True,
        description="Automatically assign agents to teams based on repo"
    )
    default_style: Optional[SessionStyle] = Field(
        default=None,
        description="Default styling for all agents"
    )
    repo_config_filename: str = Field(
        default=".iterm/hooks.json",
        description="Filename to look for in repos"
    )
    fallback_team_from_repo: bool = Field(
        default=True,
        description="Use repo name as team name if no team configured"
    )
    pass_session_id_default: bool = Field(
        default=True,
        description="Default for passing session ID to Claude"
    )


# ============================================================================
# HOOK EVENTS
# ============================================================================

class HookEventType(str, Enum):
    """Types of hook events."""
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    DIRECTORY_CHANGED = "directory_changed"
    TEAM_ASSIGNED = "team_assigned"
    STYLE_APPLIED = "style_applied"
    SESSION_ID_PASSED = "session_id_passed"


@dataclass
class HookEvent:
    """Represents a hook event with context."""

    event_type: HookEventType
    session_id: str
    agent_name: Optional[str] = None
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    team_name: Optional[str] = None
    repo_config: Optional[RepoHooksConfig] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookActionResult:
    """Result of a hook action."""

    success: bool = True
    actions_taken: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    team_assigned: Optional[str] = None
    style_applied: bool = False
    session_id_passed: bool = False
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "actions_taken": self.actions_taken,
            "errors": self.errors,
            "team_assigned": self.team_assigned,
            "style_applied": self.style_applied,
            "session_id_passed": self.session_id_passed,
            "message": self.message,
        }


# ============================================================================
# HOOK MANAGER
# ============================================================================

# Type for hook callbacks
HookCallback = Callable[[HookEvent], Coroutine[Any, Any, None]]


class AgentHookManager:
    """Manages agent lifecycle hooks for repo-based integration.

    Monitors session path changes and triggers hooks for:
    - Auto-team assignment based on working directory
    - Visual styling from per-repo configuration
    - Session ID pass-through to Claude Code
    """

    def __init__(
        self,
        config: Optional[GlobalHooksConfig] = None,
        agent_registry: Optional["AgentRegistry"] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the AgentHookManager.

        Args:
            config: Global hooks configuration. If not provided, loads from file.
            agent_registry: Agent registry for team assignment.
            logger: Optional logger instance.
        """
        self.config = config or self._load_global_config()
        self.agent_registry = agent_registry
        self.logger = logger or logging.getLogger("iterm-mcp.agent_hooks")

        # Track current path per session to detect changes
        self._session_paths: Dict[str, str] = {}

        # Cache for loaded repo configs
        self._repo_config_cache: Dict[str, Optional[RepoHooksConfig]] = {}

        # Registered callbacks for hook events
        self._callbacks: Dict[HookEventType, List[HookCallback]] = {
            event_type: [] for event_type in HookEventType
        }

    def _load_global_config(self) -> GlobalHooksConfig:
        """Load global configuration from ~/.iterm-mcp/hooks/config.json."""
        config_path = Path(os.path.expanduser("~/.iterm-mcp/hooks/config.json"))

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                return GlobalHooksConfig(**data)
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"Failed to load global hooks config: {e}")

        return GlobalHooksConfig()

    def save_global_config(self) -> None:
        """Save global configuration to file."""
        config_dir = Path(os.path.expanduser("~/.iterm-mcp/hooks"))
        config_dir.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / "config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config.model_dump(), f, indent=2)

    def register_callback(
        self,
        event_type: HookEventType,
        callback: HookCallback
    ) -> None:
        """Register a callback for a hook event type.

        Args:
            event_type: The event type to listen for.
            callback: Async function to call when event occurs.
        """
        self._callbacks[event_type].append(callback)

    async def _emit_event(self, event: HookEvent) -> None:
        """Emit a hook event to all registered callbacks.

        Args:
            event: The hook event to emit.
        """
        for callback in self._callbacks[event.event_type]:
            try:
                await callback(event)
            except Exception as e:
                self.logger.error(f"Error in hook callback: {e}")

    def load_repo_config(self, repo_path: str) -> Optional[RepoHooksConfig]:
        """Load hooks configuration from a repository.

        Args:
            repo_path: Path to the repository root.

        Returns:
            RepoHooksConfig if found, None otherwise.
        """
        # Check cache first
        if repo_path in self._repo_config_cache:
            return self._repo_config_cache[repo_path]

        config_path = Path(repo_path) / self.config.repo_config_filename

        if not config_path.exists():
            self._repo_config_cache[repo_path] = None
            return None

        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            config = RepoHooksConfig(**data)
            self._repo_config_cache[repo_path] = config
            return config
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"Failed to load repo config from {config_path}: {e}")
            self._repo_config_cache[repo_path] = None
            return None

    def find_repo_root(self, path: str) -> Optional[str]:
        """Find the git repository root containing a path.

        Args:
            path: Path to search from.

        Returns:
            Repository root path if found, None otherwise.
        """
        current = Path(path).resolve()

        while current != current.parent:
            if (current / ".git").exists():
                return str(current)
            # Also check for .iterm directory as repo marker
            if (current / ".iterm").is_dir():
                return str(current)
            current = current.parent

        return None

    def get_team_for_repo(self, repo_path: str) -> Optional[str]:
        """Determine team name for a repository.

        Priority:
        1. Explicit team in .iterm/hooks.json
        2. Repo directory name (if fallback_team_from_repo enabled)

        Args:
            repo_path: Path to the repository.

        Returns:
            Team name if determinable, None otherwise.
        """
        repo_config = self.load_repo_config(repo_path)

        if repo_config and repo_config.team:
            return repo_config.team

        if self.config.fallback_team_from_repo:
            return Path(repo_path).name

        return None

    async def on_path_changed(
        self,
        session_id: str,
        new_path: str,
        agent_name: Optional[str] = None,
    ) -> HookActionResult:
        """Handle a session path change.

        This is the main entry point for path-based hooks. Call this when
        the session's `path` variable changes.

        Args:
            session_id: The iTerm session ID.
            new_path: The new working directory path.
            agent_name: Optional agent name if known.

        Returns:
            HookActionResult with actions taken.
        """
        result = HookActionResult()

        if not self.config.enabled:
            result.message = "Hooks disabled"
            return result

        old_path = self._session_paths.get(session_id)
        self._session_paths[session_id] = new_path

        # Find repo roots
        old_repo = self.find_repo_root(old_path) if old_path else None
        new_repo = self.find_repo_root(new_path)

        # Emit directory changed event
        await self._emit_event(HookEvent(
            event_type=HookEventType.DIRECTORY_CHANGED,
            session_id=session_id,
            agent_name=agent_name,
            old_path=old_path,
            new_path=new_path,
        ))

        # If repo changed, handle transition
        if new_repo != old_repo:
            # Handle leaving old repo
            if old_repo:
                old_config = self.load_repo_config(old_repo)
                if old_config and old_config.on_exit:
                    result.actions_taken.append(f"on_exit: {old_config.on_exit}")
                    # Note: Actual command execution would be done by caller

            # Handle entering new repo
            if new_repo:
                new_config = self.load_repo_config(new_repo)

                # Auto-assign to team
                if self.config.auto_team_assignment:
                    team_name = self.get_team_for_repo(new_repo)
                    if team_name:
                        result.team_assigned = team_name
                        result.actions_taken.append(f"team_assigned: {team_name}")

                        await self._emit_event(HookEvent(
                            event_type=HookEventType.TEAM_ASSIGNED,
                            session_id=session_id,
                            agent_name=agent_name,
                            new_path=new_path,
                            team_name=team_name,
                            repo_config=new_config,
                        ))

                # Apply styling
                if new_config and new_config.style:
                    result.style_applied = True
                    result.actions_taken.append("style_applied")

                    await self._emit_event(HookEvent(
                        event_type=HookEventType.STYLE_APPLIED,
                        session_id=session_id,
                        agent_name=agent_name,
                        new_path=new_path,
                        repo_config=new_config,
                    ))

                # Pass session ID
                pass_session_id = (
                    new_config.pass_session_id
                    if new_config else self.config.pass_session_id_default
                )
                if pass_session_id:
                    result.session_id_passed = True
                    result.actions_taken.append(f"session_id_passed: {session_id}")

                    await self._emit_event(HookEvent(
                        event_type=HookEventType.SESSION_ID_PASSED,
                        session_id=session_id,
                        agent_name=agent_name,
                        new_path=new_path,
                        repo_config=new_config,
                        context={"session_id": session_id},
                    ))

                # Handle on_enter
                if new_config and new_config.on_enter:
                    result.actions_taken.append(f"on_enter: {new_config.on_enter}")

        result.message = f"Path changed: {old_path} -> {new_path}"
        return result

    async def on_agent_started(
        self,
        session_id: str,
        agent_name: str,
        initial_path: Optional[str] = None,
    ) -> HookActionResult:
        """Handle an agent starting up.

        Called when an agent is registered. Triggers initial path-based hooks.

        Args:
            session_id: The iTerm session ID.
            agent_name: The agent's name.
            initial_path: Initial working directory if known.

        Returns:
            HookActionResult with actions taken.
        """
        result = HookActionResult()

        await self._emit_event(HookEvent(
            event_type=HookEventType.AGENT_STARTED,
            session_id=session_id,
            agent_name=agent_name,
            new_path=initial_path,
        ))

        # If we have an initial path, process it
        if initial_path:
            result = await self.on_path_changed(session_id, initial_path, agent_name)

        return result

    async def on_agent_stopped(
        self,
        session_id: str,
        agent_name: str,
    ) -> HookActionResult:
        """Handle an agent stopping.

        Called when an agent is unregistered. Cleans up state.

        Args:
            session_id: The iTerm session ID.
            agent_name: The agent's name.

        Returns:
            HookActionResult with actions taken.
        """
        result = HookActionResult()

        # Clean up tracked path
        old_path = self._session_paths.pop(session_id, None)

        # Handle on_exit for current repo
        if old_path:
            repo_root = self.find_repo_root(old_path)
            if repo_root:
                repo_config = self.load_repo_config(repo_root)
                if repo_config and repo_config.on_exit:
                    result.actions_taken.append(f"on_exit: {repo_config.on_exit}")

        await self._emit_event(HookEvent(
            event_type=HookEventType.AGENT_STOPPED,
            session_id=session_id,
            agent_name=agent_name,
            old_path=old_path,
        ))

        result.message = f"Agent {agent_name} stopped"
        return result

    def clear_cache(self, repo_path: Optional[str] = None) -> None:
        """Clear the repo config cache.

        Args:
            repo_path: Specific repo to clear, or None to clear all.
        """
        if repo_path:
            self._repo_config_cache.pop(repo_path, None)
        else:
            self._repo_config_cache.clear()

    def get_session_path(self, session_id: str) -> Optional[str]:
        """Get the tracked path for a session.

        Args:
            session_id: The iTerm session ID.

        Returns:
            Current path if tracked, None otherwise.
        """
        return self._session_paths.get(session_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the hook manager.

        Returns:
            Dict with tracked sessions, cached configs, etc.
        """
        return {
            "enabled": self.config.enabled,
            "tracked_sessions": len(self._session_paths),
            "cached_repo_configs": len(self._repo_config_cache),
            "sessions": list(self._session_paths.keys()),
        }


# ============================================================================
# MODULE-LEVEL INSTANCE
# ============================================================================

_agent_hook_manager: Optional[AgentHookManager] = None


def get_agent_hook_manager(
    config: Optional[GlobalHooksConfig] = None,
    agent_registry: Optional["AgentRegistry"] = None,
    logger: Optional[logging.Logger] = None,
) -> AgentHookManager:
    """Get or create the global AgentHookManager instance.

    Args:
        config: Global hooks configuration.
        agent_registry: Agent registry for team assignment.
        logger: Optional logger instance.

    Returns:
        AgentHookManager instance.
    """
    global _agent_hook_manager
    if _agent_hook_manager is None:
        _agent_hook_manager = AgentHookManager(config, agent_registry, logger)
    return _agent_hook_manager


def reset_agent_hook_manager() -> None:
    """Reset the global AgentHookManager instance (for testing)."""
    global _agent_hook_manager
    _agent_hook_manager = None
