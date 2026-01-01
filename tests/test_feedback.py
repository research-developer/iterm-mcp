"""Tests for the feedback system."""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.feedback import (
    FeedbackCategory,
    FeedbackStatus,
    FeedbackTriggerType,
    FeedbackContext,
    FeedbackEntry,
    FeedbackConfig,
    ErrorThresholdConfig,
    PeriodicConfig,
    PatternConfig,
    GitHubConfig,
    FeedbackHookManager,
    FeedbackCollector,
    FeedbackRegistry,
    FeedbackForker,
    GitHubIntegration,
)


class TestFeedbackEnums(unittest.TestCase):
    """Test feedback enums."""

    def test_feedback_category_values(self):
        """Test FeedbackCategory enum values."""
        self.assertEqual(FeedbackCategory.BUG.value, "bug")
        self.assertEqual(FeedbackCategory.ENHANCEMENT.value, "enhancement")
        self.assertEqual(FeedbackCategory.UX.value, "ux")
        self.assertEqual(FeedbackCategory.PERFORMANCE.value, "performance")
        self.assertEqual(FeedbackCategory.DOCUMENTATION.value, "documentation")

    def test_feedback_status_values(self):
        """Test FeedbackStatus enum values."""
        self.assertEqual(FeedbackStatus.PENDING.value, "pending")
        self.assertEqual(FeedbackStatus.TRIAGED.value, "triaged")
        self.assertEqual(FeedbackStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(FeedbackStatus.RESOLVED.value, "resolved")
        self.assertEqual(FeedbackStatus.TESTING.value, "testing")
        self.assertEqual(FeedbackStatus.CLOSED.value, "closed")

    def test_feedback_trigger_type_values(self):
        """Test FeedbackTriggerType enum values."""
        self.assertEqual(FeedbackTriggerType.MANUAL.value, "manual")
        self.assertEqual(FeedbackTriggerType.ERROR_THRESHOLD.value, "error_threshold")
        self.assertEqual(FeedbackTriggerType.PERIODIC.value, "periodic")
        self.assertEqual(FeedbackTriggerType.PATTERN_DETECTED.value, "pattern_detected")


class TestFeedbackContext(unittest.TestCase):
    """Test FeedbackContext model."""

    def test_context_creation(self):
        """Test creating a feedback context."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path/to/project"
        )
        self.assertEqual(context.git_commit, "abc123")
        self.assertEqual(context.git_branch, "main")
        self.assertEqual(context.project_path, "/path/to/project")
        self.assertEqual(context.recent_tool_calls, [])
        self.assertEqual(context.recent_errors, [])

    def test_context_with_optional_fields(self):
        """Test context with all optional fields."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="feature/test",
            git_diff="+ added line",
            project_path="/path/to/project",
            recent_tool_calls=[{"tool": "test", "args": {}}],
            recent_errors=["Error 1", "Error 2"],
            terminal_output_snapshot="$ ls\nfile.py"
        )
        self.assertEqual(context.git_diff, "+ added line")
        self.assertEqual(len(context.recent_tool_calls), 1)
        self.assertEqual(len(context.recent_errors), 2)


class TestFeedbackEntry(unittest.TestCase):
    """Test FeedbackEntry model."""

    def test_entry_creation(self):
        """Test creating a feedback entry."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path/to/project"
        )
        entry = FeedbackEntry(
            agent_id="agent-1",
            agent_name="Claude",
            session_id="session-123",
            trigger_type=FeedbackTriggerType.MANUAL,
            context=context,
            category=FeedbackCategory.ENHANCEMENT,
            title="Improve error handling",
            description="The error messages could be more helpful."
        )

        # Check ID format
        self.assertTrue(entry.id.startswith("fb-"))
        self.assertEqual(entry.status, FeedbackStatus.PENDING)
        self.assertEqual(entry.category, FeedbackCategory.ENHANCEMENT)
        self.assertEqual(entry.title, "Improve error handling")

    def test_entry_with_reproduction_steps(self):
        """Test entry with reproduction steps."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path"
        )
        entry = FeedbackEntry(
            agent_id="agent-1",
            agent_name="Claude",
            session_id="session-123",
            trigger_type=FeedbackTriggerType.MANUAL,
            context=context,
            category=FeedbackCategory.BUG,
            title="Bug title",
            description="Bug description",
            reproduction_steps=["Step 1", "Step 2", "Step 3"],
            error_messages=["Error occurred"]
        )
        self.assertEqual(len(entry.reproduction_steps), 3)
        self.assertEqual(len(entry.error_messages), 1)


class TestFeedbackConfig(unittest.TestCase):
    """Test FeedbackConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FeedbackConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.error_threshold.count, 3)
        self.assertEqual(config.periodic.tool_call_count, 100)
        # Check that default patterns are regex patterns
        self.assertTrue(len(config.pattern.patterns) > 0)
        self.assertTrue(any("should" in p for p in config.pattern.patterns))

    def test_custom_config(self):
        """Test custom configuration."""
        config = FeedbackConfig(
            enabled=True,
            error_threshold=ErrorThresholdConfig(enabled=True, count=5),
            periodic=PeriodicConfig(enabled=False, tool_call_count=50),
            pattern=PatternConfig(enabled=True, patterns=[r"custom\s+pattern"]),
            github=GitHubConfig(repo="test/repo", default_labels=["test"])
        )
        self.assertEqual(config.error_threshold.count, 5)
        self.assertEqual(config.periodic.tool_call_count, 50)
        self.assertFalse(config.periodic.enabled)


class TestFeedbackHookManager(unittest.TestCase):
    """Test FeedbackHookManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        config = FeedbackConfig(
            error_threshold=ErrorThresholdConfig(enabled=True, count=3),
            periodic=PeriodicConfig(enabled=True, tool_call_count=10),  # Min is 10
            pattern=PatternConfig(enabled=True, patterns=[
                r"this\s+should",
                r"better\s+if",
                r"it\s+would\s+be\s+nice"
            ])
        )
        self.hook_manager = FeedbackHookManager(
            config=config,
            config_path=Path(self.temp_dir) / "config.json"
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_error_no_trigger(self):
        """Test recording errors below threshold."""
        # Record 2 errors - should not trigger
        result1 = self.hook_manager.record_error("agent-1", "Error 1")
        result2 = self.hook_manager.record_error("agent-1", "Error 2")
        self.assertIsNone(result1)
        self.assertIsNone(result2)

    def test_error_threshold_trigger(self):
        """Test error threshold triggering."""
        # Record 3 errors - should trigger
        self.hook_manager.record_error("agent-1", "Error 1")
        self.hook_manager.record_error("agent-1", "Error 2")
        result = self.hook_manager.record_error("agent-1", "Error 3")
        self.assertEqual(result, FeedbackTriggerType.ERROR_THRESHOLD)

    def test_error_threshold_reset_after_trigger(self):
        """Test that error count resets after trigger."""
        # Trigger once
        self.hook_manager.record_error("agent-1", "Error 1")
        self.hook_manager.record_error("agent-1", "Error 2")
        self.hook_manager.record_error("agent-1", "Error 3")  # Triggers

        # Next error should not trigger (count reset)
        result = self.hook_manager.record_error("agent-1", "Error 4")
        self.assertIsNone(result)

    def test_record_tool_call(self):
        """Test recording tool calls."""
        # Record 9 calls - should not trigger
        for i in range(9):
            result = self.hook_manager.record_tool_call("agent-1")
            self.assertIsNone(result)

        # 10th call should trigger
        result = self.hook_manager.record_tool_call("agent-1")
        self.assertEqual(result, FeedbackTriggerType.PERIODIC)

    def test_periodic_reset_after_trigger(self):
        """Test that tool count resets after trigger."""
        # Trigger once
        for _ in range(10):
            self.hook_manager.record_tool_call("agent-1")

        # Next call should not trigger (count reset)
        result = self.hook_manager.record_tool_call("agent-1")
        self.assertIsNone(result)

    def test_pattern_detection(self):
        """Test pattern detection."""
        # Should match
        result = self.hook_manager.check_pattern(
            "agent-1",
            "I think this should work differently"
        )
        self.assertEqual(result, FeedbackTriggerType.PATTERN_DETECTED)

        # Should match (case insensitive)
        self.hook_manager.clear_state("agent-1")  # Clear pending trigger
        result = self.hook_manager.check_pattern(
            "agent-1",
            "This Should Be Changed"
        )
        self.assertEqual(result, FeedbackTriggerType.PATTERN_DETECTED)

        # Should not match
        self.hook_manager.clear_state("agent-1")
        result = self.hook_manager.check_pattern(
            "agent-1",
            "Everything works fine"
        )
        self.assertIsNone(result)

    def test_disabled_triggers(self):
        """Test disabled triggers don't fire."""
        # Create manager with disabled error threshold
        config = FeedbackConfig(
            error_threshold=ErrorThresholdConfig(enabled=False, count=1)
        )
        manager = FeedbackHookManager(
            config=config,
            config_path=Path(self.temp_dir) / "disabled.json"
        )

        # Should not trigger even though count is reached
        result = manager.record_error("agent-1", "Error")
        self.assertIsNone(result)

    def test_get_stats(self):
        """Test getting agent stats."""
        self.hook_manager.record_error("agent-1", "Error 1")
        self.hook_manager.record_tool_call("agent-1")
        self.hook_manager.record_tool_call("agent-1")

        stats = self.hook_manager.get_stats("agent-1")
        self.assertEqual(stats["error_count"], 1)
        self.assertEqual(stats["tool_call_count"], 2)
        self.assertEqual(stats["error_threshold"], 3)
        self.assertEqual(stats["tool_call_threshold"], 10)

    def test_clear_state(self):
        """Test clearing agent state."""
        self.hook_manager.record_error("agent-1", "Error 1")
        self.hook_manager.record_tool_call("agent-1")
        self.hook_manager.clear_state("agent-1")

        stats = self.hook_manager.get_stats("agent-1")
        self.assertEqual(stats["error_count"], 0)
        self.assertEqual(stats["tool_call_count"], 0)


class TestFeedbackCollector(unittest.TestCase):
    """Test FeedbackCollector functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.collector = FeedbackCollector(
            feedback_dir=Path(self.temp_dir)
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_capture_context(self):
        """Test capturing feedback context."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            context = loop.run_until_complete(
                self.collector.capture_context(
                    project_path=os.getcwd(),
                    recent_tool_calls=[{"tool": "test"}],
                    recent_errors=["Error 1"]
                )
            )

            # Should have git info (or defaults if not in git repo)
            self.assertIsNotNone(context.git_commit)
            self.assertIsNotNone(context.git_branch)
            self.assertIsNotNone(context.project_path)
            self.assertEqual(context.recent_errors, ["Error 1"])
        finally:
            loop.close()

    def test_create_feedback(self):
        """Test creating feedback entry."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path"
        )
        entry = self.collector.create_feedback(
            agent_name="Claude",
            agent_id="agent-1",
            session_id="session-123",
            trigger_type=FeedbackTriggerType.MANUAL,
            category=FeedbackCategory.ENHANCEMENT,
            title="Test feedback",
            description="Test description",
            context=context,
        )

        self.assertTrue(entry.id.startswith("fb-"))
        self.assertEqual(entry.title, "Test feedback")
        self.assertEqual(entry.agent_name, "Claude")


class TestFeedbackRegistry(unittest.TestCase):
    """Test FeedbackRegistry functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_entry(self, **overrides):
        """Helper to create a feedback entry."""
        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path"
        )
        defaults = {
            "agent_id": "agent-1",
            "agent_name": "Claude",
            "session_id": "session-123",
            "trigger_type": FeedbackTriggerType.MANUAL,
            "context": context,
            "category": FeedbackCategory.ENHANCEMENT,
            "title": "Test feedback",
            "description": "Test description"
        }
        defaults.update(overrides)
        return FeedbackEntry(**defaults)

    def test_add_entry(self):
        """Test adding a feedback entry."""
        entry = self._create_entry()
        self.registry.add(entry)

        # Verify entry was saved
        retrieved = self.registry.get(entry.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Test feedback")

    def test_query_entries(self):
        """Test querying entries with filters."""
        # Create entries with different categories
        entries = [
            self._create_entry(category=FeedbackCategory.BUG, title="Bug 1"),
            self._create_entry(category=FeedbackCategory.ENHANCEMENT, title="Enhancement 1"),
            self._create_entry(
                category=FeedbackCategory.BUG,
                agent_name="Gemini",
                trigger_type=FeedbackTriggerType.ERROR_THRESHOLD,
                title="Bug 2"
            ),
        ]

        for entry in entries:
            self.registry.add(entry)

        # Query by category
        bugs = self.registry.query(category=FeedbackCategory.BUG)
        self.assertEqual(len(bugs), 2)

        # Query by agent
        claude_entries = self.registry.query(agent_name="Claude")
        self.assertEqual(len(claude_entries), 2)

        # Query all
        all_entries = self.registry.query()
        self.assertEqual(len(all_entries), 3)

    def test_update_entry(self):
        """Test updating an entry."""
        entry = self._create_entry()
        self.registry.add(entry)

        # Update the entry
        updated = self.registry.update(
            entry.id,
            status=FeedbackStatus.TRIAGED,
            github_issue_url="https://github.com/test/repo/issues/1"
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, FeedbackStatus.TRIAGED)
        self.assertEqual(updated.github_issue_url, "https://github.com/test/repo/issues/1")

    def test_remove_entry(self):
        """Test removing an entry."""
        entry = self._create_entry()
        self.registry.add(entry)

        success = self.registry.remove(entry.id)
        self.assertTrue(success)

        # Should not be findable
        self.assertIsNone(self.registry.get(entry.id))

    def test_persistence(self):
        """Test that entries persist across registry instances."""
        entry = self._create_entry(title="Persistent entry")
        self.registry.add(entry)
        entry_id = entry.id

        # Create new registry instance pointing to same directory
        new_registry = FeedbackRegistry(data_dir=self.temp_dir)

        # Should be able to retrieve entry
        retrieved = new_registry.get(entry_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Persistent entry")


class TestFeedbackForker(unittest.TestCase):
    """Test FeedbackForker functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.forker = FeedbackForker(project_path=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('core.feedback.asyncio.create_subprocess_exec')
    def test_create_worktree(self, mock_subprocess):
        """Test creating a feedback worktree."""
        # Mock successful git worktree command
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            worktree_path = loop.run_until_complete(
                self.forker.create_worktree("fb-12345678")
            )

            # Verify git worktree add was called
            mock_subprocess.assert_called()
            self.assertIn("feedback-fb-12345678", str(worktree_path))
        finally:
            loop.close()

    @patch('core.feedback.asyncio.create_subprocess_exec')
    @patch('pathlib.Path.exists', return_value=True)
    def test_cleanup_worktree(self, mock_exists, mock_subprocess):
        """Test cleaning up a worktree."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                self.forker.cleanup_worktree("fb-12345678")
            )

            self.assertTrue(success)
            mock_subprocess.assert_called()
        finally:
            loop.close()


class TestGitHubIntegration(unittest.TestCase):
    """Test GitHubIntegration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.github = GitHubIntegration(repo="test/repo")

    def test_format_steps(self):
        """Test formatting reproduction steps."""
        # Test with steps
        formatted = self.github._format_steps(["Step 1", "Step 2", "Step 3"])
        self.assertIn("1. Step 1", formatted)
        self.assertIn("2. Step 2", formatted)
        self.assertIn("3. Step 3", formatted)

        # Test without steps
        formatted = self.github._format_steps(None)
        self.assertEqual(formatted, "N/A")

    def test_format_errors(self):
        """Test formatting error messages."""
        # Test with errors
        formatted = self.github._format_errors(["Error 1", "Error 2"])
        self.assertIn("Error 1", formatted)
        self.assertIn("Error 2", formatted)

        # Test without errors
        formatted = self.github._format_errors(None)
        self.assertEqual(formatted, "No errors recorded")

    @patch('core.feedback.asyncio.create_subprocess_exec')
    def test_create_issue(self, mock_subprocess):
        """Test creating a GitHub issue."""
        # Mock gh CLI response
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"https://github.com/test/repo/issues/123",
            b""
        )
        mock_subprocess.return_value = mock_process

        context = FeedbackContext(
            git_commit="abc123",
            git_branch="main",
            project_path="/path"
        )
        entry = FeedbackEntry(
            agent_id="agent-1",
            agent_name="Claude",
            session_id="session-123",
            trigger_type=FeedbackTriggerType.MANUAL,
            context=context,
            category=FeedbackCategory.ENHANCEMENT,
            title="Test issue",
            description="Test description"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            issue_url = loop.run_until_complete(
                self.github.create_issue(entry)
            )

            self.assertEqual(issue_url, "https://github.com/test/repo/issues/123")
            mock_subprocess.assert_called()
        finally:
            loop.close()


class TestIntegration(unittest.TestCase):
    """Integration tests for the feedback system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = FeedbackRegistry(data_dir=self.temp_dir)
        config = FeedbackConfig(
            error_threshold=ErrorThresholdConfig(enabled=True, count=2)
        )
        self.hook_manager = FeedbackHookManager(
            config=config,
            config_path=Path(self.temp_dir) / "config.json"
        )
        self.collector = FeedbackCollector(
            feedback_dir=Path(self.temp_dir) / "feedback"
        )

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_feedback_workflow(self):
        """Test complete feedback workflow from trigger to storage."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Simulate error threshold trigger
            self.hook_manager.record_error("agent-1", "Error 1")
            trigger = self.hook_manager.record_error("agent-1", "Error 2")
            self.assertEqual(trigger, FeedbackTriggerType.ERROR_THRESHOLD)

            # Collect context
            context = loop.run_until_complete(
                self.collector.capture_context(
                    project_path=os.getcwd(),
                    recent_errors=["Error 1", "Error 2"]
                )
            )

            # Create entry
            entry = self.collector.create_feedback(
                agent_name="Claude",
                agent_id="agent-1",
                session_id="session-123",
                trigger_type=FeedbackTriggerType.ERROR_THRESHOLD,
                category=FeedbackCategory.BUG,
                title="Multiple errors encountered",
                description="Encountered 2 errors during operation",
                context=context,
            )

            # Store entry
            self.registry.add(entry)

            # Verify
            retrieved = self.registry.query(category=FeedbackCategory.BUG)
            self.assertEqual(len(retrieved), 1)
            self.assertEqual(retrieved[0].trigger_type, FeedbackTriggerType.ERROR_THRESHOLD)

            # Verify trigger was consumed
            stats = self.hook_manager.get_stats("agent-1")
            self.assertEqual(stats["error_count"], 0)  # Reset after trigger
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
