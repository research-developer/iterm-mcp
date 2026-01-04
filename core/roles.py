"""Role-based session specialization management.

This module provides role management for sessions, enabling:
- Role assignment to sessions/agents
- Tool access control based on roles
- Permission validation for role-restricted operations
- Default role configurations for common use cases
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from pydantic import BaseModel, Field

from .models import (
    DEFAULT_ROLE_CONFIGS,
    RoleConfig,
    SessionRole,
)

if TYPE_CHECKING:
    from .agents import AgentRegistry


class SessionRoleAssignment(BaseModel):
    """Tracks role assignment for a session."""

    session_id: str = Field(..., description="iTerm session ID")
    role: SessionRole = Field(..., description="Assigned role")
    role_config: RoleConfig = Field(..., description="Role configuration")
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assigned_by: Optional[str] = Field(default=None, description="Agent that assigned this role")


class RolePermissionError(Exception):
    """Raised when a role-based permission check fails."""

    def __init__(
        self,
        message: str,
        required_role: Optional[SessionRole] = None,
        current_role: Optional[SessionRole] = None,
        tool_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.required_role = required_role
        self.current_role = current_role
        self.tool_name = tool_name


class RoleManager:
    """Manages role assignments and permissions for sessions.

    This class handles:
    - Assigning roles to sessions
    - Checking tool access permissions based on roles
    - Managing custom role configurations
    - Persisting role assignments to disk
    """

    def __init__(
        self,
        data_dir: Optional[str] = None,
        agent_registry: Optional["AgentRegistry"] = None,
    ):
        """Initialize the role manager.

        Args:
            data_dir: Directory for persistence files. Defaults to ~/.iterm-mcp/
            agent_registry: Optional agent registry for agent lookups
        """
        if data_dir is None:
            data_dir = os.path.expanduser("~/.iterm-mcp")

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.roles_file = self.data_dir / "roles.jsonl"
        self.custom_configs_file = self.data_dir / "role_configs.jsonl"

        # In-memory caches
        self._session_roles: Dict[str, SessionRoleAssignment] = {}
        self._custom_configs: Dict[str, RoleConfig] = {}  # role name -> custom config

        self.agent_registry = agent_registry

        # Load existing data
        self._load_data()

    def attach_agent_registry(self, agent_registry: "AgentRegistry") -> None:
        """Attach an agent registry after initialization."""
        self.agent_registry = agent_registry

    def _load_data(self) -> None:
        """Load role assignments and custom configs from JSONL files."""
        # Load role assignments
        if self.roles_file.exists():
            with open(self.roles_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            assignment = SessionRoleAssignment(**data)
                            self._session_roles[assignment.session_id] = assignment
                        except (json.JSONDecodeError, ValueError):
                            continue

        # Load custom configs
        if self.custom_configs_file.exists():
            with open(self.custom_configs_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            config = RoleConfig(**data)
                            self._custom_configs[config.role.value] = config
                        except (json.JSONDecodeError, ValueError):
                            continue

    def _save_roles(self) -> None:
        """Persist all role assignments to JSONL file."""
        with open(self.roles_file, 'w') as f:
            for assignment in self._session_roles.values():
                f.write(assignment.model_dump_json() + '\n')

    def _save_custom_configs(self) -> None:
        """Persist all custom configs to JSONL file."""
        with open(self.custom_configs_file, 'w') as f:
            for config in self._custom_configs.values():
                f.write(config.model_dump_json() + '\n')

    # ==================== Role Configuration ====================

    def get_default_config(self, role: SessionRole) -> RoleConfig:
        """Get the default configuration for a role.

        Args:
            role: The role to get configuration for

        Returns:
            RoleConfig for the specified role
        """
        if role in DEFAULT_ROLE_CONFIGS:
            return DEFAULT_ROLE_CONFIGS[role]

        # Return a minimal config for CUSTOM or unknown roles
        return RoleConfig(
            role=role,
            description=f"Custom role: {role.value}",
        )

    def set_custom_config(self, config: RoleConfig) -> None:
        """Set a custom configuration for a role.

        This overrides the default configuration for the specified role.

        Args:
            config: The custom role configuration
        """
        self._custom_configs[config.role.value] = config
        self._save_custom_configs()

    def get_config(self, role: SessionRole) -> RoleConfig:
        """Get the effective configuration for a role.

        Returns custom config if set, otherwise the default config.

        Args:
            role: The role to get configuration for

        Returns:
            Effective RoleConfig for the specified role
        """
        if role.value in self._custom_configs:
            return self._custom_configs[role.value]
        return self.get_default_config(role)

    def remove_custom_config(self, role: SessionRole) -> bool:
        """Remove a custom configuration for a role.

        Args:
            role: The role to remove custom config for

        Returns:
            True if a custom config was removed
        """
        if role.value in self._custom_configs:
            del self._custom_configs[role.value]
            self._save_custom_configs()
            return True
        return False

    # ==================== Role Assignment ====================

    def assign_role(
        self,
        session_id: str,
        role: SessionRole,
        role_config: Optional[RoleConfig] = None,
        assigned_by: Optional[str] = None,
    ) -> SessionRoleAssignment:
        """Assign a role to a session.

        Args:
            session_id: The iTerm session ID
            role: The role to assign
            role_config: Optional custom config (overrides defaults)
            assigned_by: Optional agent name that assigned this role

        Returns:
            The created SessionRoleAssignment
        """
        config = role_config or self.get_config(role)

        assignment = SessionRoleAssignment(
            session_id=session_id,
            role=role,
            role_config=config,
            assigned_by=assigned_by,
        )

        self._session_roles[session_id] = assignment
        self._save_roles()

        return assignment

    def get_role(self, session_id: str) -> Optional[SessionRoleAssignment]:
        """Get the role assignment for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            SessionRoleAssignment if role is assigned, None otherwise
        """
        return self._session_roles.get(session_id)

    def get_role_by_agent(self, agent_name: str) -> Optional[SessionRoleAssignment]:
        """Get the role assignment for an agent's session.

        Args:
            agent_name: The agent name

        Returns:
            SessionRoleAssignment if found, None otherwise
        """
        if not self.agent_registry:
            return None

        agent = self.agent_registry.get_agent(agent_name)
        if agent:
            return self.get_role(agent.session_id)
        return None

    def remove_role(self, session_id: str) -> bool:
        """Remove the role assignment for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            True if a role was removed
        """
        if session_id in self._session_roles:
            del self._session_roles[session_id]
            self._save_roles()
            return True
        return False

    def list_roles(self, role_filter: Optional[SessionRole] = None) -> List[SessionRoleAssignment]:
        """List all role assignments.

        Args:
            role_filter: Optional role to filter by

        Returns:
            List of SessionRoleAssignment objects
        """
        assignments = list(self._session_roles.values())
        if role_filter:
            assignments = [a for a in assignments if a.role == role_filter]
        return assignments

    def get_sessions_by_role(self, role: SessionRole) -> List[str]:
        """Get all session IDs with a specific role.

        Args:
            role: The role to filter by

        Returns:
            List of session IDs with the specified role
        """
        return [
            assignment.session_id
            for assignment in self._session_roles.values()
            if assignment.role == role
        ]

    # ==================== Permission Checking ====================

    def is_tool_allowed(
        self,
        session_id: str,
        tool_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if a tool is allowed for a session based on its role.

        Args:
            session_id: The iTerm session ID
            tool_name: The name of the tool to check

        Returns:
            Tuple of (allowed, reason)
            - allowed: True if tool is allowed
            - reason: Explanation if not allowed, None otherwise
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            # No role assigned - allow all tools
            return True, None

        config = assignment.role_config

        # Check restricted tools first (explicit deny)
        if tool_name in config.restricted_tools:
            return False, f"Tool '{tool_name}' is restricted for role {assignment.role.value}"

        # If available_tools is empty, all non-restricted tools are allowed
        if not config.available_tools:
            return True, None

        # Check if tool is in available tools
        if tool_name in config.available_tools:
            return True, None

        return False, f"Tool '{tool_name}' is not available for role {assignment.role.value}"

    def check_tool_permission(
        self,
        session_id: str,
        tool_name: str,
    ) -> None:
        """Check if a tool is allowed and raise if not.

        Args:
            session_id: The iTerm session ID
            tool_name: The name of the tool to check

        Raises:
            RolePermissionError: If the tool is not allowed
        """
        allowed, reason = self.is_tool_allowed(session_id, tool_name)
        if not allowed:
            assignment = self._session_roles.get(session_id)
            raise RolePermissionError(
                reason or "Tool not allowed",
                current_role=assignment.role if assignment else None,
                tool_name=tool_name,
            )

    def can_spawn_agents(self, session_id: str) -> bool:
        """Check if a session can spawn new agent sessions.

        Args:
            session_id: The iTerm session ID

        Returns:
            True if the session can spawn agents
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            # No role assigned - default to False for safety
            return False
        return assignment.role_config.can_spawn_agents

    def can_modify_roles(self, session_id: str) -> bool:
        """Check if a session can modify roles of other sessions.

        Args:
            session_id: The iTerm session ID

        Returns:
            True if the session can modify roles
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            # No role assigned - default to False for safety
            return False
        return assignment.role_config.can_modify_roles

    def get_priority(self, session_id: str) -> int:
        """Get the priority level for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            Priority level (1=highest, 5=lowest). Default is 5 if no role.
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            return 5  # Lowest priority for unassigned sessions
        return assignment.role_config.priority

    # ==================== Utility Methods ====================

    def get_available_tools(self, session_id: str) -> Set[str]:
        """Get the set of explicitly available tools for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            Set of tool names that are explicitly available for this session.

            Note:
                - An empty set has a special meaning: *all tools are available*,
                  subject to any restrictions returned by ``get_restricted_tools``.
                - This applies both when the session has no role assignment and when
                  the assigned role's ``available_tools`` list is empty.
                - Use ``is_tool_allowed()`` to check if a specific tool is permitted.
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            return set()  # Empty = all tools (subject to restricted_tools)

        config = assignment.role_config
        available = set(config.available_tools)

        # Remove restricted tools from the explicitly available set
        available -= set(config.restricted_tools)

        return available

    def get_restricted_tools(self, session_id: str) -> Set[str]:
        """Get the set of restricted tools for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            Set of restricted tool names.
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            return set()

        return set(assignment.role_config.restricted_tools)

    def describe(self, session_id: str) -> Dict:
        """Get a description of the role assignment for a session.

        Args:
            session_id: The iTerm session ID

        Returns:
            Dict with role information
        """
        assignment = self._session_roles.get(session_id)
        if not assignment:
            return {
                "session_id": session_id,
                "has_role": False,
                "role": None,
                "description": None,
                "can_spawn_agents": False,
                "can_modify_roles": False,
                "priority": 5,
            }

        return {
            "session_id": session_id,
            "has_role": True,
            "role": assignment.role.value,
            "description": assignment.role_config.description,
            "available_tools": assignment.role_config.available_tools,
            "restricted_tools": assignment.role_config.restricted_tools,
            "can_spawn_agents": assignment.role_config.can_spawn_agents,
            "can_modify_roles": assignment.role_config.can_modify_roles,
            "priority": assignment.role_config.priority,
            "assigned_at": assignment.assigned_at.isoformat(),
            "assigned_by": assignment.assigned_by,
        }

    def clear_all(self) -> int:
        """Clear all role assignments.

        Returns:
            Number of assignments cleared
        """
        count = len(self._session_roles)
        self._session_roles.clear()
        self._save_roles()
        return count
