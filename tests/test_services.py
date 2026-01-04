"""Tests for the Service Registry System.

Tests cover:
- ServicePriority enum and conversion
- ServiceConfig model and validation
- ServiceRegistry model and filtering
- ServiceState dataclass
- ServiceManager configuration loading and lifecycle
"""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.services import (
    DEFAULT_PARENT_FOLDER,
    ServiceConfig,
    ServiceManager,
    ServicePriority,
    ServiceRegistry,
    ServiceState,
    get_service_manager,
)


class TestServicePriority(unittest.TestCase):
    """Tests for ServicePriority enum."""

    def test_priority_values(self):
        """Test that all priority values exist."""
        self.assertEqual(ServicePriority.QUIET.value, "quiet")
        self.assertEqual(ServicePriority.OPTIONAL.value, "optional")
        self.assertEqual(ServicePriority.PREFERRED.value, "preferred")
        self.assertEqual(ServicePriority.REQUIRED.value, "required")

    def test_from_string_lowercase(self):
        """Test from_string with lowercase values."""
        self.assertEqual(ServicePriority.from_string("quiet"), ServicePriority.QUIET)
        self.assertEqual(ServicePriority.from_string("optional"), ServicePriority.OPTIONAL)
        self.assertEqual(ServicePriority.from_string("preferred"), ServicePriority.PREFERRED)
        self.assertEqual(ServicePriority.from_string("required"), ServicePriority.REQUIRED)

    def test_from_string_uppercase(self):
        """Test from_string with uppercase values."""
        self.assertEqual(ServicePriority.from_string("QUIET"), ServicePriority.QUIET)
        self.assertEqual(ServicePriority.from_string("OPTIONAL"), ServicePriority.OPTIONAL)
        self.assertEqual(ServicePriority.from_string("PREFERRED"), ServicePriority.PREFERRED)
        self.assertEqual(ServicePriority.from_string("REQUIRED"), ServicePriority.REQUIRED)

    def test_from_string_mixed_case(self):
        """Test from_string with mixed case values."""
        self.assertEqual(ServicePriority.from_string("Quiet"), ServicePriority.QUIET)
        self.assertEqual(ServicePriority.from_string("Optional"), ServicePriority.OPTIONAL)
        self.assertEqual(ServicePriority.from_string("PreFerRed"), ServicePriority.PREFERRED)

    def test_from_string_invalid(self):
        """Test from_string with invalid values raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ServicePriority.from_string("invalid")
        self.assertIn("invalid", str(ctx.exception).lower())
        self.assertIn("must be one of", str(ctx.exception).lower())

    def test_from_string_empty(self):
        """Test from_string with empty string raises ValueError."""
        with self.assertRaises(ValueError):
            ServicePriority.from_string("")


class TestServiceConfig(unittest.TestCase):
    """Tests for ServiceConfig model."""

    def test_minimal_config(self):
        """Test creating config with only required fields."""
        config = ServiceConfig(name="test-service")
        self.assertEqual(config.name, "test-service")
        self.assertIsNone(config.display_name)
        self.assertIsNone(config.command)
        self.assertEqual(config.priority, ServicePriority.OPTIONAL)
        self.assertIsNone(config.port)
        self.assertEqual(config.repo_patterns, [])

    def test_full_config(self):
        """Test creating config with all fields."""
        config = ServiceConfig(
            name="my-service",
            display_name="My Service",
            command="npm start",
            priority=ServicePriority.REQUIRED,
            port=3000,
            working_directory="/path/to/dir",
            repo_patterns=["**/my-project*"],
            profile_tag="my-service-tag",
            health_check="curl localhost:3000/health",
            environment={"NODE_ENV": "development"},
        )
        self.assertEqual(config.name, "my-service")
        self.assertEqual(config.display_name, "My Service")
        self.assertEqual(config.command, "npm start")
        self.assertEqual(config.priority, ServicePriority.REQUIRED)
        self.assertEqual(config.port, 3000)

    def test_priority_string_conversion(self):
        """Test that priority strings are converted to enum."""
        config = ServiceConfig(name="test", priority="preferred")
        self.assertEqual(config.priority, ServicePriority.PREFERRED)

    def test_effective_display_name_with_display_name(self):
        """Test effective_display_name returns display_name when set."""
        config = ServiceConfig(name="test", display_name="Test Service")
        self.assertEqual(config.effective_display_name, "Test Service")

    def test_effective_display_name_fallback(self):
        """Test effective_display_name falls back to name."""
        config = ServiceConfig(name="test-service")
        self.assertEqual(config.effective_display_name, "test-service")

    def test_effective_profile_tag_with_tag(self):
        """Test effective_profile_tag returns profile_tag when set."""
        config = ServiceConfig(name="test", profile_tag="custom-tag")
        self.assertEqual(config.effective_profile_tag, "custom-tag")

    def test_effective_profile_tag_fallback(self):
        """Test effective_profile_tag falls back to service:{name}."""
        config = ServiceConfig(name="my-service")
        self.assertEqual(config.effective_profile_tag, "service:my-service")

    def test_path_expansion_tilde(self):
        """Test that ~ is expanded in working_directory."""
        config = ServiceConfig(name="test", working_directory="~/projects")
        self.assertNotIn("~", config.working_directory)
        self.assertTrue(config.working_directory.startswith("/"))

    def test_matches_repo_no_patterns(self):
        """Test matches_repo returns True when no patterns specified."""
        config = ServiceConfig(name="test")
        self.assertTrue(config.matches_repo("/any/path"))
        self.assertTrue(config.matches_repo("/another/path"))

    def test_matches_repo_with_patterns(self):
        """Test matches_repo with glob patterns."""
        config = ServiceConfig(
            name="test",
            repo_patterns=["**/iterm-mcp*", "**/my-project"]
        )
        self.assertTrue(config.matches_repo("/Users/dev/iterm-mcp"))
        self.assertTrue(config.matches_repo("/home/user/projects/iterm-mcp-test"))
        self.assertFalse(config.matches_repo("/Users/dev/other-project"))

    def test_matches_repo_exact_pattern(self):
        """Test matches_repo with exact path pattern."""
        config = ServiceConfig(
            name="test",
            repo_patterns=["/Users/dev/specific-project"]
        )
        self.assertTrue(config.matches_repo("/Users/dev/specific-project"))
        self.assertFalse(config.matches_repo("/Users/dev/other-project"))

    def test_port_validation_valid(self):
        """Test valid port numbers."""
        config = ServiceConfig(name="test", port=80)
        self.assertEqual(config.port, 80)

        config = ServiceConfig(name="test", port=65535)
        self.assertEqual(config.port, 65535)

        config = ServiceConfig(name="test", port=1)
        self.assertEqual(config.port, 1)

    def test_port_validation_invalid(self):
        """Test invalid port numbers raise validation errors."""
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ServiceConfig(name="test", port=0)

        with self.assertRaises(ValidationError):
            ServiceConfig(name="test", port=65536)

        with self.assertRaises(ValidationError):
            ServiceConfig(name="test", port=-1)


class TestServiceRegistry(unittest.TestCase):
    """Tests for ServiceRegistry model."""

    def test_empty_registry(self):
        """Test creating empty registry."""
        registry = ServiceRegistry()
        self.assertEqual(registry.version, "1.0")
        self.assertEqual(registry.parent_folder, DEFAULT_PARENT_FOLDER)
        self.assertEqual(registry.services, [])

    def test_registry_with_services(self):
        """Test creating registry with services."""
        services = [
            ServiceConfig(name="service1"),
            ServiceConfig(name="service2", priority=ServicePriority.REQUIRED),
        ]
        registry = ServiceRegistry(services=services)
        self.assertEqual(len(registry.services), 2)

    def test_get_service_found(self):
        """Test get_service returns service when found."""
        services = [
            ServiceConfig(name="service1"),
            ServiceConfig(name="service2"),
        ]
        registry = ServiceRegistry(services=services)
        result = registry.get_service("service2")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "service2")

    def test_get_service_not_found(self):
        """Test get_service returns None when not found."""
        services = [ServiceConfig(name="service1")]
        registry = ServiceRegistry(services=services)
        result = registry.get_service("nonexistent")
        self.assertIsNone(result)

    def test_get_services_for_repo_no_filter(self):
        """Test get_services_for_repo without priority filter."""
        services = [
            ServiceConfig(name="s1", repo_patterns=["**/project-a*"]),
            ServiceConfig(name="s2", repo_patterns=["**/project-b*"]),
            ServiceConfig(name="s3"),  # Matches all
        ]
        registry = ServiceRegistry(services=services)

        result = registry.get_services_for_repo("/home/user/project-a")
        names = [s.name for s in result]
        self.assertIn("s1", names)
        self.assertIn("s3", names)
        self.assertNotIn("s2", names)

    def test_get_services_for_repo_with_priority_filter(self):
        """Test get_services_for_repo with minimum priority filter."""
        services = [
            ServiceConfig(name="quiet", priority=ServicePriority.QUIET),
            ServiceConfig(name="optional", priority=ServicePriority.OPTIONAL),
            ServiceConfig(name="preferred", priority=ServicePriority.PREFERRED),
            ServiceConfig(name="required", priority=ServicePriority.REQUIRED),
        ]
        registry = ServiceRegistry(services=services)

        # Filter for PREFERRED and above
        result = registry.get_services_for_repo("/any/path", ServicePriority.PREFERRED)
        names = [s.name for s in result]
        self.assertNotIn("quiet", names)
        self.assertNotIn("optional", names)
        self.assertIn("preferred", names)
        self.assertIn("required", names)


class TestServiceState(unittest.TestCase):
    """Tests for ServiceState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        config = ServiceConfig(name="test")
        state = ServiceState(service=config)

        self.assertFalse(state.is_running)
        self.assertIsNone(state.session_id)
        self.assertIsNone(state.started_at)
        self.assertIsNone(state.health_status)
        self.assertIsNone(state.error_message)

    def test_running_state(self):
        """Test running state with session info."""
        config = ServiceConfig(name="test", priority=ServicePriority.REQUIRED)
        now = datetime.now()
        state = ServiceState(
            service=config,
            is_running=True,
            session_id="abc123",
            started_at=now,
            health_status=True,
        )

        self.assertTrue(state.is_running)
        self.assertEqual(state.session_id, "abc123")
        self.assertEqual(state.started_at, now)
        self.assertTrue(state.health_status)

    def test_to_dict(self):
        """Test to_dict serialization."""
        config = ServiceConfig(name="test-service", display_name="Test")
        state = ServiceState(
            service=config,
            is_running=True,
            session_id="session-123",
        )

        result = state.to_dict()
        self.assertEqual(result["name"], "test-service")
        self.assertEqual(result["display_name"], "Test")
        self.assertEqual(result["priority"], "optional")
        self.assertTrue(result["is_running"])
        self.assertEqual(result["session_id"], "session-123")


class TestServiceManager(unittest.TestCase):
    """Tests for ServiceManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.home_config_dir = os.path.join(self.temp_dir, ".iterm-mcp")
        os.makedirs(self.home_config_dir)

        # Create a test repo directory
        self.repo_dir = os.path.join(self.temp_dir, "test-repo")
        self.repo_config_dir = os.path.join(self.repo_dir, ".iterm-mcp")
        os.makedirs(self.repo_config_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Reset global instance
        import core.services
        core.services._service_manager = None

    def _create_global_config(self, services):
        """Helper to create global config file."""
        config = {
            "version": "1.0",
            "parent_folder": ".iterm-mcp",
            "services": [s if isinstance(s, dict) else s.model_dump() for s in services]
        }
        with open(os.path.join(self.home_config_dir, "services.json"), "w") as f:
            json.dump(config, f)

    def _create_repo_config(self, services):
        """Helper to create repo config file."""
        config = {
            "version": "1.0",
            "services": [s if isinstance(s, dict) else s.model_dump() for s in services]
        }
        with open(os.path.join(self.repo_config_dir, "services.json"), "w") as f:
            json.dump(config, f)

    def test_init_default(self):
        """Test ServiceManager initialization with defaults."""
        manager = ServiceManager()
        self.assertEqual(manager.parent_folder, DEFAULT_PARENT_FOLDER)
        self.assertIsNone(manager._global_registry)

    def test_init_custom_parent_folder(self):
        """Test ServiceManager with custom parent folder."""
        manager = ServiceManager(parent_folder=".custom-config")
        self.assertEqual(manager.parent_folder, ".custom-config")

    @patch("core.services.Path.home")
    def test_load_global_config_exists(self, mock_home):
        """Test loading existing global config."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([
            {"name": "service1", "priority": "optional"},
            {"name": "service2", "priority": "required"},
        ])

        manager = ServiceManager()
        registry = manager.load_global_config()

        self.assertEqual(len(registry.services), 2)
        self.assertEqual(registry.services[0].name, "service1")

    @patch("core.services.Path.home")
    def test_load_global_config_missing(self, mock_home):
        """Test loading when global config doesn't exist."""
        mock_home.return_value = Path(self.temp_dir)
        # Don't create any config file
        os.remove(os.path.join(self.home_config_dir, "services.json")) if os.path.exists(os.path.join(self.home_config_dir, "services.json")) else None

        manager = ServiceManager()
        registry = manager.load_global_config()

        self.assertEqual(len(registry.services), 0)

    @patch("core.services.Path.home")
    def test_load_global_config_cached(self, mock_home):
        """Test that global config is cached."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([{"name": "service1"}])

        manager = ServiceManager()
        registry1 = manager.load_global_config()
        registry2 = manager.load_global_config()

        self.assertIs(registry1, registry2)

    @patch("core.services.Path.home")
    def test_load_global_config_force_reload(self, mock_home):
        """Test force reload bypasses cache."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([{"name": "service1"}])
        manager = ServiceManager()
        registry1 = manager.load_global_config()

        # Modify config
        self._create_global_config([{"name": "service1"}, {"name": "service2"}])
        registry2 = manager.load_global_config(force_reload=True)

        self.assertEqual(len(registry1.services), 1)
        self.assertEqual(len(registry2.services), 2)

    def test_load_repo_config_exists(self):
        """Test loading existing repo config."""
        self._create_repo_config([{"name": "repo-service", "priority": "preferred"}])

        manager = ServiceManager()
        registry = manager.load_repo_config(self.repo_dir)

        self.assertEqual(len(registry.services), 1)
        self.assertEqual(registry.services[0].name, "repo-service")

    def test_load_repo_config_missing(self):
        """Test loading when repo config doesn't exist."""
        # Remove repo config
        config_file = os.path.join(self.repo_config_dir, "services.json")
        if os.path.exists(config_file):
            os.remove(config_file)

        manager = ServiceManager()
        registry = manager.load_repo_config(self.repo_dir)

        self.assertEqual(len(registry.services), 0)

    @patch("core.services.Path.home")
    def test_get_merged_services_global_only(self, mock_home):
        """Test merging with only global config."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([
            {"name": "global-service", "priority": "optional"}
        ])
        # Remove repo config
        config_file = os.path.join(self.repo_config_dir, "services.json")
        if os.path.exists(config_file):
            os.remove(config_file)

        manager = ServiceManager()
        services = manager.get_merged_services(self.repo_dir)

        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].name, "global-service")

    @patch("core.services.Path.home")
    def test_get_merged_services_priority_override(self, mock_home):
        """Test that repo config overrides global priority."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([
            {"name": "shared-service", "priority": "optional", "command": "npm start"}
        ])
        self._create_repo_config([
            {"name": "shared-service", "priority": "required"}  # Override priority
        ])

        manager = ServiceManager()
        services = manager.get_merged_services(self.repo_dir)

        self.assertEqual(len(services), 1)
        self.assertEqual(services[0].name, "shared-service")
        self.assertEqual(services[0].priority, ServicePriority.REQUIRED)
        self.assertEqual(services[0].command, "npm start")  # Inherited from global

    @patch("core.services.Path.home")
    def test_get_merged_services_with_priority_filter(self, mock_home):
        """Test merging with priority filter."""
        mock_home.return_value = Path(self.temp_dir)

        self._create_global_config([
            {"name": "quiet-service", "priority": "quiet"},
            {"name": "required-service", "priority": "required"},
        ])

        manager = ServiceManager()
        services = manager.get_merged_services(
            self.repo_dir,
            min_priority=ServicePriority.PREFERRED
        )

        names = [s.name for s in services]
        self.assertNotIn("quiet-service", names)
        self.assertIn("required-service", names)

    def test_get_service_state_not_found(self):
        """Test get_service_state returns None for unknown service."""
        manager = ServiceManager()
        state = manager.get_service_state("nonexistent")
        self.assertIsNone(state)

    def test_get_all_states_empty(self):
        """Test get_all_states returns empty dict initially."""
        manager = ServiceManager()
        states = manager.get_all_states()
        self.assertEqual(states, {})

    @patch("core.services.Path.home")
    def test_save_global_config(self, mock_home):
        """Test saving global config."""
        mock_home.return_value = Path(self.temp_dir)

        manager = ServiceManager()
        registry = ServiceRegistry(
            services=[ServiceConfig(name="new-service", priority=ServicePriority.PREFERRED)]
        )

        manager.save_global_config(registry)

        # Verify file was created
        config_file = os.path.join(self.home_config_dir, "services.json")
        self.assertTrue(os.path.exists(config_file))

        # Verify content
        with open(config_file) as f:
            data = json.load(f)
        self.assertEqual(len(data["services"]), 1)
        self.assertEqual(data["services"][0]["name"], "new-service")

    def test_save_repo_config(self):
        """Test saving repo config."""
        manager = ServiceManager()
        registry = ServiceRegistry(
            services=[ServiceConfig(name="repo-service")]
        )

        manager.save_repo_config(self.repo_dir, registry)

        # Verify file was created
        config_file = os.path.join(self.repo_config_dir, "services.json")
        self.assertTrue(os.path.exists(config_file))

    def test_set_terminal(self):
        """Test setting terminal reference."""
        manager = ServiceManager()
        mock_terminal = MagicMock()

        manager.set_terminal(mock_terminal)

        self.assertEqual(manager._iterm_terminal, mock_terminal)


class TestServiceManagerAsync(unittest.TestCase):
    """Async tests for ServiceManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.temp_dir, "test-repo")
        os.makedirs(self.repo_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        import core.services
        core.services._service_manager = None

    def run_async(self, coro):
        """Helper to run async tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_check_service_running_no_terminal(self):
        """Test check_service_running returns False when no terminal set."""
        async def test():
            manager = ServiceManager()
            config = ServiceConfig(name="test")
            result = await manager.check_service_running(config)
            self.assertFalse(result)

        self.run_async(test())

    def test_check_service_running_with_terminal(self):
        """Test check_service_running with mocked terminal."""
        async def test():
            manager = ServiceManager()

            # Mock terminal with sessions that have tags
            mock_session = MagicMock()
            mock_session.tags = ["service:test-service"]
            mock_session.name = "other-name"

            mock_terminal = MagicMock()
            mock_terminal.get_all_sessions.return_value = [mock_session]

            manager.set_terminal(mock_terminal)

            config = ServiceConfig(name="test-service")
            result = await manager.check_service_running(config)
            self.assertTrue(result)

        self.run_async(test())

    def test_check_service_running_not_found(self):
        """Test check_service_running when service not running."""
        async def test():
            manager = ServiceManager()

            mock_session = MagicMock()
            mock_session.tags = ["service:other-service"]
            mock_session.name = "other-name"

            mock_terminal = MagicMock()
            mock_terminal.get_all_sessions.return_value = [mock_session]

            manager.set_terminal(mock_terminal)

            config = ServiceConfig(name="test-service")
            result = await manager.check_service_running(config)
            self.assertFalse(result)

        self.run_async(test())

    def test_start_service_no_command(self):
        """Test start_service fails when service has no command."""
        async def test():
            manager = ServiceManager()
            config = ServiceConfig(name="test")  # No command

            state = await manager.start_service(config)

            self.assertFalse(state.is_running)
            self.assertIn("no command", state.error_message.lower())

        self.run_async(test())

    def test_start_service_no_terminal(self):
        """Test start_service fails when no terminal set."""
        async def test():
            manager = ServiceManager()
            config = ServiceConfig(name="test", command="npm start")

            state = await manager.start_service(config)

            self.assertFalse(state.is_running)
            self.assertIn("no iterm terminal", state.error_message.lower())

        self.run_async(test())

    def test_start_service_success(self):
        """Test successful service start."""
        async def test():
            manager = ServiceManager()

            # Mock session
            mock_session = AsyncMock()
            mock_session.session_id = "session-123"
            mock_session.send_text = AsyncMock()

            # Mock terminal
            mock_terminal = MagicMock()
            mock_terminal.create_session = AsyncMock(return_value=mock_session)

            manager.set_terminal(mock_terminal)

            config = ServiceConfig(name="test", command="npm start")
            state = await manager.start_service(config, repo_path=self.repo_dir)

            self.assertTrue(state.is_running)
            self.assertEqual(state.session_id, "session-123")
            mock_session.send_text.assert_called_once()

        self.run_async(test())

    def test_stop_service_not_running(self):
        """Test stop_service when service not running."""
        async def test():
            manager = ServiceManager()
            result = await manager.stop_service("nonexistent")
            self.assertFalse(result)

        self.run_async(test())


class TestGetServiceManager(unittest.TestCase):
    """Tests for get_service_manager singleton factory."""

    def tearDown(self):
        """Reset global instance."""
        import core.services
        core.services._service_manager = None

    def test_returns_same_instance(self):
        """Test that get_service_manager returns same instance."""
        manager1 = get_service_manager()
        manager2 = get_service_manager()
        self.assertIs(manager1, manager2)

    def test_creates_instance_on_first_call(self):
        """Test that first call creates new instance."""
        manager = get_service_manager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, ServiceManager)


if __name__ == "__main__":
    unittest.main()
