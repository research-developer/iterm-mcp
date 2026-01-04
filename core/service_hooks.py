"""Service hooks for pre-tool integration.

This module provides hooks that integrate service management with
tool operations, prompting agents based on service priority levels.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .services import (
    ServiceConfig,
    ServiceManager,
    ServicePriority,
    ServiceState,
    get_service_manager,
)


@dataclass
class HookResult:
    """Result from a service hook invocation.

    Attributes:
        proceed: Whether the operation should proceed
        prompt_required: Whether agent should be prompted
        inactive_services: Services that are not running
        auto_started: Services that were auto-started
        message: Human-readable message for the agent
        context: Additional context data
    """
    proceed: bool = True
    prompt_required: bool = False
    inactive_services: List[ServiceConfig] = field(default_factory=list)
    auto_started: List[ServiceConfig] = field(default_factory=list)
    message: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "proceed": self.proceed,
            "prompt_required": self.prompt_required,
            "inactive_services": [
                {
                    "name": s.name,
                    "display_name": s.effective_display_name,
                    "priority": s.priority.value,
                }
                for s in self.inactive_services
            ],
            "auto_started": [
                {
                    "name": s.name,
                    "display_name": s.effective_display_name,
                }
                for s in self.auto_started
            ],
            "message": self.message,
            "context": self.context,
        }


class ServiceHookManager:
    """Manages service hooks for tool operations.

    Hooks are invoked before certain operations (like team creation)
    to check service status and prompt agents based on priority:

    - required: Auto-start in background, proceed
    - preferred: Prompt agent with service info
    - optional: Notify only, proceed automatically
    - quiet: No action, proceed silently
    """

    def __init__(
        self,
        service_manager: Optional[ServiceManager] = None,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the ServiceHookManager.

        Args:
            service_manager: ServiceManager instance (uses global if not provided)
            logger: Optional logger instance
        """
        self.service_manager = service_manager or get_service_manager()
        self.logger = logger or logging.getLogger("iterm-mcp.service_hooks")

    async def pre_create_team_hook(
        self,
        team_name: str,
        repo_path: Optional[str] = None
    ) -> HookResult:
        """Hook invoked before creating a team.

        Checks for inactive services and takes action based on priority:
        - required: Auto-start services in background
        - preferred: Return prompt_required=True for agent decision
        - optional: Include in message but proceed
        - quiet: Ignore

        Args:
            team_name: Name of the team being created
            repo_path: Optional repo path for service matching

        Returns:
            HookResult with action taken and agent prompt if needed
        """
        result = HookResult()
        result.context["team_name"] = team_name
        result.context["repo_path"] = repo_path

        if not repo_path:
            # No repo context, can't check services
            self.logger.debug("No repo_path provided, skipping service check")
            return result

        try:
            # Get all inactive services for this repo
            inactive = await self.service_manager.get_inactive_services(repo_path)

            if not inactive:
                self.logger.debug(f"All services running for {repo_path}")
                return result

            # Categorize by priority
            required_inactive: List[ServiceConfig] = []
            preferred_inactive: List[ServiceConfig] = []
            optional_inactive: List[ServiceConfig] = []

            for service in inactive:
                if service.priority == ServicePriority.REQUIRED:
                    required_inactive.append(service)
                elif service.priority == ServicePriority.PREFERRED:
                    preferred_inactive.append(service)
                elif service.priority == ServicePriority.OPTIONAL:
                    optional_inactive.append(service)
                # quiet services are ignored

            # Handle required services - auto-start them
            for service in required_inactive:
                self.logger.info(f"Auto-starting required service: {service.name}")
                state = await self.service_manager.start_service(
                    service,
                    repo_path=repo_path,
                    background=True
                )
                if state.is_running:
                    result.auto_started.append(service)
                else:
                    # Required service failed to start
                    result.proceed = False
                    result.message = f"Required service '{service.effective_display_name}' failed to start: {state.error_message}"
                    return result

            # Handle preferred services - prompt agent
            if preferred_inactive:
                result.prompt_required = True
                result.inactive_services.extend(preferred_inactive)

                service_names = [s.effective_display_name for s in preferred_inactive]
                result.message = self._build_preferred_message(service_names, team_name)

            # Handle optional services - notify but proceed
            if optional_inactive:
                result.inactive_services.extend(optional_inactive)

                if not result.message:
                    service_names = [s.effective_display_name for s in optional_inactive]
                    result.message = self._build_optional_message(service_names)

            # Include auto-started info in message
            if result.auto_started:
                started_names = [s.effective_display_name for s in result.auto_started]
                started_msg = f"Auto-started required services: {', '.join(started_names)}. "
                result.message = started_msg + (result.message or "")

            return result

        except Exception as e:
            self.logger.error(f"Error in pre_create_team_hook: {e}")
            result.message = f"Error checking services: {e}"
            return result

    def _build_preferred_message(
        self,
        service_names: List[str],
        team_name: str
    ) -> str:
        """Build a prompt message for preferred services.

        Args:
            service_names: Names of inactive preferred services
            team_name: Name of the team being created

        Returns:
            Formatted prompt message
        """
        if len(service_names) == 1:
            return (
                f"The preferred service '{service_names[0]}' is not running. "
                f"Would you like to start it before creating team '{team_name}'? "
                "You can proceed without it, but some features may be unavailable."
            )
        else:
            names = ", ".join(service_names[:-1]) + f" and {service_names[-1]}"
            return (
                f"The following preferred services are not running: {names}. "
                f"Would you like to start them before creating team '{team_name}'? "
                "You can proceed without them, but some features may be unavailable."
            )

    def _build_optional_message(self, service_names: List[str]) -> str:
        """Build a notification message for optional services.

        Args:
            service_names: Names of inactive optional services

        Returns:
            Formatted notification message
        """
        if len(service_names) == 1:
            return f"Note: Optional service '{service_names[0]}' is not running."
        else:
            names = ", ".join(service_names)
            return f"Note: Optional services not running: {names}."

    async def start_services_for_team(
        self,
        service_names: List[str],
        repo_path: str
    ) -> Dict[str, ServiceState]:
        """Start specified services for a team operation.

        Called when agent decides to start preferred services.

        Args:
            service_names: Names of services to start
            repo_path: Repository path for context

        Returns:
            Dictionary of service name to ServiceState
        """
        results: Dict[str, ServiceState] = {}
        services = self.service_manager.get_merged_services(repo_path)

        service_map = {s.name: s for s in services}

        for name in service_names:
            if name not in service_map:
                self.logger.warning(f"Service '{name}' not found in config")
                continue

            service = service_map[name]
            self.logger.info(f"Starting service: {name}")
            state = await self.service_manager.start_service(
                service,
                repo_path=repo_path,
                background=True
            )
            results[name] = state

        return results


# Module-level instance for easy access
_service_hook_manager: Optional[ServiceHookManager] = None


def get_service_hook_manager(
    service_manager: Optional[ServiceManager] = None,
    logger: Optional[logging.Logger] = None
) -> ServiceHookManager:
    """Get or create the global ServiceHookManager instance.

    Args:
        service_manager: ServiceManager instance
        logger: Optional logger instance

    Returns:
        ServiceHookManager instance
    """
    global _service_hook_manager
    if _service_hook_manager is None:
        _service_hook_manager = ServiceHookManager(service_manager, logger)
    return _service_hook_manager
