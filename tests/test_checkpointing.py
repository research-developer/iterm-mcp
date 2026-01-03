"""Tests for checkpointing functionality.

Tests cover:
- FileCheckpointer save/load/list/delete operations
- SQLiteCheckpointer save/load/list/delete operations
- CheckpointManager functionality
- AgentRegistry save_state/load_state methods
- Session state serialization patterns
"""

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.checkpointing import (
    AgentState,
    Checkpoint,
    CheckpointManager,
    Checkpointer,
    FileCheckpointer,
    RegistryState,
    SessionState,
    SQLiteCheckpointer,
    TeamState,
)
from core.agents import Agent, AgentRegistry, Team


class TestSessionState(unittest.TestCase):
    """Tests for SessionState model."""

    def test_session_state_creation(self):
        """Test creating a SessionState with required fields."""
        state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )

        self.assertEqual(state.session_id, "session-123")
        self.assertEqual(state.persistent_id, "persist-456")
        self.assertEqual(state.name, "test-session")
        self.assertEqual(state.max_lines, 50)  # Default
        self.assertFalse(state.is_monitoring)  # Default
        self.assertIsNotNone(state.created_at)

    def test_session_state_with_optional_fields(self):
        """Test SessionState with optional fields."""
        state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session",
            max_lines=100,
            is_monitoring=True,
            last_command="echo hello",
            last_output="hello",
            metadata={"key": "value"}
        )

        self.assertEqual(state.max_lines, 100)
        self.assertTrue(state.is_monitoring)
        self.assertEqual(state.last_command, "echo hello")
        self.assertEqual(state.last_output, "hello")
        self.assertEqual(state.metadata, {"key": "value"})

    def test_session_state_serialization(self):
        """Test that SessionState can be serialized to JSON."""
        state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )

        # Should not raise
        data = state.model_dump(mode='json')
        self.assertIsInstance(data, dict)
        self.assertEqual(data["session_id"], "session-123")


class TestAgentState(unittest.TestCase):
    """Tests for AgentState model."""

    def test_agent_state_creation(self):
        """Test creating an AgentState."""
        state = AgentState(
            name="agent-1",
            session_id="session-123"
        )

        self.assertEqual(state.name, "agent-1")
        self.assertEqual(state.session_id, "session-123")
        self.assertEqual(state.teams, [])
        self.assertIsNotNone(state.created_at)

    def test_agent_state_with_teams(self):
        """Test AgentState with team memberships."""
        state = AgentState(
            name="agent-1",
            session_id="session-123",
            teams=["team-a", "team-b"],
            metadata={"role": "worker"}
        )

        self.assertEqual(state.teams, ["team-a", "team-b"])
        self.assertEqual(state.metadata, {"role": "worker"})


class TestTeamState(unittest.TestCase):
    """Tests for TeamState model."""

    def test_team_state_creation(self):
        """Test creating a TeamState."""
        state = TeamState(name="team-1")

        self.assertEqual(state.name, "team-1")
        self.assertEqual(state.description, "")
        self.assertIsNone(state.parent_team)

    def test_team_state_with_parent(self):
        """Test TeamState with parent team."""
        state = TeamState(
            name="sub-team",
            description="A sub team",
            parent_team="parent-team"
        )

        self.assertEqual(state.parent_team, "parent-team")


class TestCheckpoint(unittest.TestCase):
    """Tests for Checkpoint model."""

    def test_checkpoint_creation(self):
        """Test creating a Checkpoint."""
        checkpoint = Checkpoint()

        self.assertIsNotNone(checkpoint.checkpoint_id)
        self.assertIsNotNone(checkpoint.created_at)
        self.assertEqual(checkpoint.version, "1.0")
        self.assertEqual(checkpoint.trigger, "manual")
        self.assertEqual(checkpoint.sessions, {})
        self.assertIsNone(checkpoint.registry)

    def test_checkpoint_with_sessions(self):
        """Test Checkpoint with session states."""
        session_state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )

        checkpoint = Checkpoint(
            sessions={"session-123": session_state},
            trigger="auto"
        )

        self.assertIn("session-123", checkpoint.sessions)
        self.assertEqual(checkpoint.trigger, "auto")

    def test_checkpoint_with_registry(self):
        """Test Checkpoint with registry state."""
        registry = RegistryState(
            agents={"agent-1": AgentState(name="agent-1", session_id="s1")},
            teams={"team-1": TeamState(name="team-1")},
            active_session="s1"
        )

        checkpoint = Checkpoint(registry=registry)

        self.assertIsNotNone(checkpoint.registry)
        self.assertIn("agent-1", checkpoint.registry.agents)


class TestFileCheckpointer(unittest.TestCase):
    """Tests for FileCheckpointer."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpointer = FileCheckpointer(checkpoint_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_checkpoint(self):
        """Test saving and loading a checkpoint."""
        session_state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )
        checkpoint = Checkpoint(
            sessions={"session-123": session_state},
            trigger="test"
        )

        async def run_test():
            checkpoint_id = await self.checkpointer.save(checkpoint)
            self.assertEqual(checkpoint_id, checkpoint.checkpoint_id)

            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.checkpoint_id, checkpoint.checkpoint_id)
            self.assertIn("session-123", loaded.sessions)

        asyncio.run(run_test())

    def test_load_nonexistent_checkpoint(self):
        """Test loading a checkpoint that doesn't exist."""
        async def run_test():
            loaded = await self.checkpointer.load("nonexistent-id")
            self.assertIsNone(loaded)

        asyncio.run(run_test())

    def test_list_checkpoints(self):
        """Test listing checkpoints."""
        async def run_test():
            # Create multiple checkpoints
            for i in range(3):
                checkpoint = Checkpoint(
                    sessions={f"session-{i}": SessionState(
                        session_id=f"session-{i}",
                        persistent_id=f"persist-{i}",
                        name=f"test-{i}"
                    )},
                    trigger=f"test-{i}"
                )
                await self.checkpointer.save(checkpoint)

            # List all checkpoints
            checkpoints = await self.checkpointer.list_checkpoints()
            self.assertEqual(len(checkpoints), 3)

            # List with limit
            limited = await self.checkpointer.list_checkpoints(limit=2)
            self.assertEqual(len(limited), 2)

        asyncio.run(run_test())

    def test_list_checkpoints_by_session(self):
        """Test listing checkpoints filtered by session ID."""
        async def run_test():
            # Create checkpoints with different sessions
            cp1 = Checkpoint(
                sessions={"session-a": SessionState(
                    session_id="session-a",
                    persistent_id="persist-a",
                    name="session-a"
                )}
            )
            cp2 = Checkpoint(
                sessions={"session-b": SessionState(
                    session_id="session-b",
                    persistent_id="persist-b",
                    name="session-b"
                )}
            )

            await self.checkpointer.save(cp1)
            await self.checkpointer.save(cp2)

            # Filter by session
            filtered = await self.checkpointer.list_checkpoints(session_id="session-a")
            self.assertEqual(len(filtered), 1)
            self.assertIn("session-a", filtered[0]["session_ids"])

        asyncio.run(run_test())

    def test_delete_checkpoint(self):
        """Test deleting a checkpoint."""
        checkpoint = Checkpoint()

        async def run_test():
            checkpoint_id = await self.checkpointer.save(checkpoint)

            # Verify it exists
            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNotNone(loaded)

            # Delete it
            result = await self.checkpointer.delete(checkpoint_id)
            self.assertTrue(result)

            # Verify it's gone
            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNone(loaded)

        asyncio.run(run_test())

    def test_delete_nonexistent_checkpoint(self):
        """Test deleting a checkpoint that doesn't exist."""
        async def run_test():
            result = await self.checkpointer.delete("nonexistent-id")
            self.assertFalse(result)

        asyncio.run(run_test())

    def test_get_latest_checkpoint(self):
        """Test getting the latest checkpoint."""
        async def run_test():
            # Create multiple checkpoints
            checkpoints_created = []
            for i in range(3):
                checkpoint = Checkpoint(trigger=f"test-{i}")
                await self.checkpointer.save(checkpoint)
                checkpoints_created.append(checkpoint)
                await asyncio.sleep(0.01)  # Ensure different timestamps

            # Get latest
            latest = await self.checkpointer.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.checkpoint_id, checkpoints_created[-1].checkpoint_id)

        asyncio.run(run_test())

    def test_index_persistence(self):
        """Test that the index persists across checkpointer instances."""
        checkpoint = Checkpoint()

        async def run_test():
            # Save with first checkpointer
            checkpoint_id = await self.checkpointer.save(checkpoint)

            # Create new checkpointer with same directory
            new_checkpointer = FileCheckpointer(checkpoint_dir=self.temp_dir)

            # Verify index was loaded
            checkpoints = await new_checkpointer.list_checkpoints()
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual(checkpoints[0]["checkpoint_id"], checkpoint_id)

        asyncio.run(run_test())


class TestSQLiteCheckpointer(unittest.TestCase):
    """Tests for SQLiteCheckpointer."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_checkpoints.db")
        self.checkpointer = SQLiteCheckpointer(db_path=self.db_path)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_checkpoint(self):
        """Test saving and loading a checkpoint."""
        session_state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )
        checkpoint = Checkpoint(
            sessions={"session-123": session_state},
            trigger="test"
        )

        async def run_test():
            checkpoint_id = await self.checkpointer.save(checkpoint)
            self.assertEqual(checkpoint_id, checkpoint.checkpoint_id)

            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.checkpoint_id, checkpoint.checkpoint_id)
            self.assertIn("session-123", loaded.sessions)

        asyncio.run(run_test())

    def test_list_checkpoints(self):
        """Test listing checkpoints."""
        async def run_test():
            # Create multiple checkpoints
            for i in range(3):
                checkpoint = Checkpoint(
                    sessions={f"session-{i}": SessionState(
                        session_id=f"session-{i}",
                        persistent_id=f"persist-{i}",
                        name=f"test-{i}"
                    )},
                    trigger=f"test-{i}"
                )
                await self.checkpointer.save(checkpoint)

            # List all checkpoints
            checkpoints = await self.checkpointer.list_checkpoints()
            self.assertEqual(len(checkpoints), 3)

        asyncio.run(run_test())

    def test_list_checkpoints_by_session(self):
        """Test listing checkpoints filtered by session ID."""
        async def run_test():
            # Create checkpoints with different sessions
            cp1 = Checkpoint(
                sessions={"session-a": SessionState(
                    session_id="session-a",
                    persistent_id="persist-a",
                    name="session-a"
                )}
            )
            cp2 = Checkpoint(
                sessions={"session-b": SessionState(
                    session_id="session-b",
                    persistent_id="persist-b",
                    name="session-b"
                )}
            )

            await self.checkpointer.save(cp1)
            await self.checkpointer.save(cp2)

            # Filter by session
            filtered = await self.checkpointer.list_checkpoints(session_id="session-a")
            self.assertEqual(len(filtered), 1)

        asyncio.run(run_test())

    def test_delete_checkpoint(self):
        """Test deleting a checkpoint."""
        checkpoint = Checkpoint()

        async def run_test():
            checkpoint_id = await self.checkpointer.save(checkpoint)

            # Verify it exists
            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNotNone(loaded)

            # Delete it
            result = await self.checkpointer.delete(checkpoint_id)
            self.assertTrue(result)

            # Verify it's gone
            loaded = await self.checkpointer.load(checkpoint_id)
            self.assertIsNone(loaded)

        asyncio.run(run_test())

    def test_get_latest_checkpoint(self):
        """Test getting the latest checkpoint."""
        async def run_test():
            # Create multiple checkpoints
            checkpoints_created = []
            for i in range(3):
                checkpoint = Checkpoint(trigger=f"test-{i}")
                await self.checkpointer.save(checkpoint)
                checkpoints_created.append(checkpoint)
                await asyncio.sleep(0.01)  # Ensure different timestamps

            # Get latest
            latest = await self.checkpointer.get_latest()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.checkpoint_id, checkpoints_created[-1].checkpoint_id)

        asyncio.run(run_test())

    def test_cleanup_old_checkpoints(self):
        """Test cleaning up old checkpoints."""
        async def run_test():
            # Create many checkpoints
            for i in range(15):
                checkpoint = Checkpoint(trigger=f"test-{i}")
                await self.checkpointer.save(checkpoint)

            # Cleanup keeping only 5
            deleted = await self.checkpointer.cleanup_old_checkpoints(
                max_age_days=365,  # Won't delete by age
                max_count=5
            )

            self.assertEqual(deleted, 10)  # 15 - 5 = 10 deleted

            # Verify only 5 remain
            remaining = await self.checkpointer.list_checkpoints(limit=20)
            self.assertEqual(len(remaining), 5)

        asyncio.run(run_test())


class TestCheckpointManager(unittest.TestCase):
    """Tests for CheckpointManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpointer = FileCheckpointer(checkpoint_dir=self.temp_dir)
        self.manager = CheckpointManager(
            checkpointer=self.checkpointer,
            auto_checkpoint=True,
            checkpoint_interval=3
        )

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_checkpoint(self):
        """Test creating a checkpoint through the manager."""
        session_state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )

        async def run_test():
            checkpoint = await self.manager.create_checkpoint(
                sessions={"session-123": session_state},
                trigger="test"
            )

            self.assertIsNotNone(checkpoint)
            self.assertEqual(self.manager.last_checkpoint_id, checkpoint.checkpoint_id)

        asyncio.run(run_test())

    def test_restore_checkpoint(self):
        """Test restoring from a checkpoint."""
        session_state = SessionState(
            session_id="session-123",
            persistent_id="persist-456",
            name="test-session"
        )

        async def run_test():
            # Create a checkpoint
            checkpoint = await self.manager.create_checkpoint(
                sessions={"session-123": session_state}
            )

            # Restore by ID
            restored = await self.manager.restore_checkpoint(checkpoint.checkpoint_id)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.checkpoint_id, checkpoint.checkpoint_id)

            # Restore latest
            latest = await self.manager.restore_checkpoint()
            self.assertIsNotNone(latest)
            self.assertEqual(latest.checkpoint_id, checkpoint.checkpoint_id)

        asyncio.run(run_test())

    def test_auto_checkpoint_threshold(self):
        """Test auto-checkpoint threshold detection."""
        async def run_test():
            # With interval of 3, should return False until 3rd call
            self.assertFalse(await self.manager.should_auto_checkpoint())
            self.assertFalse(await self.manager.should_auto_checkpoint())
            self.assertTrue(await self.manager.should_auto_checkpoint())  # 3rd call

        asyncio.run(run_test())

    def test_auto_checkpoint_disabled(self):
        """Test that auto-checkpoint can be disabled."""
        manager = CheckpointManager(
            checkpointer=self.checkpointer,
            auto_checkpoint=False
        )

        async def run_test():
            for _ in range(10):
                self.assertFalse(await manager.should_auto_checkpoint())

        asyncio.run(run_test())

    def test_auto_checkpoint_resets_after_create(self):
        """Test that operation count resets after creating a checkpoint."""
        async def run_test():
            # Increment count
            await self.manager.should_auto_checkpoint()
            await self.manager.should_auto_checkpoint()

            # Create checkpoint (should reset count)
            await self.manager.create_checkpoint()

            # Should be back to 0, so first call returns False
            self.assertFalse(await self.manager.should_auto_checkpoint())

        asyncio.run(run_test())

    def test_list_checkpoints(self):
        """Test listing checkpoints through manager."""
        async def run_test():
            # Create some checkpoints
            for i in range(3):
                await self.manager.create_checkpoint(trigger=f"test-{i}")

            checkpoints = await self.manager.list_checkpoints()
            self.assertEqual(len(checkpoints), 3)

        asyncio.run(run_test())

    def test_delete_checkpoint(self):
        """Test deleting a checkpoint through manager."""
        async def run_test():
            checkpoint = await self.manager.create_checkpoint()

            result = await self.manager.delete_checkpoint(checkpoint.checkpoint_id)
            self.assertTrue(result)

            # Verify it's gone
            restored = await self.manager.restore_checkpoint(checkpoint.checkpoint_id)
            self.assertIsNone(restored)

        asyncio.run(run_test())


class TestAgentRegistryState(unittest.TestCase):
    """Tests for AgentRegistry save_state/load_state methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_state_empty_registry(self):
        """Test saving state of an empty registry."""
        state = self.registry.save_state()

        self.assertIn("agents", state)
        self.assertIn("teams", state)
        self.assertIn("created_at", state)
        self.assertEqual(state["agents"], {})
        self.assertEqual(state["teams"], {})

    def test_save_state_with_agents(self):
        """Test saving state with registered agents."""
        # Register an agent
        self.registry.register_agent(
            name="agent-1",
            session_id="session-123",
            teams=["team-1"],
            metadata={"role": "worker"}
        )

        state = self.registry.save_state()

        self.assertIn("agent-1", state["agents"])
        agent_state = state["agents"]["agent-1"]
        self.assertEqual(agent_state["name"], "agent-1")
        self.assertEqual(agent_state["session_id"], "session-123")
        self.assertEqual(agent_state["teams"], ["team-1"])

    def test_save_state_with_teams(self):
        """Test saving state with teams."""
        # Create a team
        self.registry.create_team(
            name="team-1",
            description="Test team"
        )

        state = self.registry.save_state()

        self.assertIn("team-1", state["teams"])
        team_state = state["teams"]["team-1"]
        self.assertEqual(team_state["name"], "team-1")
        self.assertEqual(team_state["description"], "Test team")

    def test_save_state_with_message_history(self):
        """Test saving state with message history."""
        # Add some message history using the internal deque
        from core.agents import MessageRecord
        import hashlib

        content_hash = hashlib.sha256("Hello".encode()).hexdigest()
        record = MessageRecord(
            content_hash=content_hash,
            recipients=["agent-1"]
        )
        self.registry._message_history.append(record)

        state = self.registry.save_state()

        self.assertEqual(len(state["message_history"]), 1)
        self.assertEqual(state["message_history"][0]["content_hash"], content_hash)

    def test_load_state_empty(self):
        """Test loading an empty state."""
        state = {
            "agents": {},
            "teams": {},
            "active_session": None,
            "message_history": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self.registry.load_state(state)

        self.assertEqual(len(self.registry._agents), 0)
        self.assertEqual(len(self.registry._teams), 0)

    def test_load_state_with_agents(self):
        """Test loading state with agents."""
        state = {
            "agents": {
                "agent-1": {
                    "name": "agent-1",
                    "session_id": "session-123",
                    "teams": ["team-1"],
                    "metadata": {"role": "worker"},
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            "teams": {},
            "active_session": "session-123",
            "message_history": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self.registry.load_state(state)

        self.assertIn("agent-1", self.registry._agents)
        agent = self.registry._agents["agent-1"]
        self.assertEqual(agent.name, "agent-1")
        self.assertEqual(agent.session_id, "session-123")

    def test_load_state_with_teams(self):
        """Test loading state with teams."""
        state = {
            "agents": {},
            "teams": {
                "team-1": {
                    "name": "team-1",
                    "description": "Test team",
                    "parent_team": None,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            "active_session": None,
            "message_history": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self.registry.load_state(state)

        self.assertIn("team-1", self.registry._teams)
        team = self.registry._teams["team-1"]
        self.assertEqual(team.name, "team-1")
        self.assertEqual(team.description, "Test team")

    def test_load_state_clears_existing(self):
        """Test that loading state clears existing data."""
        # Add some data first
        self.registry.register_agent(
            name="old-agent",
            session_id="old-session"
        )
        self.registry.create_team(name="old-team")

        # Load new state
        state = {
            "agents": {
                "new-agent": {
                    "name": "new-agent",
                    "session_id": "new-session",
                    "teams": [],
                    "metadata": {},
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            "teams": {},
            "active_session": None,
            "message_history": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        self.registry.load_state(state)

        # Old data should be gone
        self.assertNotIn("old-agent", self.registry._agents)
        self.assertNotIn("old-team", self.registry._teams)

        # New data should be present
        self.assertIn("new-agent", self.registry._agents)

    def test_state_roundtrip(self):
        """Test saving and loading state preserves data."""
        # Set up initial state
        self.registry.register_agent(
            name="agent-1",
            session_id="session-123",
            teams=["team-1"],
            metadata={"role": "worker"}
        )
        self.registry.create_team(
            name="team-1",
            description="Test team"
        )

        # Save state
        saved_state = self.registry.save_state()

        # Create new registry and load state (use separate dir to avoid conflicts)
        new_temp_dir = tempfile.mkdtemp()
        try:
            new_registry = AgentRegistry(data_dir=new_temp_dir)
            new_registry.load_state(saved_state)

            # Verify data matches
            self.assertIn("agent-1", new_registry._agents)
            self.assertIn("team-1", new_registry._teams)
        finally:
            shutil.rmtree(new_temp_dir, ignore_errors=True)

    def test_get_state_summary(self):
        """Test getting a state summary."""
        self.registry.register_agent(
            name="agent-1",
            session_id="session-123"
        )
        self.registry.create_team(name="team-1")

        summary = self.registry.get_state_summary()

        self.assertEqual(summary["agent_count"], 1)
        self.assertEqual(summary["team_count"], 1)
        self.assertIn("agent-1", summary["agents"])
        self.assertIn("team-1", summary["teams"])


class TestCheckpointerProtocol(unittest.TestCase):
    """Tests for Checkpointer protocol compliance."""

    def test_file_checkpointer_is_checkpointer(self):
        """Test that FileCheckpointer implements Checkpointer protocol."""
        temp_dir = tempfile.mkdtemp()
        try:
            checkpointer = FileCheckpointer(checkpoint_dir=temp_dir)
            self.assertTrue(isinstance(checkpointer, Checkpointer))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sqlite_checkpointer_is_checkpointer(self):
        """Test that SQLiteCheckpointer implements Checkpointer protocol."""
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = os.path.join(temp_dir, "test.db")
            checkpointer = SQLiteCheckpointer(db_path=db_path)
            self.assertTrue(isinstance(checkpointer, Checkpointer))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestCheckpointWithRegistry(unittest.TestCase):
    """Integration tests for checkpointing with AgentRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = os.path.join(self.temp_dir, "checkpoints")
        self.registry_dir = os.path.join(self.temp_dir, "registry")

        os.makedirs(self.checkpoint_dir)
        os.makedirs(self.registry_dir)

        self.checkpointer = FileCheckpointer(checkpoint_dir=self.checkpoint_dir)
        self.manager = CheckpointManager(checkpointer=self.checkpointer)
        self.registry = AgentRegistry(data_dir=self.registry_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_checkpoint_with_registry_state(self):
        """Test creating a checkpoint with registry state."""
        # Set up registry
        self.registry.register_agent(
            name="agent-1",
            session_id="session-123"
        )
        self.registry.create_team(name="team-1")

        async def run_test():
            # Create registry state for checkpoint
            registry_state = RegistryState(
                agents={
                    name: AgentState(
                        name=agent.name,
                        session_id=agent.session_id,
                        teams=agent.teams,
                        metadata=agent.metadata
                    )
                    for name, agent in self.registry._agents.items()
                },
                teams={
                    name: TeamState(
                        name=team.name,
                        description=team.description,
                        parent_team=team.parent_team
                    )
                    for name, team in self.registry._teams.items()
                }
            )

            # Create checkpoint
            checkpoint = await self.manager.create_checkpoint(
                registry=registry_state,
                trigger="integration-test"
            )

            # Restore and verify
            restored = await self.manager.restore_checkpoint()
            self.assertIsNotNone(restored.registry)
            self.assertIn("agent-1", restored.registry.agents)
            self.assertIn("team-1", restored.registry.teams)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
