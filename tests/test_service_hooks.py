"""Tests for the Service Hook System.

Tests cover:
- HookResult dataclass
- ServiceHookManager hook invocations
- Priority-based behavior (required, preferred, optional, quiet)
- Message generation
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.services import (
    ServiceConfig,
    ServiceManager,
    ServicePriority,
    ServiceState,
)
from core.service_hooks import (
    HookResult,
    ServiceHookManager,
    get_service_hook_manager,
)


class TestHookResult(unittest.TestCase):
    """Tests for HookResult dataclass."""

    def test_default_values(self):
        """Test default HookResult values."""
        result = HookResult()

        self.assertTrue(result.proceed)
        self.assertFalse(result.prompt_required)
        self.assertEqual(result.inactive_services, [])
        self.assertEqual(result.auto_started, [])
        self.assertIsNone(result.message)
        self.assertEqual(result.context, {})

    def test_custom_values(self):
        """Test HookResult with custom values."""
        service = ServiceConfig(name="test")
        result = HookResult(
            proceed=False,
            prompt_required=True,
            inactive_services=[service],
            message="Test message",
            context={"key": "value"},
        )

        self.assertFalse(result.proceed)
        self.assertTrue(result.prompt_required)
        self.assertEqual(len(result.inactive_services), 1)
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.context["key"], "value")

    def test_to_dict_empty(self):
        """Test to_dict with default values."""
        result = HookResult()
        data = result.to_dict()

        self.assertTrue(data["proceed"])
        self.assertFalse(data["prompt_required"])
        self.assertEqual(data["inactive_services"], [])
        self.assertEqual(data["auto_started"], [])
        self.assertIsNone(data["message"])

    def test_to_dict_with_services(self):
        """Test to_dict with services."""
        service = ServiceConfig(
            name="test-service",
            display_name="Test Service",
            priority=ServicePriority.PREFERRED,
        )
        result = HookResult(
            inactive_services=[service],
            auto_started=[service],
        )

        data = result.to_dict()

        self.assertEqual(len(data["inactive_services"]), 1)
        self.assertEqual(data["inactive_services"][0]["name"], "test-service")
        self.assertEqual(data["inactive_services"][0]["display_name"], "Test Service")
        self.assertEqual(data["inactive_services"][0]["priority"], "preferred")

        self.assertEqual(len(data["auto_started"]), 1)
        self.assertEqual(data["auto_started"][0]["name"], "test-service")


class TestServiceHookManager(unittest.TestCase):
    """Tests for ServiceHookManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_service_manager = MagicMock(spec=ServiceManager)
        self.hook_manager = ServiceHookManager(
            service_manager=self.mock_service_manager
        )

    def tearDown(self):
        """Clean up."""
        import core.service_hooks
        core.service_hooks._service_hook_manager = None

    def run_async(self, coro):
        """Helper to run async tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def test_init_with_service_manager(self):
        """Test initialization with provided service manager."""
        manager = ServiceHookManager(service_manager=self.mock_service_manager)
        self.assertEqual(manager.service_manager, self.mock_service_manager)

    def test_pre_create_team_hook_no_repo_path(self):
        """Test hook returns early when no repo_path provided."""
        async def test():
            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path=None
            )

            self.assertTrue(result.proceed)
            self.assertFalse(result.prompt_required)
            self.assertEqual(result.inactive_services, [])

        self.run_async(test())

    def test_pre_create_team_hook_all_running(self):
        """Test hook when all services are running."""
        async def test():
            # Mock no inactive services
            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[]
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)
            self.assertFalse(result.prompt_required)
            self.assertEqual(result.inactive_services, [])

        self.run_async(test())

    def test_pre_create_team_hook_required_auto_starts(self):
        """Test that required services are auto-started."""
        async def test():
            required_service = ServiceConfig(
                name="required-svc",
                command="npm start",
                priority=ServicePriority.REQUIRED,
            )

            # Mock inactive services
            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[required_service]
            )

            # Mock successful start
            running_state = ServiceState(
                service=required_service,
                is_running=True,
                session_id="session-123",
            )
            self.mock_service_manager.start_service = AsyncMock(
                return_value=running_state
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)
            self.assertEqual(len(result.auto_started), 1)
            self.assertEqual(result.auto_started[0].name, "required-svc")
            self.mock_service_manager.start_service.assert_called_once()

        self.run_async(test())

    def test_pre_create_team_hook_required_fails(self):
        """Test that hook fails when required service fails to start."""
        async def test():
            required_service = ServiceConfig(
                name="required-svc",
                command="npm start",
                priority=ServicePriority.REQUIRED,
            )

            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[required_service]
            )

            # Mock failed start
            failed_state = ServiceState(
                service=required_service,
                is_running=False,
                error_message="Connection refused",
            )
            self.mock_service_manager.start_service = AsyncMock(
                return_value=failed_state
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertFalse(result.proceed)
            self.assertIn("failed to start", result.message.lower())

        self.run_async(test())

    def test_pre_create_team_hook_preferred_prompts(self):
        """Test that preferred services trigger prompt."""
        async def test():
            preferred_service = ServiceConfig(
                name="preferred-svc",
                display_name="Preferred Service",
                priority=ServicePriority.PREFERRED,
            )

            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[preferred_service]
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="my-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)
            self.assertTrue(result.prompt_required)
            self.assertEqual(len(result.inactive_services), 1)
            self.assertIn("Preferred Service", result.message)
            self.assertIn("my-team", result.message)

        self.run_async(test())

    def test_pre_create_team_hook_optional_notifies(self):
        """Test that optional services generate notification message."""
        async def test():
            optional_service = ServiceConfig(
                name="optional-svc",
                display_name="Optional Service",
                priority=ServicePriority.OPTIONAL,
            )

            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[optional_service]
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)
            self.assertFalse(result.prompt_required)
            self.assertEqual(len(result.inactive_services), 1)
            self.assertIn("Optional Service", result.message)
            self.assertIn("not running", result.message.lower())

        self.run_async(test())

    def test_pre_create_team_hook_quiet_ignored(self):
        """Test that quiet services are ignored."""
        async def test():
            quiet_service = ServiceConfig(
                name="quiet-svc",
                priority=ServicePriority.QUIET,
            )

            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[quiet_service]
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)
            self.assertFalse(result.prompt_required)
            self.assertEqual(result.inactive_services, [])
            self.assertIsNone(result.message)

        self.run_async(test())

    def test_pre_create_team_hook_mixed_priorities(self):
        """Test hook with mixed priority services."""
        async def test():
            required_svc = ServiceConfig(
                name="required",
                command="cmd",
                priority=ServicePriority.REQUIRED,
            )
            preferred_svc = ServiceConfig(
                name="preferred",
                priority=ServicePriority.PREFERRED,
            )
            optional_svc = ServiceConfig(
                name="optional",
                priority=ServicePriority.OPTIONAL,
            )

            self.mock_service_manager.get_inactive_services = AsyncMock(
                return_value=[required_svc, preferred_svc, optional_svc]
            )

            # Required starts successfully
            self.mock_service_manager.start_service = AsyncMock(
                return_value=ServiceState(
                    service=required_svc,
                    is_running=True,
                    session_id="s1"
                )
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            # Should proceed (required started)
            self.assertTrue(result.proceed)
            # Should prompt (preferred inactive)
            self.assertTrue(result.prompt_required)
            # Auto-started should contain required
            self.assertEqual(len(result.auto_started), 1)
            # Inactive should contain preferred and optional
            self.assertEqual(len(result.inactive_services), 2)

        self.run_async(test())

    def test_build_preferred_message_single(self):
        """Test message building for single preferred service."""
        message = self.hook_manager._build_preferred_message(
            ["My Service"],
            "dev-team"
        )

        self.assertIn("My Service", message)
        self.assertIn("dev-team", message)
        self.assertIn("not running", message.lower())

    def test_build_preferred_message_multiple(self):
        """Test message building for multiple preferred services."""
        message = self.hook_manager._build_preferred_message(
            ["Service A", "Service B", "Service C"],
            "dev-team"
        )

        self.assertIn("Service A", message)
        self.assertIn("Service B", message)
        self.assertIn("Service C", message)
        self.assertIn("and", message)

    def test_build_optional_message_single(self):
        """Test message building for single optional service."""
        message = self.hook_manager._build_optional_message(["Optional Svc"])

        self.assertIn("Optional Svc", message)
        self.assertIn("not running", message.lower())

    def test_build_optional_message_multiple(self):
        """Test message building for multiple optional services."""
        message = self.hook_manager._build_optional_message(
            ["Svc A", "Svc B"]
        )

        self.assertIn("Svc A", message)
        self.assertIn("Svc B", message)

    def test_start_services_for_team(self):
        """Test starting services for a team."""
        async def test():
            service = ServiceConfig(name="test-svc", command="npm start")
            self.mock_service_manager.get_merged_services = MagicMock(
                return_value=[service]
            )
            self.mock_service_manager.start_service = AsyncMock(
                return_value=ServiceState(
                    service=service,
                    is_running=True,
                    session_id="s1"
                )
            )

            results = await self.hook_manager.start_services_for_team(
                service_names=["test-svc"],
                repo_path="/some/repo"
            )

            self.assertIn("test-svc", results)
            self.assertTrue(results["test-svc"].is_running)

        self.run_async(test())

    def test_start_services_for_team_not_found(self):
        """Test starting non-existent service."""
        async def test():
            self.mock_service_manager.get_merged_services = MagicMock(
                return_value=[]
            )

            results = await self.hook_manager.start_services_for_team(
                service_names=["nonexistent"],
                repo_path="/some/repo"
            )

            self.assertEqual(results, {})

        self.run_async(test())

    def test_pre_create_team_hook_exception_handling(self):
        """Test hook handles exceptions gracefully."""
        async def test():
            self.mock_service_manager.get_inactive_services = AsyncMock(
                side_effect=Exception("Database error")
            )

            result = await self.hook_manager.pre_create_team_hook(
                team_name="test-team",
                repo_path="/some/repo"
            )

            self.assertTrue(result.proceed)  # Proceed on error
            self.assertIn("error", result.message.lower())

        self.run_async(test())


class TestGetServiceHookManager(unittest.TestCase):
    """Tests for get_service_hook_manager singleton factory."""

    def tearDown(self):
        """Reset global instance."""
        import core.service_hooks
        core.service_hooks._service_hook_manager = None

    def test_returns_same_instance(self):
        """Test that get_service_hook_manager returns same instance."""
        manager1 = get_service_hook_manager()
        manager2 = get_service_hook_manager()
        self.assertIs(manager1, manager2)

    def test_creates_instance_on_first_call(self):
        """Test that first call creates new instance."""
        manager = get_service_hook_manager()
        self.assertIsNotNone(manager)
        self.assertIsInstance(manager, ServiceHookManager)


if __name__ == "__main__":
    unittest.main()
