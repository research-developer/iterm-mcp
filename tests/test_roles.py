"""Tests for role-based session specialization."""

import os
import shutil
import tempfile
import unittest

from core.models import (
    SessionRole,
    RoleConfig,
    DEFAULT_ROLE_CONFIGS,
    SessionConfig,
)
from core.roles import (
    RoleManager,
    RolePermissionError,
)
from core.agents import Agent, AgentRegistry


class TestSessionRoleEnum(unittest.TestCase):
    """Test SessionRole enum."""

    def test_all_roles_exist(self):
        """Test that all expected roles are defined."""
        expected_roles = [
            "devops", "builder", "debugger", "researcher",
            "tester", "orchestrator", "monitor", "custom"
        ]
        actual_roles = [r.value for r in SessionRole]
        for role in expected_roles:
            self.assertIn(role, actual_roles)

    def test_role_from_string(self):
        """Test creating role from string value."""
        role = SessionRole("devops")
        self.assertEqual(role, SessionRole.DEVOPS)

    def test_role_comparison(self):
        """Test role equality comparison."""
        self.assertEqual(SessionRole.BUILDER, SessionRole("builder"))
        self.assertNotEqual(SessionRole.BUILDER, SessionRole.DEBUGGER)


class TestRoleConfig(unittest.TestCase):
    """Test RoleConfig model."""

    def test_minimal_config(self):
        """Test creating a role config with minimal fields."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            description="A custom role"
        )
        self.assertEqual(config.role, SessionRole.CUSTOM)
        self.assertEqual(config.description, "A custom role")
        self.assertEqual(config.available_tools, [])
        self.assertEqual(config.restricted_tools, [])
        self.assertEqual(config.priority, 3)
        self.assertFalse(config.can_spawn_agents)
        self.assertFalse(config.can_modify_roles)

    def test_full_config(self):
        """Test creating a role config with all fields."""
        config = RoleConfig(
            role=SessionRole.DEVOPS,
            description="DevOps specialist",
            available_tools=["deploy", "monitor"],
            restricted_tools=["delete_prod"],
            default_commands=["kubectl get pods"],
            environment={"KUBECONFIG": "/path/to/config"},
            can_spawn_agents=True,
            can_modify_roles=False,
            priority=2,
        )
        self.assertEqual(config.role, SessionRole.DEVOPS)
        self.assertIn("deploy", config.available_tools)
        self.assertIn("delete_prod", config.restricted_tools)
        self.assertEqual(config.priority, 2)
        self.assertTrue(config.can_spawn_agents)

    def test_priority_bounds(self):
        """Test that priority is bounded 1-5."""
        # Valid priorities
        config1 = RoleConfig(role=SessionRole.CUSTOM, priority=1)
        self.assertEqual(config1.priority, 1)

        config5 = RoleConfig(role=SessionRole.CUSTOM, priority=5)
        self.assertEqual(config5.priority, 5)

    def test_default_priority(self):
        """Test default priority value."""
        config = RoleConfig(role=SessionRole.CUSTOM)
        self.assertEqual(config.priority, 3)


class TestDefaultRoleConfigs(unittest.TestCase):
    """Test default role configurations."""

    def test_all_standard_roles_have_configs(self):
        """Test that all standard roles have default configs."""
        standard_roles = [
            SessionRole.DEVOPS,
            SessionRole.BUILDER,
            SessionRole.DEBUGGER,
            SessionRole.RESEARCHER,
            SessionRole.TESTER,
            SessionRole.ORCHESTRATOR,
            SessionRole.MONITOR,
        ]
        for role in standard_roles:
            self.assertIn(role, DEFAULT_ROLE_CONFIGS)
            config = DEFAULT_ROLE_CONFIGS[role]
            self.assertEqual(config.role, role)
            self.assertGreater(len(config.description), 0)

    def test_orchestrator_has_spawn_capability(self):
        """Test that orchestrator can spawn agents."""
        config = DEFAULT_ROLE_CONFIGS[SessionRole.ORCHESTRATOR]
        self.assertTrue(config.can_spawn_agents)
        self.assertTrue(config.can_modify_roles)
        self.assertEqual(config.priority, 1)

    def test_monitor_is_read_only(self):
        """Test that monitor has restricted write tools."""
        config = DEFAULT_ROLE_CONFIGS[SessionRole.MONITOR]
        self.assertFalse(config.can_spawn_agents)
        self.assertFalse(config.can_modify_roles)


class TestAgentWithRole(unittest.TestCase):
    """Test Agent model with role field."""

    def test_agent_without_role(self):
        """Test creating an agent without a role."""
        agent = Agent(name="test-agent", session_id="session-123")
        self.assertIsNone(agent.role)

    def test_agent_with_role(self):
        """Test creating an agent with a role."""
        agent = Agent(
            name="devops-agent",
            session_id="session-123",
            role=SessionRole.DEVOPS
        )
        self.assertEqual(agent.role, SessionRole.DEVOPS)

    def test_agent_has_role_method(self):
        """Test the has_role method."""
        agent = Agent(
            name="builder-agent",
            session_id="session-123",
            role=SessionRole.BUILDER
        )
        self.assertTrue(agent.has_role(SessionRole.BUILDER))
        self.assertFalse(agent.has_role(SessionRole.DEVOPS))

    def test_agent_has_role_when_none(self):
        """Test has_role returns False when role is None."""
        agent = Agent(name="test-agent", session_id="session-123")
        self.assertFalse(agent.has_role(SessionRole.DEVOPS))


class TestAgentRegistryRoles(unittest.TestCase):
    """Test AgentRegistry role-related methods."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_agent_with_role(self):
        """Test registering an agent with a role."""
        agent = self.registry.register_agent(
            name="devops-agent",
            session_id="session-abc",
            role=SessionRole.DEVOPS
        )
        self.assertEqual(agent.role, SessionRole.DEVOPS)

        # Verify retrieval
        retrieved = self.registry.get_agent("devops-agent")
        self.assertEqual(retrieved.role, SessionRole.DEVOPS)

    def test_set_agent_role(self):
        """Test setting role on existing agent."""
        self.registry.register_agent("agent-1", "session-1")

        self.assertTrue(self.registry.set_agent_role("agent-1", SessionRole.BUILDER))

        agent = self.registry.get_agent("agent-1")
        self.assertEqual(agent.role, SessionRole.BUILDER)

    def test_clear_agent_role(self):
        """Test clearing role from agent."""
        self.registry.register_agent("agent-1", "session-1", role=SessionRole.TESTER)

        self.assertTrue(self.registry.set_agent_role("agent-1", None))

        agent = self.registry.get_agent("agent-1")
        self.assertIsNone(agent.role)

    def test_set_role_nonexistent_agent(self):
        """Test setting role on non-existent agent returns False."""
        result = self.registry.set_agent_role("nonexistent", SessionRole.DEVOPS)
        self.assertFalse(result)

    def test_get_agents_by_role(self):
        """Test getting agents filtered by role."""
        self.registry.register_agent("devops-1", "s1", role=SessionRole.DEVOPS)
        self.registry.register_agent("devops-2", "s2", role=SessionRole.DEVOPS)
        self.registry.register_agent("builder-1", "s3", role=SessionRole.BUILDER)
        self.registry.register_agent("no-role", "s4")

        devops_agents = self.registry.get_agents_by_role(SessionRole.DEVOPS)
        self.assertEqual(len(devops_agents), 2)
        names = [a.name for a in devops_agents]
        self.assertIn("devops-1", names)
        self.assertIn("devops-2", names)
        self.assertNotIn("builder-1", names)


class TestRoleManager(unittest.TestCase):
    """Test RoleManager functionality."""

    def setUp(self):
        """Create temporary directory for role manager data."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_assign_role(self):
        """Test assigning a role to a session."""
        assignment = self.role_manager.assign_role(
            session_id="session-123",
            role=SessionRole.DEVOPS
        )
        self.assertEqual(assignment.session_id, "session-123")
        self.assertEqual(assignment.role, SessionRole.DEVOPS)
        self.assertIsNotNone(assignment.role_config)

    def test_assign_role_with_custom_config(self):
        """Test assigning a role with custom configuration."""
        custom_config = RoleConfig(
            role=SessionRole.CUSTOM,
            description="My custom role",
            available_tools=["tool1", "tool2"],
            can_spawn_agents=True,
        )
        assignment = self.role_manager.assign_role(
            session_id="session-123",
            role=SessionRole.CUSTOM,
            role_config=custom_config,
        )
        self.assertEqual(assignment.role_config.description, "My custom role")
        self.assertTrue(assignment.role_config.can_spawn_agents)

    def test_get_role(self):
        """Test getting role assignment for a session."""
        self.role_manager.assign_role("session-abc", SessionRole.BUILDER)

        assignment = self.role_manager.get_role("session-abc")
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.role, SessionRole.BUILDER)

    def test_get_role_nonexistent(self):
        """Test getting role for non-existent session."""
        assignment = self.role_manager.get_role("nonexistent")
        self.assertIsNone(assignment)

    def test_remove_role(self):
        """Test removing role from a session."""
        self.role_manager.assign_role("session-123", SessionRole.TESTER)

        removed = self.role_manager.remove_role("session-123")
        self.assertTrue(removed)

        assignment = self.role_manager.get_role("session-123")
        self.assertIsNone(assignment)

    def test_remove_nonexistent_role(self):
        """Test removing role that doesn't exist."""
        removed = self.role_manager.remove_role("nonexistent")
        self.assertFalse(removed)

    def test_list_roles(self):
        """Test listing all role assignments."""
        self.role_manager.assign_role("s1", SessionRole.DEVOPS)
        self.role_manager.assign_role("s2", SessionRole.BUILDER)
        self.role_manager.assign_role("s3", SessionRole.DEVOPS)

        all_roles = self.role_manager.list_roles()
        self.assertEqual(len(all_roles), 3)

    def test_list_roles_with_filter(self):
        """Test listing roles with filter."""
        self.role_manager.assign_role("s1", SessionRole.DEVOPS)
        self.role_manager.assign_role("s2", SessionRole.BUILDER)
        self.role_manager.assign_role("s3", SessionRole.DEVOPS)

        devops_roles = self.role_manager.list_roles(role_filter=SessionRole.DEVOPS)
        self.assertEqual(len(devops_roles), 2)

    def test_get_sessions_by_role(self):
        """Test getting session IDs by role."""
        self.role_manager.assign_role("s1", SessionRole.TESTER)
        self.role_manager.assign_role("s2", SessionRole.TESTER)
        self.role_manager.assign_role("s3", SessionRole.BUILDER)

        tester_sessions = self.role_manager.get_sessions_by_role(SessionRole.TESTER)
        self.assertEqual(len(tester_sessions), 2)
        self.assertIn("s1", tester_sessions)
        self.assertIn("s2", tester_sessions)


class TestToolPermissions(unittest.TestCase):
    """Test tool permission checking."""

    def setUp(self):
        """Create temporary directory and role manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tool_allowed_no_role(self):
        """Test that all tools are allowed when no role assigned."""
        allowed, reason = self.role_manager.is_tool_allowed("session-123", "any_tool")
        self.assertTrue(allowed)
        self.assertIsNone(reason)

    def test_tool_restricted(self):
        """Test that restricted tools are denied."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            restricted_tools=["dangerous_tool", "delete_all"]
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        allowed, reason = self.role_manager.is_tool_allowed("session-123", "dangerous_tool")
        self.assertFalse(allowed)
        self.assertIn("restricted", reason.lower())

    def test_tool_in_available_list(self):
        """Test that available tools are allowed."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            available_tools=["safe_tool", "read_only"]
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        allowed, reason = self.role_manager.is_tool_allowed("session-123", "safe_tool")
        self.assertTrue(allowed)

    def test_tool_not_in_available_list(self):
        """Test that tools not in available list are denied."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            available_tools=["safe_tool", "read_only"]
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        allowed, reason = self.role_manager.is_tool_allowed("session-123", "other_tool")
        self.assertFalse(allowed)
        self.assertIn("not available", reason.lower())

    def test_empty_available_allows_all(self):
        """Test that empty available_tools allows all non-restricted."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            available_tools=[],  # Empty means all allowed
            restricted_tools=["blocked_tool"]
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        allowed, reason = self.role_manager.is_tool_allowed("session-123", "any_tool")
        self.assertTrue(allowed)

    def test_check_tool_permission_raises(self):
        """Test that check_tool_permission raises on denied."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            restricted_tools=["blocked"]
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        with self.assertRaises(RolePermissionError) as ctx:
            self.role_manager.check_tool_permission("session-123", "blocked")

        self.assertEqual(ctx.exception.tool_name, "blocked")


class TestSpawnAndModifyPermissions(unittest.TestCase):
    """Test can_spawn_agents and can_modify_roles permissions."""

    def setUp(self):
        """Create temporary directory and role manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_can_spawn_agents_default_false(self):
        """Test that sessions without role cannot spawn by default."""
        result = self.role_manager.can_spawn_agents("session-123")
        self.assertFalse(result)

    def test_can_spawn_agents_with_permission(self):
        """Test that sessions with permission can spawn."""
        config = RoleConfig(
            role=SessionRole.ORCHESTRATOR,
            can_spawn_agents=True
        )
        self.role_manager.assign_role("session-123", SessionRole.ORCHESTRATOR, role_config=config)

        result = self.role_manager.can_spawn_agents("session-123")
        self.assertTrue(result)

    def test_can_modify_roles_default_false(self):
        """Test that sessions without role cannot modify roles by default."""
        result = self.role_manager.can_modify_roles("session-123")
        self.assertFalse(result)

    def test_can_modify_roles_with_permission(self):
        """Test that sessions with permission can modify roles."""
        config = RoleConfig(
            role=SessionRole.ORCHESTRATOR,
            can_modify_roles=True
        )
        self.role_manager.assign_role("session-123", SessionRole.ORCHESTRATOR, role_config=config)

        result = self.role_manager.can_modify_roles("session-123")
        self.assertTrue(result)


class TestRolePriority(unittest.TestCase):
    """Test role priority functionality."""

    def setUp(self):
        """Create temporary directory and role manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_priority_default_for_unassigned(self):
        """Test default priority for sessions without role."""
        priority = self.role_manager.get_priority("session-123")
        self.assertEqual(priority, 5)  # Lowest priority

    def test_priority_from_config(self):
        """Test priority from role config."""
        config = RoleConfig(
            role=SessionRole.CUSTOM,
            priority=2
        )
        self.role_manager.assign_role("session-123", SessionRole.CUSTOM, role_config=config)

        priority = self.role_manager.get_priority("session-123")
        self.assertEqual(priority, 2)

    def test_orchestrator_has_highest_priority(self):
        """Test that orchestrator has priority 1."""
        self.role_manager.assign_role("session-123", SessionRole.ORCHESTRATOR)

        priority = self.role_manager.get_priority("session-123")
        self.assertEqual(priority, 1)


class TestRoleDescribe(unittest.TestCase):
    """Test the describe method for role information."""

    def setUp(self):
        """Create temporary directory and role manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_describe_no_role(self):
        """Test describe for session without role."""
        description = self.role_manager.describe("session-123")

        self.assertFalse(description["has_role"])
        self.assertIsNone(description["role"])
        self.assertEqual(description["priority"], 5)

    def test_describe_with_role(self):
        """Test describe for session with role."""
        self.role_manager.assign_role(
            "session-123",
            SessionRole.DEVOPS,
            assigned_by="admin"
        )

        description = self.role_manager.describe("session-123")

        self.assertTrue(description["has_role"])
        self.assertEqual(description["role"], "devops")
        self.assertEqual(description["assigned_by"], "admin")
        self.assertIn("assigned_at", description)


class TestRolePersistence(unittest.TestCase):
    """Test JSONL persistence for roles."""

    def setUp(self):
        """Create temporary directory."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_roles_persist(self):
        """Test that role assignments persist across instances."""
        # Create and populate role manager
        rm1 = RoleManager(data_dir=self.temp_dir)
        rm1.assign_role("session-123", SessionRole.DEVOPS, assigned_by="test")

        # Create new instance (simulates restart)
        rm2 = RoleManager(data_dir=self.temp_dir)
        assignment = rm2.get_role("session-123")

        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.role, SessionRole.DEVOPS)
        self.assertEqual(assignment.assigned_by, "test")

    def test_roles_file_created(self):
        """Test that roles.jsonl file is created."""
        rm = RoleManager(data_dir=self.temp_dir)
        rm.assign_role("session-123", SessionRole.BUILDER)

        roles_file = os.path.join(self.temp_dir, "roles.jsonl")
        self.assertTrue(os.path.exists(roles_file))

    def test_clear_all_roles(self):
        """Test clearing all role assignments."""
        rm = RoleManager(data_dir=self.temp_dir)
        rm.assign_role("s1", SessionRole.DEVOPS)
        rm.assign_role("s2", SessionRole.BUILDER)
        rm.assign_role("s3", SessionRole.TESTER)

        count = rm.clear_all()
        self.assertEqual(count, 3)
        self.assertEqual(len(rm.list_roles()), 0)


class TestCustomRoleConfigs(unittest.TestCase):
    """Test custom role configuration management."""

    def setUp(self):
        """Create temporary directory and role manager."""
        self.temp_dir = tempfile.mkdtemp()
        self.role_manager = RoleManager(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_default_config(self):
        """Test getting default config for a role."""
        config = self.role_manager.get_default_config(SessionRole.DEVOPS)
        self.assertEqual(config.role, SessionRole.DEVOPS)
        self.assertIn("DevOps", config.description)

    def test_set_and_get_custom_config(self):
        """Test setting and retrieving custom config."""
        custom = RoleConfig(
            role=SessionRole.DEVOPS,
            description="My custom DevOps config",
            available_tools=["custom_tool"]
        )
        self.role_manager.set_custom_config(custom)

        config = self.role_manager.get_config(SessionRole.DEVOPS)
        self.assertEqual(config.description, "My custom DevOps config")
        self.assertIn("custom_tool", config.available_tools)

    def test_remove_custom_config(self):
        """Test removing custom config reverts to default."""
        custom = RoleConfig(
            role=SessionRole.DEVOPS,
            description="Custom config"
        )
        self.role_manager.set_custom_config(custom)

        removed = self.role_manager.remove_custom_config(SessionRole.DEVOPS)
        self.assertTrue(removed)

        config = self.role_manager.get_config(SessionRole.DEVOPS)
        self.assertNotEqual(config.description, "Custom config")


class TestSessionConfigWithRole(unittest.TestCase):
    """Test SessionConfig model with role field."""

    def test_session_config_without_role(self):
        """Test SessionConfig without role is valid."""
        config = SessionConfig(name="test-session")
        self.assertIsNone(config.role)
        self.assertIsNone(config.role_config)

    def test_session_config_with_role(self):
        """Test SessionConfig with role."""
        config = SessionConfig(
            name="devops-session",
            role=SessionRole.DEVOPS
        )
        self.assertEqual(config.role, SessionRole.DEVOPS)

    def test_session_config_with_role_config(self):
        """Test SessionConfig with custom role config."""
        role_config = RoleConfig(
            role=SessionRole.CUSTOM,
            description="Special session",
            can_spawn_agents=True
        )
        config = SessionConfig(
            name="special-session",
            role=SessionRole.CUSTOM,
            role_config=role_config
        )
        self.assertEqual(config.role_config.description, "Special session")
        self.assertTrue(config.role_config.can_spawn_agents)


if __name__ == "__main__":
    unittest.main()
