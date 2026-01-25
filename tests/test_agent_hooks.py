"""Tests for agent lifecycle hooks."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from core.agent_hooks import (
    AgentHookManager,
    ColorSpec,
    GlobalHooksConfig,
    HookActionResult,
    HookEvent,
    HookEventType,
    RepoHooksConfig,
    SessionStyle,
    get_agent_hook_manager,
    reset_agent_hook_manager,
)


class TestAgentHooksConfig(IsolatedAsyncioTestCase):
    """Tests for hook configuration loading."""

    def test_color_spec_creation(self):
        """Test ColorSpec model creation."""
        color = ColorSpec(r=255, g=128, b=64)
        self.assertEqual(color.r, 255)
        self.assertEqual(color.g, 128)
        self.assertEqual(color.b, 64)
        self.assertEqual(color.a, 255)  # default alpha

    def test_color_spec_with_aliases(self):
        """Test ColorSpec with alias field names."""
        color = ColorSpec(red=100, green=150, blue=200, alpha=128)
        self.assertEqual(color.r, 100)
        self.assertEqual(color.g, 150)
        self.assertEqual(color.b, 200)
        self.assertEqual(color.a, 128)

    def test_session_style_creation(self):
        """Test SessionStyle model creation."""
        style = SessionStyle(
            background_color=ColorSpec(r=30, g=40, b=50),
            tab_color=ColorSpec(r=100, g=150, b=200),
            badge="🚀 {team}"
        )
        self.assertIsNotNone(style.background_color)
        self.assertEqual(style.background_color.r, 30)
        self.assertEqual(style.badge, "🚀 {team}")

    def test_repo_hooks_config_defaults(self):
        """Test RepoHooksConfig default values."""
        config = RepoHooksConfig()
        self.assertIsNone(config.team)
        self.assertIsNone(config.style)
        self.assertEqual(config.auto_services, [])
        self.assertEqual(config.env, {})
        self.assertTrue(config.pass_session_id)
        self.assertEqual(config.claude_session_id_env, "CLAUDE_SESSION_ID")

    def test_global_hooks_config_defaults(self):
        """Test GlobalHooksConfig default values."""
        config = GlobalHooksConfig()
        self.assertTrue(config.enabled)
        self.assertTrue(config.monitor_path_changes)
        self.assertTrue(config.auto_team_assignment)
        self.assertTrue(config.fallback_team_from_repo)
        self.assertTrue(config.pass_session_id_default)
        self.assertEqual(config.repo_config_filename, ".iterm/hooks.json")


class TestAgentHookManager(IsolatedAsyncioTestCase):
    """Tests for AgentHookManager."""

    def setUp(self):
        """Reset global hook manager before each test."""
        reset_agent_hook_manager()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Cleanup after tests."""
        reset_agent_hook_manager()
        # Cleanup temp dir
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hook_manager_creation(self):
        """Test AgentHookManager creation with default config."""
        manager = AgentHookManager()
        self.assertTrue(manager.config.enabled)
        self.assertEqual(len(manager._session_paths), 0)

    def test_hook_manager_singleton(self):
        """Test get_agent_hook_manager returns singleton."""
        manager1 = get_agent_hook_manager()
        manager2 = get_agent_hook_manager()
        self.assertIs(manager1, manager2)

    def test_find_repo_root_with_git(self):
        """Test finding repo root with .git directory."""
        # Create a fake repo structure
        repo_path = Path(self.temp_dir).resolve() / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        subdir = repo_path / "src" / "components"
        subdir.mkdir(parents=True)

        manager = AgentHookManager()
        found_root = manager.find_repo_root(str(subdir))
        self.assertEqual(found_root, str(repo_path))

    def test_find_repo_root_with_iterm(self):
        """Test finding repo root with .iterm directory."""
        repo_path = Path(self.temp_dir).resolve() / "test-project"
        repo_path.mkdir()
        (repo_path / ".iterm").mkdir()
        subdir = repo_path / "lib"
        subdir.mkdir()

        manager = AgentHookManager()
        found_root = manager.find_repo_root(str(subdir))
        self.assertEqual(found_root, str(repo_path))

    def test_find_repo_root_not_found(self):
        """Test finding repo root when not in a repo."""
        manager = AgentHookManager()
        found_root = manager.find_repo_root("/tmp")
        self.assertIsNone(found_root)

    def test_load_repo_config(self):
        """Test loading repo config from .iterm/hooks.json."""
        # Create a repo with config
        repo_path = Path(self.temp_dir) / "my-project"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        config_dir = repo_path / ".iterm"
        config_dir.mkdir()

        config_data = {
            "team": "my-team",
            "style": {
                "background_color": {"r": 30, "g": 30, "b": 40},
                "badge": "🔧 {repo}"
            },
            "pass_session_id": True
        }
        with open(config_dir / "hooks.json", "w") as f:
            json.dump(config_data, f)

        manager = AgentHookManager()
        config = manager.load_repo_config(str(repo_path))

        self.assertIsNotNone(config)
        self.assertEqual(config.team, "my-team")
        self.assertIsNotNone(config.style)
        self.assertEqual(config.style.badge, "🔧 {repo}")

    def test_load_repo_config_not_found(self):
        """Test loading repo config when not present."""
        repo_path = Path(self.temp_dir) / "no-config-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = AgentHookManager()
        config = manager.load_repo_config(str(repo_path))
        self.assertIsNone(config)

    def test_get_team_for_repo_explicit(self):
        """Test getting team name from explicit config."""
        repo_path = Path(self.temp_dir) / "team-project"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        config_dir = repo_path / ".iterm"
        config_dir.mkdir()

        with open(config_dir / "hooks.json", "w") as f:
            json.dump({"team": "explicit-team"}, f)

        manager = AgentHookManager()
        team = manager.get_team_for_repo(str(repo_path))
        self.assertEqual(team, "explicit-team")

    def test_get_team_for_repo_fallback(self):
        """Test getting team name from repo directory name."""
        repo_path = Path(self.temp_dir) / "my-awesome-project"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = AgentHookManager()
        team = manager.get_team_for_repo(str(repo_path))
        self.assertEqual(team, "my-awesome-project")

    async def test_on_path_changed_basic(self):
        """Test basic path change handling."""
        manager = AgentHookManager()
        result = await manager.on_path_changed("session-1", "/some/path")

        self.assertTrue(result.success)
        self.assertIn("Path changed", result.message)

    async def test_on_path_changed_enters_repo(self):
        """Test path change when entering a repo."""
        # Create a repo
        repo_path = Path(self.temp_dir) / "enter-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = AgentHookManager()

        # Start outside repo
        await manager.on_path_changed("session-2", "/tmp")

        # Enter repo
        result = await manager.on_path_changed("session-2", str(repo_path))

        self.assertTrue(result.success)
        self.assertEqual(result.team_assigned, "enter-repo")
        # Actions are formatted as "action: value"
        self.assertTrue(any("team_assigned" in a for a in result.actions_taken))

    async def test_on_agent_started(self):
        """Test agent started hook."""
        repo_path = Path(self.temp_dir) / "started-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = AgentHookManager()
        result = await manager.on_agent_started(
            "session-3",
            "test-agent",
            str(repo_path)
        )

        self.assertTrue(result.success)
        self.assertEqual(result.team_assigned, "started-repo")

    async def test_on_agent_stopped(self):
        """Test agent stopped hook."""
        manager = AgentHookManager()

        # First start the agent
        await manager.on_path_changed("session-4", "/some/path")
        self.assertIn("session-4", manager._session_paths)

        # Then stop
        result = await manager.on_agent_stopped("session-4", "test-agent")

        self.assertTrue(result.success)
        self.assertNotIn("session-4", manager._session_paths)

    async def test_callback_registration(self):
        """Test registering and triggering callbacks."""
        manager = AgentHookManager()
        events_received = []

        async def on_dir_changed(event: HookEvent):
            events_received.append(event)

        manager.register_callback(HookEventType.DIRECTORY_CHANGED, on_dir_changed)

        await manager.on_path_changed("session-5", "/new/path")

        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0].event_type, HookEventType.DIRECTORY_CHANGED)
        self.assertEqual(events_received[0].session_id, "session-5")
        self.assertEqual(events_received[0].new_path, "/new/path")

    def test_get_stats(self):
        """Test getting hook manager stats."""
        manager = AgentHookManager()
        stats = manager.get_stats()

        self.assertIn("enabled", stats)
        self.assertIn("tracked_sessions", stats)
        self.assertIn("cached_repo_configs", stats)
        self.assertTrue(stats["enabled"])
        self.assertEqual(stats["tracked_sessions"], 0)

    def test_clear_cache(self):
        """Test clearing repo config cache."""
        repo_path = Path(self.temp_dir) / "cache-test"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = AgentHookManager()

        # Load config (populates cache)
        manager.load_repo_config(str(repo_path))
        self.assertEqual(len(manager._repo_config_cache), 1)

        # Clear cache
        manager.clear_cache()
        self.assertEqual(len(manager._repo_config_cache), 0)


class TestSessionIdPatterns(IsolatedAsyncioTestCase):
    """Tests for session ID pattern matching utilities."""

    def test_valid_session_id(self):
        """Test is_valid_session_id with valid UUIDs."""
        from core.agent_hooks import is_valid_session_id

        # Standard UUID formats (lowercase)
        self.assertTrue(is_valid_session_id("550e8400-e29b-41d4-a716-446655440000"))
        self.assertTrue(is_valid_session_id("f9a88c53-2c5f-405c-a2f7-0907bf35e318"))

        # Uppercase should also work (case insensitive)
        self.assertTrue(is_valid_session_id("550E8400-E29B-41D4-A716-446655440000"))
        self.assertTrue(is_valid_session_id("F9A88C53-2C5F-405C-A2F7-0907BF35E318"))

        # Mixed case
        self.assertTrue(is_valid_session_id("550e8400-E29B-41d4-A716-446655440000"))

    def test_invalid_session_id(self):
        """Test is_valid_session_id rejects invalid formats."""
        from core.agent_hooks import is_valid_session_id

        # Too short
        self.assertFalse(is_valid_session_id("550e8400"))

        # Missing dashes
        self.assertFalse(is_valid_session_id("550e8400e29b41d4a716446655440000"))

        # Wrong segment lengths
        self.assertFalse(is_valid_session_id("550e840-e29b-41d4-a716-446655440000"))

        # Empty string
        self.assertFalse(is_valid_session_id(""))

        # Random text
        self.assertFalse(is_valid_session_id("not-a-uuid"))

        # Invalid characters
        self.assertFalse(is_valid_session_id("550e8400-e29b-41d4-a716-44665544000g"))

    def test_extract_session_ids(self):
        """Test extracting session IDs from text."""
        from core.agent_hooks import extract_session_ids

        text = """
        Starting session 550e8400-e29b-41d4-a716-446655440000 in /Users/test
        Agent f9a88c53-2c5f-405c-a2f7-0907bf35e318 connected to session 550e8400-e29b-41d4-a716-446655440000
        """

        ids = extract_session_ids(text)

        # Should find 3 IDs (one appears twice)
        self.assertEqual(len(ids), 3)
        self.assertIn("550e8400-e29b-41d4-a716-446655440000", ids)
        self.assertIn("f9a88c53-2c5f-405c-a2f7-0907bf35e318", ids)

    def test_extract_session_ids_none_found(self):
        """Test extract_session_ids with no IDs in text."""
        from core.agent_hooks import extract_session_ids

        text = "No session IDs here, just regular text."
        ids = extract_session_ids(text)
        self.assertEqual(ids, [])

    def test_extract_session_ids_lowercase(self):
        """Test that extracted IDs are normalized to lowercase."""
        from core.agent_hooks import extract_session_ids

        text = "Session 550E8400-E29B-41D4-A716-446655440000 started"
        ids = extract_session_ids(text)

        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0], "550e8400-e29b-41d4-a716-446655440000")


class TestManageAgentHooksModels(IsolatedAsyncioTestCase):
    """Tests for ManageAgentHooksRequest/Response models."""

    def test_request_model_get_config(self):
        """Test ManageAgentHooksRequest for get_config operation."""
        from core.models import ManageAgentHooksRequest
        req = ManageAgentHooksRequest(operation="get_config")
        self.assertEqual(req.operation, "get_config")

    def test_request_model_set_variable(self):
        """Test ManageAgentHooksRequest for set_variable operation."""
        from core.models import ManageAgentHooksRequest
        req = ManageAgentHooksRequest(
            operation="set_variable",
            session_id="test-session",
            variable_name="hooks_enabled",
            variable_value="false"
        )
        self.assertEqual(req.operation, "set_variable")
        self.assertEqual(req.session_id, "test-session")
        self.assertEqual(req.variable_name, "hooks_enabled")
        self.assertEqual(req.variable_value, "false")

    def test_request_model_get_variable(self):
        """Test ManageAgentHooksRequest for get_variable operation."""
        from core.models import ManageAgentHooksRequest
        req = ManageAgentHooksRequest(
            operation="get_variable",
            session_id="test-session",
            variable_name="team_override"
        )
        self.assertEqual(req.operation, "get_variable")
        self.assertEqual(req.session_id, "test-session")
        self.assertEqual(req.variable_name, "team_override")

    def test_response_model(self):
        """Test ManageAgentHooksResponse model."""
        from core.models import ManageAgentHooksResponse
        resp = ManageAgentHooksResponse(
            operation="set_variable",
            success=True,
            data={"variable_name": "hooks_enabled", "variable_value": "true"}
        )
        self.assertEqual(resp.operation, "set_variable")
        self.assertTrue(resp.success)
        self.assertEqual(resp.data["variable_value"], "true")

    def test_response_model_error(self):
        """Test ManageAgentHooksResponse with error."""
        from core.models import ManageAgentHooksResponse
        resp = ManageAgentHooksResponse(
            operation="get_variable",
            success=False,
            error="session_id is required"
        )
        self.assertFalse(resp.success)
        self.assertEqual(resp.error, "session_id is required")


if __name__ == "__main__":
    import unittest
    unittest.main()
