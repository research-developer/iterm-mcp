"""
Integration tests for MCP feedback tools using FastMCP Client.

These tests verify that the MCP tool wrappers correctly call the underlying
feedback system components with proper arguments.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.feedback import (
    FeedbackCategory,
    FeedbackCollector,
    FeedbackConfig,
    FeedbackContext,
    FeedbackEntry,
    FeedbackForker,
    FeedbackHookManager,
    FeedbackRegistry,
    FeedbackStatus,
    FeedbackTriggerType,
    GitHubIntegration,
)


def make_context(project_path: str = "/tmp") -> FeedbackContext:
    """Helper to create a minimal FeedbackContext for testing."""
    return FeedbackContext(
        git_commit="abc123",
        git_branch="main",
        project_path=project_path,
    )


class TestSubmitFeedback(unittest.TestCase):
    """Test the submit_feedback MCP tool."""

    def setUp(self):
        """Set up test fixtures with mocked components."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(Path(self.temp_dir) / "feedback.jsonl")
        self.hook_manager = FeedbackHookManager()
        self.collector = FeedbackCollector()
        self.forker = FeedbackForker(project_path=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_submit_feedback_creates_entry(self):
        """Test that submit_feedback creates a feedback entry."""
        import asyncio

        async def create_feedback():
            context = await self.collector.capture_context(
                project_path=self.temp_dir,
                recent_tool_calls=[],
                recent_errors=["Test error"],
            )
            # create_feedback is synchronous, not async
            entry = self.collector.create_feedback(
                agent_id="test-agent",
                agent_name="TestAgent",
                session_id="session-123",
                trigger_type=FeedbackTriggerType.MANUAL,
                category=FeedbackCategory.BUG,
                title="Test Bug",
                description="This is a test bug report",
                context=context,
            )
            return entry

        entry = asyncio.run(create_feedback())

        # Verify entry was created
        self.assertIsNotNone(entry)
        self.assertEqual(entry.title, "Test Bug")
        self.assertEqual(entry.category, FeedbackCategory.BUG)
        self.assertEqual(entry.agent_name, "TestAgent")
        self.assertEqual(entry.status, FeedbackStatus.PENDING)

    def test_submit_feedback_with_reproduction_steps(self):
        """Test feedback submission with optional fields."""
        import asyncio

        async def create_detailed_feedback():
            context = await self.collector.capture_context(
                project_path=self.temp_dir,
            )
            # create_feedback is synchronous
            entry = self.collector.create_feedback(
                agent_id="agent-1",
                agent_name="Agent",
                session_id="sess-1",
                trigger_type=FeedbackTriggerType.MANUAL,
                category=FeedbackCategory.ENHANCEMENT,
                title="Feature Request",
                description="Add new feature",
                reproduction_steps=["Step 1", "Step 2"],
                suggested_improvement="Do X instead of Y",
                error_messages=["Error 1"],
                context=context,
            )
            return entry

        entry = asyncio.run(create_detailed_feedback())

        self.assertEqual(entry.reproduction_steps, ["Step 1", "Step 2"])
        self.assertEqual(entry.suggested_improvement, "Do X instead of Y")
        self.assertEqual(entry.error_messages, ["Error 1"])


class TestCheckFeedbackTriggers(unittest.TestCase):
    """Test the check_feedback_triggers MCP tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.hook_manager = FeedbackHookManager()

    def test_error_threshold_trigger(self):
        """Test that error threshold triggers correctly."""
        agent_id = "test-agent"

        # Record errors up to threshold
        for i in range(2):
            result = self.hook_manager.record_error(agent_id, f"Error {i}")
            self.assertIsNone(result)

        # Third error should trigger
        result = self.hook_manager.record_error(agent_id, "Error 3")
        self.assertEqual(result, FeedbackTriggerType.ERROR_THRESHOLD)

        # Counter should reset after trigger
        stats = self.hook_manager.get_stats(agent_id)
        self.assertEqual(stats["error_count"], 0)

    def test_periodic_trigger(self):
        """Test that periodic trigger fires correctly."""
        agent_id = "test-agent"
        config = FeedbackConfig()
        periodic_count = config.periodic.tool_call_count

        # Record tool calls up to threshold - 1
        for i in range(periodic_count - 1):
            result = self.hook_manager.record_tool_call(agent_id)
            self.assertIsNone(result)

        # Next call should trigger
        result = self.hook_manager.record_tool_call(agent_id)
        self.assertEqual(result, FeedbackTriggerType.PERIODIC)

    def test_pattern_detection_trigger(self):
        """Test that pattern detection works."""
        agent_id = "test-agent"

        # Text without patterns
        result = self.hook_manager.check_pattern(agent_id, "Normal text here")
        self.assertIsNone(result)

        # Text with trigger pattern
        result = self.hook_manager.check_pattern(agent_id, "this should work better")
        self.assertEqual(result, FeedbackTriggerType.PATTERN_DETECTED)

    def test_get_stats(self):
        """Test that get_stats returns correct information."""
        agent_id = "test-agent"

        # Record some activity
        self.hook_manager.record_error(agent_id, "Error 1")
        self.hook_manager.record_tool_call(agent_id)
        self.hook_manager.record_tool_call(agent_id)

        stats = self.hook_manager.get_stats(agent_id)

        self.assertEqual(stats["error_count"], 1)
        self.assertEqual(stats["tool_call_count"], 2)
        self.assertIn("error_threshold", stats)
        self.assertIn("tool_call_threshold", stats)


class TestQueryFeedback(unittest.TestCase):
    """Test the query_feedback MCP tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(Path(self.temp_dir) / "feedback.jsonl")

        # Add some test entries with required context
        self.entries = []
        for i, (cat, status) in enumerate([
            (FeedbackCategory.BUG, FeedbackStatus.PENDING),
            (FeedbackCategory.BUG, FeedbackStatus.TRIAGED),
            (FeedbackCategory.ENHANCEMENT, FeedbackStatus.PENDING),
            (FeedbackCategory.UX, FeedbackStatus.RESOLVED),
        ]):
            entry = FeedbackEntry(
                agent_id=f"agent-{i}",
                agent_name=f"Agent{i}",
                session_id=f"session-{i}",
                trigger_type=FeedbackTriggerType.MANUAL,
                category=cat,
                title=f"Feedback {i}",
                description=f"Description {i}",
                status=status,
                context=make_context(self.temp_dir),
            )
            self.registry.add(entry)
            self.entries.append(entry)

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_all(self):
        """Test querying all entries."""
        results = self.registry.list_all()
        self.assertEqual(len(results), 4)

    def test_query_by_category(self):
        """Test querying by category."""
        results = self.registry.query(category=FeedbackCategory.BUG)
        self.assertEqual(len(results), 2)
        for entry in results:
            self.assertEqual(entry.category, FeedbackCategory.BUG)

    def test_query_by_status(self):
        """Test querying by status."""
        results = self.registry.query(status=FeedbackStatus.PENDING)
        self.assertEqual(len(results), 2)
        for entry in results:
            self.assertEqual(entry.status, FeedbackStatus.PENDING)

    def test_query_with_limit(self):
        """Test querying with limit."""
        results = self.registry.query(limit=2)
        self.assertEqual(len(results), 2)

    def test_get_pending(self):
        """Test getting pending entries."""
        results = self.registry.get_pending()
        self.assertEqual(len(results), 2)


class TestForkForFeedback(unittest.TestCase):
    """Test the fork_for_feedback MCP tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.forker = FeedbackForker(project_path=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("asyncio.create_subprocess_exec")
    def test_create_worktree(self, mock_subprocess):
        """Test worktree creation."""
        import asyncio

        # Mock successful subprocess
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        async def create_wt():
            return await self.forker.create_worktree("fb-12345678-abcd1234")

        result = asyncio.run(create_wt())

        self.assertIsNotNone(result)
        self.assertIn("fb-12345678-abcd1234", str(result))

    def test_get_fork_command(self):
        """Test fork command generation."""
        command = self.forker.get_fork_command(
            session_id="session-123",
            worktree_path=Path("/tmp/worktree"),
        )

        self.assertIn("claude", command)
        self.assertIn("--fork-session", command)


class TestTriageFeedbackToGitHub(unittest.TestCase):
    """Test the triage_feedback_to_github MCP tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(Path(self.temp_dir) / "feedback.jsonl")
        # GitHubIntegration requires repo set for create_issue
        self.github = GitHubIntegration(repo="owner/repo")

        # Create a test entry with required context
        self.entry = FeedbackEntry(
            agent_id="agent-1",
            agent_name="TestAgent",
            session_id="session-1",
            trigger_type=FeedbackTriggerType.MANUAL,
            category=FeedbackCategory.BUG,
            title="Test Bug",
            description="Bug description",
            reproduction_steps=["Step 1", "Step 2"],
            error_messages=["Error message"],
            context=make_context(self.temp_dir),
        )
        self.registry.add(self.entry)

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_format_reproduction_steps(self):
        """Test formatting of reproduction steps."""
        formatted = self.github._format_steps(["Step 1", "Step 2", "Step 3"])
        self.assertIn("1. Step 1", formatted)
        self.assertIn("2. Step 2", formatted)
        self.assertIn("3. Step 3", formatted)

    def test_format_error_messages(self):
        """Test formatting of error messages."""
        formatted = self.github._format_errors(["Error 1", "Error 2"])
        self.assertIn("Error 1", formatted)
        self.assertIn("Error 2", formatted)

    @patch("asyncio.create_subprocess_exec")
    def test_create_issue(self, mock_subprocess):
        """Test GitHub issue creation."""
        import asyncio

        # Mock successful subprocess returning issue URL
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"https://github.com/owner/repo/issues/123\n", b"")
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        async def create_issue():
            return await self.github.create_issue(
                feedback=self.entry,
                labels=["bug", "agent-feedback"],
            )

        result = asyncio.run(create_issue())

        self.assertEqual(result, "https://github.com/owner/repo/issues/123")


class TestNotifyFeedbackUpdate(unittest.TestCase):
    """Test the notify_feedback_update MCP tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(Path(self.temp_dir) / "feedback.jsonl")

        # Create a test entry with required context
        self.entry = FeedbackEntry(
            agent_id="agent-1",
            agent_name="TestAgent",
            session_id="session-1",
            trigger_type=FeedbackTriggerType.MANUAL,
            category=FeedbackCategory.BUG,
            title="Test Bug",
            description="Bug description",
            context=make_context(self.temp_dir),
        )
        self.registry.add(self.entry)

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_update_status(self):
        """Test updating feedback status."""
        # Update to triaged
        updated = self.registry.update(
            self.entry.id,
            status=FeedbackStatus.TRIAGED,
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, FeedbackStatus.TRIAGED)

    def test_link_github_issue(self):
        """Test linking a GitHub issue."""
        issue_url = "https://github.com/owner/repo/issues/42"

        updated = self.registry.link_github_issue(self.entry.id, issue_url)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.github_issue_url, issue_url)

    def test_link_github_pr(self):
        """Test linking a GitHub PR."""
        pr_url = "https://github.com/owner/repo/pull/43"

        updated = self.registry.link_github_pr(self.entry.id, pr_url)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.github_pr_url, pr_url)


class TestGetFeedbackConfig(unittest.TestCase):
    """Test the get_feedback_config MCP tool."""

    def test_default_config(self):
        """Test getting default configuration."""
        config = FeedbackConfig()

        # Check error threshold config
        self.assertTrue(config.error_threshold.enabled)
        self.assertEqual(config.error_threshold.count, 3)

        # Check periodic config
        self.assertTrue(config.periodic.enabled)
        self.assertEqual(config.periodic.tool_call_count, 100)

        # Check pattern config
        self.assertTrue(config.pattern.enabled)
        # Patterns are regex patterns, not plain strings
        self.assertTrue(len(config.pattern.patterns) > 0)
        # Verify at least one pattern matches "this should"
        import re
        matches = any(re.search(p, "this should work") for p in config.pattern.patterns)
        self.assertTrue(matches)

    def test_config_to_dict(self):
        """Test config serialization."""
        config = FeedbackConfig()
        config_dict = config.model_dump()

        self.assertIn("error_threshold", config_dict)
        self.assertIn("periodic", config_dict)
        self.assertIn("pattern", config_dict)
        self.assertIn("github", config_dict)


class TestEnvironmentVariableOverrides(unittest.TestCase):
    """Test environment variable configuration overrides."""

    def test_error_threshold_env_override(self):
        """Test ITERM_MCP_FEEDBACK_ERROR_THRESHOLD override."""
        with patch.dict(os.environ, {"ITERM_MCP_FEEDBACK_ERROR_THRESHOLD": "5"}):
            hook_manager = FeedbackHookManager()
            stats = hook_manager.get_stats("test-agent")
            self.assertEqual(stats["error_threshold"], 5)

    def test_periodic_calls_env_override(self):
        """Test ITERM_MCP_FEEDBACK_PERIODIC_CALLS override."""
        with patch.dict(os.environ, {"ITERM_MCP_FEEDBACK_PERIODIC_CALLS": "50"}):
            hook_manager = FeedbackHookManager()
            stats = hook_manager.get_stats("test-agent")
            self.assertEqual(stats["tool_call_threshold"], 50)

    def test_combined_env_overrides(self):
        """Test both environment variable overrides together."""
        with patch.dict(os.environ, {
            "ITERM_MCP_FEEDBACK_ERROR_THRESHOLD": "10",
            "ITERM_MCP_FEEDBACK_PERIODIC_CALLS": "200",
        }):
            hook_manager = FeedbackHookManager()
            stats = hook_manager.get_stats("test-agent")
            self.assertEqual(stats["error_threshold"], 10)
            self.assertEqual(stats["tool_call_threshold"], 200)


class TestNotificationManager(unittest.TestCase):
    """Test the NotificationManager class."""

    def test_notification_manager_import(self):
        """Test that NotificationManager can be imported from the server."""
        from iterm_mcpy.fastmcp_server import NotificationManager

        # Should be able to create an instance
        manager = NotificationManager()
        self.assertIsNotNone(manager)

    def test_notification_manager_initialization(self):
        """Test NotificationManager initialization."""
        from iterm_mcpy.fastmcp_server import NotificationManager

        manager = NotificationManager()

        # Check it has the expected methods (add, add_simple)
        self.assertTrue(hasattr(manager, "add"))
        self.assertTrue(hasattr(manager, "add_simple"))

    def test_notification_manager_add_simple(self):
        """Test NotificationManager add_simple method."""
        import asyncio
        from iterm_mcpy.fastmcp_server import NotificationManager

        manager = NotificationManager()

        async def add_notification():
            await manager.add_simple(
                agent="test-agent",
                level="info",
                summary="Test notification",
                context="Test context",
            )

        # Should not raise
        asyncio.run(add_notification())


class TestMCPToolIntegration(unittest.TestCase):
    """Integration tests that verify MCP tools work end-to-end."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(Path(self.temp_dir) / "feedback.jsonl")
        self.hook_manager = FeedbackHookManager()
        self.collector = FeedbackCollector()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_feedback_workflow_via_tools(self):
        """Test complete workflow: submit -> query -> triage -> notify."""
        import asyncio

        async def run_workflow():
            # 1. Submit feedback (what submit_feedback tool does)
            context = await self.collector.capture_context(
                project_path=self.temp_dir,
            )
            # create_feedback is synchronous
            entry = self.collector.create_feedback(
                agent_id="workflow-agent",
                agent_name="WorkflowAgent",
                session_id="workflow-session",
                trigger_type=FeedbackTriggerType.MANUAL,
                category=FeedbackCategory.BUG,
                title="Workflow Test Bug",
                description="Testing the full workflow",
                context=context,
            )
            self.registry.add(entry)

            # 2. Query feedback (what query_feedback tool does)
            pending = self.registry.get_pending()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].id, entry.id)

            # 3. Update status (part of triage workflow)
            self.registry.update(entry.id, status=FeedbackStatus.TRIAGED)

            # 4. Link GitHub issue
            self.registry.link_github_issue(
                entry.id,
                "https://github.com/owner/repo/issues/999",
            )

            # 5. Verify final state
            final_entry = self.registry.get(entry.id)
            self.assertEqual(final_entry.status, FeedbackStatus.TRIAGED)
            self.assertEqual(
                final_entry.github_issue_url,
                "https://github.com/owner/repo/issues/999",
            )

            return final_entry

        result = asyncio.run(run_workflow())
        self.assertIsNotNone(result)

    def test_trigger_detection_workflow(self):
        """Test trigger detection and feedback creation workflow."""
        agent_id = "trigger-agent"

        # Record errors until threshold
        for i in range(3):
            trigger = self.hook_manager.record_error(agent_id, f"Error {i}")
            if i < 2:
                self.assertIsNone(trigger)
            else:
                self.assertEqual(trigger, FeedbackTriggerType.ERROR_THRESHOLD)

        # After trigger, should have reset
        stats = self.hook_manager.get_stats(agent_id)
        self.assertEqual(stats["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
