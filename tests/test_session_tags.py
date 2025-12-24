"""Tests for session tagging and locking.

These tests validate the SessionTagLockManager implementation against
the Gherkin specifications defined in issues #46-#52.
"""

import shutil
import tempfile
import unittest

from core.agents import AgentRegistry
from core.tags import SessionTagLockManager


class TestSessionTagging(unittest.TestCase):
    """Validate tag create/read/update/delete operations on sessions.

    Based on Gherkin specs from issue #46 and #47.
    """

    def setUp(self):
        self.manager = SessionTagLockManager()

    def test_session_has_empty_tags_by_default(self):
        """Scenario: Session has empty tags by default."""
        tags = self.manager.get_tags("new-session")
        self.assertEqual(tags, [])

    def test_tags_are_stored_as_set_no_duplicates(self):
        """Scenario: Tags are stored as a set (no duplicates)."""
        self.manager.set_tags("s1", ["ipython"])
        self.manager.set_tags("s1", ["ipython"])  # Add again
        tags = self.manager.get_tags("s1")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags, ["ipython"])

    def test_multiple_tags_can_be_stored(self):
        """Scenario: Multiple tags can be stored."""
        self.manager.set_tags("s1", ["ssh", "production", "critical"])
        tags = self.manager.get_tags("s1")
        self.assertEqual(len(tags), 3)
        self.assertIn("ssh", tags)
        self.assertIn("production", tags)
        self.assertIn("critical", tags)

    def test_add_and_remove_tags(self):
        """Scenario: Full CRUD cycle for tags."""
        # Create
        tags = self.manager.set_tags("s1", ["ipython", "daemon"])
        self.assertEqual(tags, ["daemon", "ipython"])

        # Update (append)
        updated = self.manager.set_tags("s1", ["ssh"], append=True)
        self.assertEqual(updated, ["daemon", "ipython", "ssh"])

        # Delete specific
        remaining = self.manager.remove_tags("s1", ["daemon"])
        self.assertEqual(remaining, ["ipython", "ssh"])

        # Clear all
        cleared = self.manager.set_tags("s1", [], append=False)
        self.assertEqual(cleared, [])

    def test_replace_tags_with_append_false(self):
        """Scenario: Replace all tags when append=False."""
        self.manager.set_tags("s1", ["old1", "old2"])
        new_tags = self.manager.set_tags("s1", ["new1", "new2"], append=False)
        self.assertEqual(new_tags, ["new1", "new2"])
        self.assertNotIn("old1", new_tags)

    def test_remove_nonexistent_tag_is_idempotent(self):
        """Scenario: Removing non-existent tag is idempotent."""
        self.manager.set_tags("s1", ["existing"])
        remaining = self.manager.remove_tags("s1", ["non-existent"])
        self.assertEqual(remaining, ["existing"])

    def test_whitespace_tags_are_normalized(self):
        """Tags with whitespace are trimmed, empty strings ignored."""
        tags = self.manager.set_tags("s1", ["  ssh  ", "  ", "daemon", ""])
        self.assertEqual(tags, ["daemon", "ssh"])

    def test_describe_returns_combined_info(self):
        """Scenario: describe() returns both tags and lock info."""
        self.manager.set_tags("s1", ["prod", "critical"])
        self.manager.lock_session("s1", "agent-a")

        info = self.manager.describe("s1")
        self.assertEqual(info["tags"], ["critical", "prod"])
        self.assertEqual(info["locked_by"], "agent-a")


class TestSessionLocking(unittest.TestCase):
    """Validate session lock acquisition, enforcement, and release.

    Based on Gherkin specs from issue #48.
    """

    def setUp(self):
        self.manager = SessionTagLockManager()

    def test_agent_can_lock_session(self):
        """Scenario: Agent can lock a session."""
        acquired, owner = self.manager.lock_session("s1", "agent-a")
        self.assertTrue(acquired)
        self.assertEqual(owner, "agent-a")
        self.assertTrue(self.manager.is_locked("s1"))
        self.assertEqual(self.manager.lock_owner("s1"), "agent-a")

    def test_lock_is_idempotent_for_owner(self):
        """Scenario: Session can only have one lock (idempotent for owner)."""
        self.manager.lock_session("s1", "agent-a")
        acquired, owner = self.manager.lock_session("s1", "agent-a")
        self.assertTrue(acquired)  # Should succeed (idempotent)
        self.assertEqual(owner, "agent-a")

    def test_cannot_lock_already_locked_session(self):
        """Scenario: Different agent cannot lock already-locked session."""
        self.manager.lock_session("s1", "agent-a")
        acquired, owner = self.manager.lock_session("s1", "agent-b")
        self.assertFalse(acquired)
        self.assertEqual(owner, "agent-a")  # Original owner

    def test_lock_owner_can_write(self):
        """Scenario: Lock owner can write to their locked session."""
        self.manager.lock_session("s1", "agent-a")
        allowed, owner = self.manager.check_permission("s1", "agent-a")
        self.assertTrue(allowed)
        self.assertEqual(owner, "agent-a")

    def test_non_owner_blocked_from_writing(self):
        """Scenario: Non-owner is blocked from writing."""
        self.manager.lock_session("s1", "agent-a")
        allowed, owner = self.manager.check_permission("s1", "agent-b")
        self.assertFalse(allowed)
        self.assertEqual(owner, "agent-a")

    def test_unlocked_session_allows_any_write(self):
        """Scenario: Unlocked session allows anyone to write."""
        allowed, owner = self.manager.check_permission("s1", "agent-b")
        self.assertTrue(allowed)
        self.assertIsNone(owner)

    def test_owner_can_unlock(self):
        """Scenario: Agent can unlock its own session."""
        self.manager.lock_session("s1", "agent-a")
        success = self.manager.unlock_session("s1", "agent-a")
        self.assertTrue(success)
        self.assertFalse(self.manager.is_locked("s1"))

    def test_non_owner_cannot_unlock(self):
        """Scenario: Agent cannot unlock another agent's session."""
        self.manager.lock_session("s1", "agent-a")
        success = self.manager.unlock_session("s1", "agent-b")
        self.assertFalse(success)
        self.assertTrue(self.manager.is_locked("s1"))  # Still locked

    def test_force_unlock_without_agent(self):
        """Scenario: Force unlock (admin operation) with agent=None."""
        self.manager.lock_session("s1", "agent-a")
        success = self.manager.unlock_session("s1", None)
        self.assertTrue(success)
        self.assertFalse(self.manager.is_locked("s1"))

    def test_unlock_already_unlocked_is_idempotent(self):
        """Scenario: Unlocking an unlocked session returns True."""
        success = self.manager.unlock_session("s1", "agent-a")
        self.assertTrue(success)


class TestLockCleanup(unittest.TestCase):
    """Ensure locks are released when agents are removed.

    Based on Gherkin specs from issue #50.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_release_on_agent_removal(self):
        """Scenario: Locks released on graceful agent removal."""
        manager = SessionTagLockManager()
        registry = AgentRegistry(data_dir=self.temp_dir, lock_manager=manager)
        registry.register_agent("agent-x", "session-1")

        acquired, _ = manager.lock_session("session-1", "agent-x")
        self.assertTrue(acquired)
        self.assertTrue(manager.is_locked("session-1"))

        registry.remove_agent("agent-x")
        self.assertFalse(manager.is_locked("session-1"))

    def test_release_multiple_locks_on_agent_removal(self):
        """Scenario: All locks by agent are released on removal."""
        manager = SessionTagLockManager()
        registry = AgentRegistry(data_dir=self.temp_dir, lock_manager=manager)
        registry.register_agent("agent-x", "session-1")

        # Lock multiple sessions
        manager.lock_session("session-1", "agent-x")
        manager.lock_session("session-2", "agent-x")
        manager.lock_session("session-3", "agent-x")

        self.assertTrue(manager.is_locked("session-1"))
        self.assertTrue(manager.is_locked("session-2"))
        self.assertTrue(manager.is_locked("session-3"))

        registry.remove_agent("agent-x")

        self.assertFalse(manager.is_locked("session-1"))
        self.assertFalse(manager.is_locked("session-2"))
        self.assertFalse(manager.is_locked("session-3"))

    def test_only_terminated_agent_locks_released(self):
        """Scenario: Only terminated agent's locks are released."""
        manager = SessionTagLockManager()
        registry = AgentRegistry(data_dir=self.temp_dir, lock_manager=manager)
        registry.register_agent("agent-a", "session-1")
        registry.register_agent("agent-b", "session-2")

        manager.lock_session("session-1", "agent-a")
        manager.lock_session("session-2", "agent-b")

        registry.remove_agent("agent-a")

        self.assertFalse(manager.is_locked("session-1"))  # Released
        self.assertTrue(manager.is_locked("session-2"))   # Still locked


class TestReleaseByAgent(unittest.TestCase):
    """Test release_locks_by_agent directly."""

    def test_release_locks_by_agent(self):
        """Direct test of release_locks_by_agent method."""
        manager = SessionTagLockManager()

        manager.lock_session("s1", "agent-a")
        manager.lock_session("s2", "agent-a")
        manager.lock_session("s3", "agent-b")

        manager.release_locks_by_agent("agent-a")

        self.assertFalse(manager.is_locked("s1"))
        self.assertFalse(manager.is_locked("s2"))
        self.assertTrue(manager.is_locked("s3"))  # Different agent


class TestPermissionChecks(unittest.TestCase):
    """Test permission checking edge cases."""

    def setUp(self):
        self.manager = SessionTagLockManager()

    def test_none_requester_blocked_on_locked_session(self):
        """Unknown/None requester should be blocked on locked session."""
        self.manager.lock_session("s1", "agent-a")
        allowed, owner = self.manager.check_permission("s1", None)
        self.assertFalse(allowed)
        self.assertEqual(owner, "agent-a")

    def test_none_requester_allowed_on_unlocked_session(self):
        """Unknown/None requester should be allowed on unlocked session."""
        allowed, owner = self.manager.check_permission("s1", None)
        self.assertTrue(allowed)
        self.assertIsNone(owner)


if __name__ == "__main__":
    unittest.main()
