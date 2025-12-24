"""Tests for session tagging and locking."""

import os
import shutil
import tempfile
import unittest

from core.agents import AgentRegistry
from core.tags import SessionTagLockManager


class TestSessionTagging(unittest.TestCase):
    """Validate tag CRUD operations."""

    def test_add_and_remove_tags(self):
        manager = SessionTagLockManager()

        tags = manager.set_tags("s1", ["ipython", "daemon"])
        self.assertEqual(tags, ["daemon", "ipython"])

        updated = manager.set_tags("s1", ["ssh"], append=True)
        self.assertEqual(updated, ["daemon", "ipython", "ssh"])

        remaining = manager.remove_tags("s1", ["daemon"])
        self.assertEqual(remaining, ["ipython", "ssh"])

        cleared = manager.set_tags("s1", [], append=False)
        self.assertEqual(cleared, [])


class TestSessionLocking(unittest.TestCase):
    """Validate lock acquisition and enforcement."""

    def test_lock_enforcement(self):
        manager = SessionTagLockManager()
        self.assertTrue(manager.lock_session("s1", "agent-a"))
        self.assertTrue(manager.is_locked("s1"))
        self.assertEqual(manager.lock_owner("s1"), "agent-a")

        allowed, owner = manager.check_permission("s1", "agent-a")
        self.assertTrue(allowed)
        self.assertEqual(owner, "agent-a")

        allowed_other, owner_other = manager.check_permission("s1", "agent-b")
        self.assertFalse(allowed_other)
        self.assertEqual(owner_other, "agent-a")

        self.assertFalse(manager.unlock_session("s1", "agent-b"))
        self.assertTrue(manager.unlock_session("s1", "agent-a"))
        self.assertFalse(manager.is_locked("s1"))


class TestLockCleanup(unittest.TestCase):
    """Ensure locks are released when agents are removed."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_release_on_agent_removal(self):
        manager = SessionTagLockManager()
        registry = AgentRegistry(data_dir=self.temp_dir, lock_manager=manager)
        registry.register_agent("agent-x", "session-1")

        self.assertTrue(manager.lock_session("session-1", "agent-x"))
        self.assertTrue(manager.is_locked("session-1"))

        registry.remove_agent("agent-x")
        self.assertFalse(manager.is_locked("session-1"))


if __name__ == "__main__":
    unittest.main()
