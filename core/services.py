"""Service registry system for cross-repo service management.

This module provides:
- Service priority levels (quiet, optional, preferred, required)
- Service configuration and state models
- ServiceManager for loading configs and managing service lifecycle
"""

import fnmatch
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, field_validator, model_validator


# Default config locations
DEFAULT_PARENT_FOLDER = ".iterm-mcp"
GLOBAL_CONFIG_DIR = Path.home() / DEFAULT_PARENT_FOLDER
SERVICES_CONFIG_FILENAME = "services.json"


class ServicePriority(str, Enum):
    """Priority levels for services.

    Determines behavior during team creation:
    - quiet: No notification, not started automatically
    - optional: Notification only when inactive
    - preferred: Prompt agent before team creation
    - required: Auto-start in background before team creation
    """
    QUIET = "quiet"
    OPTIONAL = "optional"
    PREFERRED = "preferred"
    REQUIRED = "required"

    @classmethod
    def from_string(cls, value: str) -> "ServicePriority":
        """Convert string to ServicePriority, case-insensitive.

        Args:
            value: String value to convert

        Returns:
            ServicePriority enum value

        Raises:
            ValueError: If value is not a valid priority
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid = ", ".join(p.value for p in cls)
            raise ValueError(f"Invalid priority '{value}'. Must be one of: {valid}")


class ServiceConfig(BaseModel):
    """Configuration for a single service.

    Services can be defined globally or per-repo. Per-repo configs
    can override the priority of globally-defined services.
    """

    name: str = Field(..., description="Unique service identifier")
    display_name: Optional[str] = Field(
        default=None,
        description="Human-readable name (defaults to name)"
    )
    command: Optional[str] = Field(
        default=None,
        description="Command to start the service"
    )
    priority: ServicePriority = Field(
        default=ServicePriority.OPTIONAL,
        description="Service priority level"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Port the service listens on (for status checking)"
    )
    working_directory: Optional[str] = Field(
        default=None,
        description="Working directory for the service (supports ~ expansion)"
    )
    repo_patterns: List[str] = Field(
        default_factory=list,
        description="Glob patterns to match repo paths (e.g., '**/iterm-mcp*')"
    )
    profile_tag: Optional[str] = Field(
        default=None,
        description="iTerm profile tag to identify running service"
    )
    health_check: Optional[str] = Field(
        default=None,
        description="Command to check if service is healthy (exit 0 = healthy)"
    )
    environment: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the service"
    )

    @field_validator('priority', mode='before')
    @classmethod
    def convert_priority(cls, v):
        """Convert string priority to enum."""
        if isinstance(v, str):
            return ServicePriority.from_string(v)
        return v

    @field_validator('working_directory', mode='before')
    @classmethod
    def expand_path(cls, v):
        """Expand ~ and environment variables in path."""
        if v:
            return os.path.expanduser(os.path.expandvars(v))
        return v

    @property
    def effective_display_name(self) -> str:
        """Get display name, falling back to name."""
        return self.display_name or self.name

    @property
    def effective_profile_tag(self) -> str:
        """Get profile tag, falling back to service:{name}."""
        return self.profile_tag or f"service:{self.name}"

    def matches_repo(self, repo_path: str) -> bool:
        """Check if this service applies to the given repo.

        Args:
            repo_path: Path to the repository

        Returns:
            True if service applies to this repo
        """
        if not self.repo_patterns:
            # No patterns means applies to all repos
            return True

        repo_path = os.path.expanduser(repo_path)
        for pattern in self.repo_patterns:
            if fnmatch.fnmatch(repo_path, pattern):
                return True
        return False


class ServiceRegistry(BaseModel):
    """Registry of service configurations.

    Can be loaded from global config (~/.iterm-mcp/services.json)
    or per-repo config (<repo>/.iterm-mcp/services.json).
    """

    version: str = Field(default="1.0", description="Config format version")
    parent_folder: str = Field(
        default=DEFAULT_PARENT_FOLDER,
        description="Parent folder name for configs"
    )
    services: List[ServiceConfig] = Field(
        default_factory=list,
        description="List of service configurations"
    )

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get a service by name.

        Args:
            name: Service name

        Returns:
            ServiceConfig or None
        """
        for service in self.services:
            if service.name == name:
                return service
        return None

    def get_services_for_repo(
        self,
        repo_path: str,
        min_priority: Optional[ServicePriority] = None
    ) -> List[ServiceConfig]:
        """Get services that apply to a repo, filtered by minimum priority.

        Args:
            repo_path: Path to the repository
            min_priority: Minimum priority level to include

        Returns:
            List of matching ServiceConfig objects
        """
        priority_order = [
            ServicePriority.QUIET,
            ServicePriority.OPTIONAL,
            ServicePriority.PREFERRED,
            ServicePriority.REQUIRED
        ]

        results = []
        for service in self.services:
            if not service.matches_repo(repo_path):
                continue

            if min_priority:
                service_idx = priority_order.index(service.priority)
                min_idx = priority_order.index(min_priority)
                if service_idx < min_idx:
                    continue

            results.append(service)

        return results


@dataclass
class ServiceState:
    """Runtime state for a service instance."""

    service: ServiceConfig
    is_running: bool = False
    session_id: Optional[str] = None
    started_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_status: Optional[bool] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.service.name,
            "display_name": self.service.effective_display_name,
            "priority": self.service.priority.value,
            "is_running": self.is_running,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "health_status": self.health_status,
            "error_message": self.error_message,
        }


class ServiceManager:
    """Manages service configuration loading and lifecycle.

    Loads service configurations from:
    1. Global config: ~/.iterm-mcp/services.json
    2. Per-repo config: <repo>/.iterm-mcp/services.json

    Per-repo configs can override priority of globally-defined services.
    """

    def __init__(
        self,
        parent_folder: str = DEFAULT_PARENT_FOLDER,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the ServiceManager.

        Args:
            parent_folder: Name of the config folder (default: .iterm-mcp)
            logger: Optional logger instance
        """
        self.parent_folder = parent_folder
        self.logger = logger or logging.getLogger("iterm-mcp.services")

        # Cached registries
        self._global_registry: Optional[ServiceRegistry] = None
        self._repo_registries: Dict[str, ServiceRegistry] = {}

        # Runtime state
        self._service_states: Dict[str, ServiceState] = {}

        # iTerm session reference (set externally)
        self._iterm_terminal = None

    def set_terminal(self, terminal) -> None:
        """Set the iTerm terminal reference for session operations.

        Args:
            terminal: ItermTerminal instance
        """
        self._iterm_terminal = terminal

    def load_global_config(self, force_reload: bool = False) -> ServiceRegistry:
        """Load the global service configuration.

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            ServiceRegistry from global config
        """
        if self._global_registry and not force_reload:
            return self._global_registry

        config_path = Path.home() / self.parent_folder / SERVICES_CONFIG_FILENAME

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                self._global_registry = ServiceRegistry.model_validate(data)
                self.logger.info(f"Loaded global config with {len(self._global_registry.services)} services")
            except Exception as e:
                self.logger.error(f"Error loading global config from {config_path}: {e}")
                self._global_registry = ServiceRegistry()
        else:
            self.logger.debug(f"No global config at {config_path}")
            self._global_registry = ServiceRegistry()

        return self._global_registry

    def load_repo_config(self, repo_path: str, force_reload: bool = False) -> ServiceRegistry:
        """Load service configuration for a specific repo.

        Args:
            repo_path: Path to the repository
            force_reload: Force reload even if already loaded

        Returns:
            ServiceRegistry from repo config
        """
        repo_path = os.path.expanduser(repo_path)

        if repo_path in self._repo_registries and not force_reload:
            return self._repo_registries[repo_path]

        config_path = Path(repo_path) / self.parent_folder / SERVICES_CONFIG_FILENAME

        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                registry = ServiceRegistry.model_validate(data)
                self._repo_registries[repo_path] = registry
                self.logger.info(f"Loaded repo config for {repo_path} with {len(registry.services)} services")
            except Exception as e:
                self.logger.error(f"Error loading repo config from {config_path}: {e}")
                registry = ServiceRegistry()
                self._repo_registries[repo_path] = registry
        else:
            self.logger.debug(f"No repo config at {config_path}")
            registry = ServiceRegistry()
            self._repo_registries[repo_path] = registry

        return registry

    def get_merged_services(
        self,
        repo_path: str,
        min_priority: Optional[ServicePriority] = None
    ) -> List[ServiceConfig]:
        """Get services for a repo, merging global and repo configs.

        Per-repo configs can override priority of globally-defined services.

        Args:
            repo_path: Path to the repository
            min_priority: Minimum priority level to include

        Returns:
            List of merged ServiceConfig objects
        """
        global_registry = self.load_global_config()
        repo_registry = self.load_repo_config(repo_path)

        # Start with global services that match this repo
        merged: Dict[str, ServiceConfig] = {}
        for service in global_registry.get_services_for_repo(repo_path, min_priority):
            merged[service.name] = service

        # Override/add repo-specific services
        for service in repo_registry.services:
            if service.name in merged:
                # Repo config overrides priority of global service
                global_service = merged[service.name]

                # Create merged config with repo's priority
                merged_config = ServiceConfig(
                    name=service.name,
                    display_name=service.display_name or global_service.display_name,
                    command=service.command or global_service.command,
                    priority=service.priority,  # Use repo's priority
                    port=service.port or global_service.port,
                    working_directory=service.working_directory or global_service.working_directory,
                    repo_patterns=service.repo_patterns or global_service.repo_patterns,
                    profile_tag=service.profile_tag or global_service.profile_tag,
                    health_check=service.health_check or global_service.health_check,
                    environment={**global_service.environment, **service.environment},
                )
                merged[service.name] = merged_config
            else:
                merged[service.name] = service

        # Filter by minimum priority if specified
        if min_priority:
            priority_order = [
                ServicePriority.QUIET,
                ServicePriority.OPTIONAL,
                ServicePriority.PREFERRED,
                ServicePriority.REQUIRED
            ]
            min_idx = priority_order.index(min_priority)
            merged = {
                name: svc for name, svc in merged.items()
                if priority_order.index(svc.priority) >= min_idx
            }

        return list(merged.values())

    def get_service_state(self, service_name: str) -> Optional[ServiceState]:
        """Get the runtime state of a service.

        Args:
            service_name: Name of the service

        Returns:
            ServiceState or None
        """
        return self._service_states.get(service_name)

    def get_all_states(self) -> Dict[str, ServiceState]:
        """Get all service states.

        Returns:
            Dictionary of service name to ServiceState
        """
        return self._service_states.copy()

    async def check_service_running(self, service: ServiceConfig) -> bool:
        """Check if a service is currently running via iTerm profile tags.

        Args:
            service: Service configuration

        Returns:
            True if service appears to be running
        """
        if not self._iterm_terminal:
            self.logger.warning("No iTerm terminal set, cannot check service status")
            return False

        tag = service.effective_profile_tag

        try:
            # Look for sessions with the service tag
            sessions = self._iterm_terminal.get_all_sessions()
            for session in sessions:
                # Check if session has the service tag
                if hasattr(session, 'tags') and tag in session.tags:
                    return True

                # Also check session name pattern
                if hasattr(session, 'name') and service.name in session.name:
                    return True
        except Exception as e:
            self.logger.error(f"Error checking if service {service.name} is running: {e}")

        return False

    async def get_inactive_services(
        self,
        repo_path: str,
        min_priority: Optional[ServicePriority] = None
    ) -> List[ServiceConfig]:
        """Get services that should be running but aren't.

        Args:
            repo_path: Path to the repository
            min_priority: Minimum priority level to check

        Returns:
            List of inactive ServiceConfig objects
        """
        services = self.get_merged_services(repo_path, min_priority)
        inactive = []

        for service in services:
            is_running = await self.check_service_running(service)

            # Update state
            state = self._service_states.get(service.name)
            if state:
                state.is_running = is_running
            else:
                state = ServiceState(service=service, is_running=is_running)
                self._service_states[service.name] = state

            if not is_running:
                inactive.append(service)

        return inactive

    async def start_service(
        self,
        service: ServiceConfig,
        repo_path: Optional[str] = None,
        background: bool = True
    ) -> ServiceState:
        """Start a service in an iTerm session.

        Args:
            service: Service configuration
            repo_path: Optional repo path context
            background: Run in background (default True)

        Returns:
            ServiceState with updated status
        """
        state = self._service_states.get(service.name)
        if not state:
            state = ServiceState(service=service)
            self._service_states[service.name] = state

        if not service.command:
            state.error_message = "Service has no command configured"
            self.logger.error(f"Cannot start {service.name}: no command")
            return state

        if not self._iterm_terminal:
            state.error_message = "No iTerm terminal available"
            self.logger.error(f"Cannot start {service.name}: no terminal")
            return state

        try:
            # Determine working directory
            cwd = service.working_directory
            if not cwd and repo_path:
                cwd = repo_path

            # Create session with service tag
            session_name = f"service:{service.name}"

            # Use the terminal to create a session
            session = await self._iterm_terminal.create_session(
                name=session_name,
                working_directory=cwd,
            )

            if session:
                # Send the command
                await session.send_text(service.command, execute=True)

                state.is_running = True
                state.session_id = session.session_id
                state.started_at = datetime.now()
                state.error_message = None

                self.logger.info(f"Started service {service.name} in session {session.session_id}")
            else:
                state.error_message = "Failed to create session"

        except Exception as e:
            state.error_message = str(e)
            self.logger.error(f"Error starting service {service.name}: {e}")

        return state

    async def stop_service(self, service_name: str) -> bool:
        """Stop a running service.

        Args:
            service_name: Name of the service to stop

        Returns:
            True if successfully stopped
        """
        state = self._service_states.get(service_name)
        if not state or not state.session_id:
            self.logger.warning(f"Service {service_name} not found or no session")
            return False

        if not self._iterm_terminal:
            self.logger.error(f"Cannot stop {service_name}: no terminal")
            return False

        try:
            # Send Ctrl+C to the session
            session = self._iterm_terminal.get_session_by_id(state.session_id)
            if session:
                await session.send_control_character('c')

                # Give it a moment, then close the session
                import asyncio
                await asyncio.sleep(0.5)
                await self._iterm_terminal.close_session(state.session_id)

            state.is_running = False
            state.session_id = None
            self.logger.info(f"Stopped service {service_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping service {service_name}: {e}")
            return False

    def save_global_config(self, registry: ServiceRegistry) -> None:
        """Save a service registry to global config.

        Args:
            registry: ServiceRegistry to save
        """
        config_dir = Path.home() / self.parent_folder
        config_dir.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / SERVICES_CONFIG_FILENAME

        try:
            with open(config_path, 'w') as f:
                json.dump(registry.model_dump(), f, indent=2)
            self._global_registry = registry
            self.logger.info(f"Saved global config to {config_path}")
        except Exception as e:
            self.logger.error(f"Error saving global config: {e}")
            raise

    def save_repo_config(self, repo_path: str, registry: ServiceRegistry) -> None:
        """Save a service registry to repo config.

        Args:
            repo_path: Path to the repository
            registry: ServiceRegistry to save
        """
        repo_path = os.path.expanduser(repo_path)
        config_dir = Path(repo_path) / self.parent_folder
        config_dir.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / SERVICES_CONFIG_FILENAME

        try:
            with open(config_path, 'w') as f:
                json.dump(registry.model_dump(), f, indent=2)
            self._repo_registries[repo_path] = registry
            self.logger.info(f"Saved repo config to {config_path}")
        except Exception as e:
            self.logger.error(f"Error saving repo config: {e}")
            raise


# Module-level instance for easy access
_service_manager: Optional[ServiceManager] = None


def get_service_manager(
    parent_folder: str = DEFAULT_PARENT_FOLDER,
    logger: Optional[logging.Logger] = None
) -> ServiceManager:
    """Get or create the global ServiceManager instance.

    Args:
        parent_folder: Name of the config folder
        logger: Optional logger instance

    Returns:
        ServiceManager instance
    """
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager(parent_folder, logger)
    return _service_manager
