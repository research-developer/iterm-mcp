"""Tests for session tagging and locking.

These tests validate the SessionTagLockManager implementation against
the Gherkin specifications defined in issues #46-#52.
"""

import shutil
import tempfile
import unittest

import time

from core.agents import AgentRegistry
from core.tags import SessionTagLockManager, FocusCooldownManager


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


class TestFocusCooldown(unittest.TestCase):
    """Test focus cooldown to prevent rapid session switching."""

    def test_first_focus_always_allowed(self):
        """Scenario: First focus request is always allowed."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        allowed, blocking_agent, remaining = cooldown.check_cooldown("s1", "agent-a")
        self.assertTrue(allowed)
        self.assertIsNone(blocking_agent)
        self.assertEqual(remaining, 0.0)

    def test_focus_blocked_during_cooldown(self):
        """Scenario: Different session focus blocked during cooldown."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        cooldown.record_focus("s1", "agent-a")

        # Different session should be blocked
        allowed, blocking_agent, remaining = cooldown.check_cooldown("s2", "agent-b")
        self.assertFalse(allowed)
        self.assertEqual(blocking_agent, "agent-a")
        self.assertGreater(remaining, 0)

    def test_same_session_focus_is_idempotent(self):
        """Scenario: Same session can be focused again (idempotent)."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        cooldown.record_focus("s1", "agent-a")

        # Same session should be allowed
        allowed, blocking_agent, remaining = cooldown.check_cooldown("s1", "agent-b")
        self.assertTrue(allowed)

    def test_same_agent_can_focus_different_session(self):
        """Scenario: Same agent can focus different session."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        cooldown.record_focus("s1", "agent-a")

        # Same agent focusing different session should be allowed
        allowed, blocking_agent, remaining = cooldown.check_cooldown("s2", "agent-a")
        self.assertTrue(allowed)

    def test_focus_allowed_after_cooldown_expires(self):
        """Scenario: Focus allowed after cooldown period expires."""
        cooldown = FocusCooldownManager(cooldown_seconds=0.1)  # Short cooldown
        cooldown.record_focus("s1", "agent-a")

        # Wait for cooldown to expire
        time.sleep(0.15)

        allowed, blocking_agent, remaining = cooldown.check_cooldown("s2", "agent-b")
        self.assertTrue(allowed)
        self.assertEqual(remaining, 0.0)

    def test_reset_clears_cooldown(self):
        """Scenario: Reset clears the cooldown state."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        cooldown.record_focus("s1", "agent-a")

        # Should be blocked
        allowed, _, _ = cooldown.check_cooldown("s2", "agent-b")
        self.assertFalse(allowed)

        # Reset
        cooldown.reset()

        # Should now be allowed
        allowed, _, _ = cooldown.check_cooldown("s2", "agent-b")
        self.assertTrue(allowed)

    def test_get_status_shows_cooldown_info(self):
        """Scenario: get_status returns current cooldown state."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)

        # Before any focus
        status = cooldown.get_status()
        self.assertFalse(status["in_cooldown"])
        self.assertIsNone(status["last_session"])
        self.assertIsNone(status["last_agent"])

        # After focus
        cooldown.record_focus("s1", "agent-a")
        status = cooldown.get_status()
        self.assertTrue(status["in_cooldown"])
        self.assertEqual(status["last_session"], "s1")
        self.assertEqual(status["last_agent"], "agent-a")
        self.assertGreater(status["remaining_seconds"], 0)

    def test_cooldown_seconds_configurable(self):
        """Scenario: Cooldown period is configurable."""
        cooldown = FocusCooldownManager(cooldown_seconds=5.0)
        self.assertEqual(cooldown.cooldown_seconds, 5.0)

        cooldown.cooldown_seconds = 10.0
        self.assertEqual(cooldown.cooldown_seconds, 10.0)

        # Negative values should be clamped to 0
        cooldown.cooldown_seconds = -1.0
        self.assertEqual(cooldown.cooldown_seconds, 0.0)

    def test_none_agent_still_triggers_cooldown(self):
        """Scenario: Focus without agent still triggers cooldown."""
        cooldown = FocusCooldownManager(cooldown_seconds=2.0)
        cooldown.record_focus("s1", None)

        # Different session by different agent should be blocked
        allowed, blocking_agent, remaining = cooldown.check_cooldown("s2", "agent-b")
        self.assertFalse(allowed)
        self.assertIsNone(blocking_agent)  # No blocking agent name
        self.assertGreater(remaining, 0)


class TestTagFiltering(unittest.TestCase):
    """Tests for filtering sessions by tags (Issue #52).

    Based on Gherkin specs from issue #52.
    """

    def setUp(self):
        self.manager = SessionTagLockManager()
        # Set up test sessions with various tags
        self.manager.set_tags("s1", ["ipython", "daemon"])
        self.manager.set_tags("s2", ["ssh", "production"])
        self.manager.set_tags("s3", ["ipython", "ssh"])
        self.manager.set_tags("s4", ["daemon"])

    def test_filter_by_single_tag(self):
        """Scenario: Filter sessions by a single tag."""
        sessions = self.manager.sessions_with_tag("ipython")
        self.assertEqual(set(sessions), {"s1", "s3"})

    def test_filter_by_any_tags(self):
        """Scenario: Filter sessions matching ANY of multiple tags (OR)."""
        sessions = self.manager.sessions_with_tags(["ipython", "ssh"], match_all=False)
        self.assertEqual(set(sessions), {"s1", "s2", "s3"})

    def test_filter_by_all_tags(self):
        """Scenario: Filter sessions matching ALL of multiple tags (AND)."""
        sessions = self.manager.sessions_with_tags(["ipython", "ssh"], match_all=True)
        self.assertEqual(sessions, ["s3"])

    def test_filter_returns_empty_for_nonexistent_tag(self):
        """Scenario: Filter returns empty list for non-existent tag."""
        sessions = self.manager.sessions_with_tag("nonexistent")
        self.assertEqual(sessions, [])

    def test_has_tag_check(self):
        """Scenario: Check if session has a specific tag."""
        self.assertTrue(self.manager.has_tag("s1", "ipython"))
        self.assertFalse(self.manager.has_tag("s1", "ssh"))

    def test_has_any_tags_check(self):
        """Scenario: Check if session has any of specified tags."""
        self.assertTrue(self.manager.has_any_tags("s1", ["ipython", "ssh"]))
        self.assertFalse(self.manager.has_any_tags("s4", ["ipython", "ssh"]))

    def test_has_all_tags_check(self):
        """Scenario: Check if session has all specified tags."""
        self.assertTrue(self.manager.has_all_tags("s3", ["ipython", "ssh"]))
        self.assertFalse(self.manager.has_all_tags("s1", ["ipython", "ssh"]))


class TestLockFiltering(unittest.TestCase):
    """Tests for filtering sessions by lock status (Issue #52)."""

    def setUp(self):
        self.manager = SessionTagLockManager()
        # Set up test sessions with various lock states
        self.manager.lock_session("s1", "agent-a")
        self.manager.lock_session("s2", "agent-a")
        self.manager.lock_session("s3", "agent-b")
        # s4 is unlocked

    def test_get_locks_by_agent(self):
        """Scenario: Get all locks held by a specific agent."""
        locks = self.manager.get_locks_by_agent("agent-a")
        self.assertEqual(set(locks), {"s1", "s2"})

    def test_get_all_locks(self):
        """Scenario: Get all locks as dict."""
        locks = self.manager.get_all_locks()
        self.assertEqual(locks, {
            "s1": "agent-a",
            "s2": "agent-a",
            "s3": "agent-b"
        })

    def test_get_lock_info(self):
        """Scenario: Get detailed lock info."""
        lock_info = self.manager.get_lock_info("s1")
        self.assertIsNotNone(lock_info)
        self.assertEqual(lock_info.owner, "agent-a")
        self.assertIsNotNone(lock_info.locked_at)

    def test_get_lock_info_returns_none_for_unlocked(self):
        """Scenario: get_lock_info returns None for unlocked session."""
        lock_info = self.manager.get_lock_info("s4")
        self.assertIsNone(lock_info)

    def test_locked_at_timestamp(self):
        """Scenario: Lock timestamp is recorded."""
        locked_at = self.manager.get_locked_at("s1")
        self.assertIsNotNone(locked_at)

    def test_locked_at_returns_none_for_unlocked(self):
        """Scenario: get_locked_at returns None for unlocked session."""
        locked_at = self.manager.get_locked_at("s4")
        self.assertIsNone(locked_at)


class TestAccessRequests(unittest.TestCase):
    """Tests for pending access request tracking (Issue #52)."""

    def setUp(self):
        self.manager = SessionTagLockManager()
        self.manager.lock_session("s1", "agent-a")

    def test_add_access_request(self):
        """Scenario: Add pending access request."""
        added = self.manager.add_access_request("s1", "agent-b")
        self.assertTrue(added)
        self.assertIn("agent-b", self.manager.get_pending_requests("s1"))

    def test_add_access_request_to_own_lock_fails(self):
        """Scenario: Owner cannot request access to own lock."""
        added = self.manager.add_access_request("s1", "agent-a")
        self.assertFalse(added)

    def test_add_access_request_to_unlocked_fails(self):
        """Scenario: Cannot request access to unlocked session."""
        added = self.manager.add_access_request("s2", "agent-b")
        self.assertFalse(added)

    def test_remove_access_request(self):
        """Scenario: Remove pending access request."""
        self.manager.add_access_request("s1", "agent-b")
        removed = self.manager.remove_access_request("s1", "agent-b")
        self.assertTrue(removed)
        self.assertNotIn("agent-b", self.manager.get_pending_requests("s1"))

    def test_get_pending_request_count(self):
        """Scenario: Get count of pending requests."""
        self.manager.add_access_request("s1", "agent-b")
        self.manager.add_access_request("s1", "agent-c")
        count = self.manager.get_pending_request_count("s1")
        self.assertEqual(count, 2)

    def test_pending_requests_sorted(self):
        """Scenario: Pending requests are returned sorted."""
        self.manager.add_access_request("s1", "charlie")
        self.manager.add_access_request("s1", "alice")
        self.manager.add_access_request("s1", "bob")
        requests = self.manager.get_pending_requests("s1")
        self.assertEqual(requests, ["alice", "bob", "charlie"])

    def test_describe_includes_pending_requests(self):
        """Scenario: describe() includes pending access request count."""
        self.manager.add_access_request("s1", "agent-b")
        self.manager.add_access_request("s1", "agent-c")
        info = self.manager.describe("s1")
        self.assertEqual(info["pending_access_requests"], 2)


class TestDescribeSession(unittest.TestCase):
    """Tests for describe() method including all Issue #52 fields."""

    def setUp(self):
        self.manager = SessionTagLockManager()

    def test_describe_unlocked_session(self):
        """Scenario: describe() for unlocked session."""
        self.manager.set_tags("s1", ["test"])
        info = self.manager.describe("s1")
        self.assertEqual(info["tags"], ["test"])
        self.assertFalse(info["locked"])
        self.assertIsNone(info["locked_by"])
        self.assertIsNone(info["locked_at"])
        self.assertEqual(info["pending_access_requests"], 0)

    def test_describe_locked_session(self):
        """Scenario: describe() for locked session with full info."""
        self.manager.set_tags("s1", ["critical", "production"])
        self.manager.lock_session("s1", "agent-a")
        self.manager.add_access_request("s1", "agent-b")

        info = self.manager.describe("s1")
        self.assertEqual(info["tags"], ["critical", "production"])
        self.assertTrue(info["locked"])
        self.assertEqual(info["locked_by"], "agent-a")
        self.assertIsNotNone(info["locked_at"])
        self.assertEqual(info["pending_access_requests"], 1)

    def test_describe_nonexistent_session(self):
        """Scenario: describe() for session with no tags or locks."""
        info = self.manager.describe("nonexistent")
        self.assertEqual(info["tags"], [])
        self.assertFalse(info["locked"])
        self.assertIsNone(info["locked_by"])
        self.assertIsNone(info["locked_at"])
        self.assertEqual(info["pending_access_requests"], 0)


if __name__ == "__main__":
    unittest.main()
