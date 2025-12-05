"""Tests for agent registry and parallel operations."""

import os
import shutil
import tempfile
import unittest

from core.agents import (
    Agent,
    Team,
    AgentRegistry,
    CascadingMessage,
)


class TestAgentModel(unittest.TestCase):
    """Test Agent Pydantic model."""

    def test_agent_creation(self):
        """Test creating an agent with required fields."""
        agent = Agent(name="test-agent", session_id="session-123")
        self.assertEqual(agent.name, "test-agent")
        self.assertEqual(agent.session_id, "session-123")
        self.assertEqual(agent.teams, [])
        self.assertEqual(agent.metadata, {})

    def test_agent_with_teams(self):
        """Test creating an agent with team membership."""
        agent = Agent(
            name="test-agent",
            session_id="session-123",
            teams=["frontend", "devops"]
        )
        self.assertTrue(agent.is_member_of("frontend"))
        self.assertTrue(agent.is_member_of("devops"))
        self.assertFalse(agent.is_member_of("backend"))

    def test_agent_with_metadata(self):
        """Test creating an agent with metadata."""
        agent = Agent(
            name="test-agent",
            session_id="session-123",
            metadata={"role": "code-reviewer", "priority": "high"}
        )
        self.assertEqual(agent.metadata["role"], "code-reviewer")


class TestTeamModel(unittest.TestCase):
    """Test Team Pydantic model."""

    def test_team_creation(self):
        """Test creating a team."""
        team = Team(name="engineering")
        self.assertEqual(team.name, "engineering")
        self.assertEqual(team.description, "")
        self.assertIsNone(team.parent_team)

    def test_team_with_parent(self):
        """Test creating a team with parent."""
        team = Team(
            name="frontend",
            description="Frontend engineers",
            parent_team="engineering"
        )
        self.assertEqual(team.parent_team, "engineering")


class TestAgentRegistry(unittest.TestCase):
    """Test AgentRegistry functionality."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_agent(self):
        """Test registering a new agent."""
        agent = self.registry.register_agent(
            name="agent-1",
            session_id="session-abc"
        )
        self.assertEqual(agent.name, "agent-1")
        self.assertEqual(agent.session_id, "session-abc")

        # Verify retrieval
        retrieved = self.registry.get_agent("agent-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, "session-abc")

    def test_register_agent_with_teams(self):
        """Test registering an agent with team membership."""
        self.registry.create_team("team-a")
        self.registry.create_team("team-b")

        agent = self.registry.register_agent(
            name="multi-team-agent",
            session_id="session-123",
            teams=["team-a", "team-b"]
        )
        self.assertIn("team-a", agent.teams)
        self.assertIn("team-b", agent.teams)

    def test_get_agent_by_session(self):
        """Test retrieving agent by session ID."""
        self.registry.register_agent("agent-x", "unique-session-id")
        agent = self.registry.get_agent_by_session("unique-session-id")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "agent-x")

    def test_remove_agent(self):
        """Test removing an agent."""
        self.registry.register_agent("temp-agent", "session-temp")
        self.assertTrue(self.registry.remove_agent("temp-agent"))
        self.assertIsNone(self.registry.get_agent("temp-agent"))

    def test_list_agents(self):
        """Test listing all agents."""
        self.registry.register_agent("agent-1", "s1")
        self.registry.register_agent("agent-2", "s2")
        self.registry.register_agent("agent-3", "s3")

        agents = self.registry.list_agents()
        self.assertEqual(len(agents), 3)
        names = [a.name for a in agents]
        self.assertIn("agent-1", names)
        self.assertIn("agent-2", names)
        self.assertIn("agent-3", names)

    def test_list_agents_by_team(self):
        """Test listing agents filtered by team."""
        self.registry.create_team("devops")
        self.registry.register_agent("agent-1", "s1", teams=["devops"])
        self.registry.register_agent("agent-2", "s2", teams=["devops"])
        self.registry.register_agent("agent-3", "s3", teams=["frontend"])

        devops_agents = self.registry.list_agents(team="devops")
        self.assertEqual(len(devops_agents), 2)
        names = [a.name for a in devops_agents]
        self.assertIn("agent-1", names)
        self.assertIn("agent-2", names)

    def test_assign_to_team(self):
        """Test assigning an agent to a team."""
        self.registry.create_team("new-team")
        self.registry.register_agent("agent-1", "s1")

        self.assertTrue(self.registry.assign_to_team("agent-1", "new-team"))
        agent = self.registry.get_agent("agent-1")
        self.assertIn("new-team", agent.teams)

    def test_remove_from_team(self):
        """Test removing an agent from a team."""
        self.registry.create_team("temp-team")
        self.registry.register_agent("agent-1", "s1", teams=["temp-team"])

        self.assertTrue(self.registry.remove_from_team("agent-1", "temp-team"))
        agent = self.registry.get_agent("agent-1")
        self.assertNotIn("temp-team", agent.teams)


class TestTeamManagement(unittest.TestCase):
    """Test team management in AgentRegistry."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_team(self):
        """Test creating a team."""
        team = self.registry.create_team("engineering", "Engineering department")
        self.assertEqual(team.name, "engineering")
        self.assertEqual(team.description, "Engineering department")

    def test_get_team(self):
        """Test retrieving a team."""
        self.registry.create_team("backend")
        team = self.registry.get_team("backend")
        self.assertIsNotNone(team)
        self.assertEqual(team.name, "backend")

    def test_remove_team(self):
        """Test removing a team and cleanup from agents."""
        self.registry.create_team("temp-team")
        self.registry.register_agent("agent-1", "s1", teams=["temp-team"])

        self.assertTrue(self.registry.remove_team("temp-team"))
        self.assertIsNone(self.registry.get_team("temp-team"))

        # Verify team removed from agent
        agent = self.registry.get_agent("agent-1")
        self.assertNotIn("temp-team", agent.teams)

    def test_list_teams(self):
        """Test listing all teams."""
        self.registry.create_team("team-a")
        self.registry.create_team("team-b")
        self.registry.create_team("team-c")

        teams = self.registry.list_teams()
        self.assertEqual(len(teams), 3)

    def test_team_hierarchy(self):
        """Test team parent-child hierarchy."""
        self.registry.create_team("company")
        self.registry.create_team("engineering", parent_team="company")
        self.registry.create_team("frontend", parent_team="engineering")

        hierarchy = self.registry.get_team_hierarchy("frontend")
        self.assertEqual(hierarchy, ["company", "engineering", "frontend"])

    def test_get_child_teams(self):
        """Test getting child teams."""
        self.registry.create_team("parent")
        self.registry.create_team("child-1", parent_team="parent")
        self.registry.create_team("child-2", parent_team="parent")
        self.registry.create_team("other")

        children = self.registry.get_child_teams("parent")
        self.assertEqual(len(children), 2)
        names = [t.name for t in children]
        self.assertIn("child-1", names)
        self.assertIn("child-2", names)


class TestMessageDeduplication(unittest.TestCase):
    """Test message deduplication functionality."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)
        self.registry.register_agent("agent-1", "s1")
        self.registry.register_agent("agent-2", "s2")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_message_sent(self):
        """Test recording a sent message."""
        self.registry.record_message_sent("Hello world", ["agent-1"])
        self.assertTrue(self.registry.was_message_sent("Hello world", "agent-1"))
        self.assertFalse(self.registry.was_message_sent("Hello world", "agent-2"))

    def test_filter_unsent_recipients(self):
        """Test filtering recipients who haven't received a message."""
        self.registry.record_message_sent("Test message", ["agent-1"])

        unsent = self.registry.filter_unsent_recipients(
            "Test message",
            ["agent-1", "agent-2"]
        )
        self.assertEqual(unsent, ["agent-2"])

    def test_different_messages_not_deduplicated(self):
        """Test that different messages are not considered duplicates."""
        self.registry.record_message_sent("Message A", ["agent-1"])
        self.assertFalse(self.registry.was_message_sent("Message B", "agent-1"))

    def test_message_history_limit(self):
        """Test that message history respects max limit."""
        small_registry = AgentRegistry(
            data_dir=self.temp_dir + "/small",
            max_message_history=3
        )
        small_registry.register_agent("agent-1", "s1")

        # Send more messages than the limit
        small_registry.record_message_sent("msg-1", ["agent-1"])
        small_registry.record_message_sent("msg-2", ["agent-1"])
        small_registry.record_message_sent("msg-3", ["agent-1"])
        small_registry.record_message_sent("msg-4", ["agent-1"])

        # First message should be evicted
        self.assertFalse(small_registry.was_message_sent("msg-1", "agent-1"))
        # Later messages should still be tracked
        self.assertTrue(small_registry.was_message_sent("msg-4", "agent-1"))


class TestCascadingMessages(unittest.TestCase):
    """Test cascading message resolution."""

    def setUp(self):
        """Create temporary directory and set up test agents/teams."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)

        # Create team hierarchy
        self.registry.create_team("all")
        self.registry.create_team("frontend", parent_team="all")
        self.registry.create_team("backend", parent_team="all")

        # Create agents in teams
        self.registry.register_agent("alice", "s1", teams=["frontend"])
        self.registry.register_agent("bob", "s2", teams=["frontend"])
        self.registry.register_agent("charlie", "s3", teams=["backend"])
        self.registry.register_agent("dave", "s4", teams=["backend"])

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_broadcast_only(self):
        """Test broadcast message to all agents."""
        cascade = CascadingMessage(broadcast="Hello everyone!")
        targets = self.registry.resolve_cascade_targets(cascade)

        self.assertEqual(len(targets), 1)
        self.assertIn("Hello everyone!", targets)
        self.assertEqual(len(targets["Hello everyone!"]), 4)

    def test_team_message(self):
        """Test team-specific message."""
        cascade = CascadingMessage(
            teams={"frontend": "Frontend task", "backend": "Backend task"}
        )
        targets = self.registry.resolve_cascade_targets(cascade)

        self.assertEqual(len(targets), 2)
        frontend_agents = targets.get("Frontend task", [])
        backend_agents = targets.get("Backend task", [])

        self.assertIn("alice", frontend_agents)
        self.assertIn("bob", frontend_agents)
        self.assertIn("charlie", backend_agents)
        self.assertIn("dave", backend_agents)

    def test_agent_specific_message(self):
        """Test agent-specific message override."""
        cascade = CascadingMessage(
            broadcast="General instruction",
            agents={"alice": "Special task for Alice"}
        )
        targets = self.registry.resolve_cascade_targets(cascade)

        # Alice should get her specific message, others get broadcast
        alice_msg = None
        general_recipients = []
        for msg, agents in targets.items():
            if "Alice" in msg:
                alice_msg = msg
                self.assertIn("alice", agents)
            else:
                general_recipients.extend(agents)

        self.assertIsNotNone(alice_msg)
        self.assertNotIn("alice", general_recipients)
        self.assertIn("bob", general_recipients)
        self.assertIn("charlie", general_recipients)

    def test_cascade_priority(self):
        """Test that more specific messages override less specific."""
        cascade = CascadingMessage(
            broadcast="Broadcast message",
            teams={"frontend": "Frontend message"},
            agents={"alice": "Alice's special message"}
        )
        targets = self.registry.resolve_cascade_targets(cascade)

        # alice gets agent-specific
        # bob gets team-specific (frontend)
        # charlie, dave get broadcast (backend, no team override)
        found_alice = False
        found_bob = False
        found_backend = False

        for msg, agents in targets.items():
            if "Alice's special" in msg:
                self.assertEqual(agents, ["alice"])
                found_alice = True
            elif "Frontend message" in msg:
                self.assertEqual(agents, ["bob"])
                found_bob = True
            elif "Broadcast message" in msg:
                self.assertIn("charlie", agents)
                self.assertIn("dave", agents)
                found_backend = True

        self.assertTrue(found_alice, "Alice should get special message")
        self.assertTrue(found_bob, "Bob should get frontend message")
        self.assertTrue(found_backend, "Charlie/Dave should get broadcast")

    def test_get_session_ids_for_agents(self):
        """Test converting agent names to session IDs."""
        session_ids = self.registry.get_session_ids_for_agents(
            ["alice", "charlie", "unknown"]
        )
        self.assertEqual(len(session_ids), 2)
        self.assertIn("s1", session_ids)  # alice
        self.assertIn("s3", session_ids)  # charlie


class TestActiveSession(unittest.TestCase):
    """Test active session management."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = AgentRegistry(data_dir=self.temp_dir)
        self.registry.register_agent("agent-1", "session-abc")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_active_session(self):
        """Test setting active session."""
        self.assertIsNone(self.registry.active_session)
        self.registry.active_session = "session-abc"
        self.assertEqual(self.registry.active_session, "session-abc")

    def test_get_active_agent(self):
        """Test getting agent for active session."""
        self.registry.active_session = "session-abc"
        agent = self.registry.get_active_agent()
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "agent-1")

    def test_get_active_agent_no_session(self):
        """Test getting active agent when no session set."""
        agent = self.registry.get_active_agent()
        self.assertIsNone(agent)


class TestPersistence(unittest.TestCase):
    """Test JSONL persistence."""

    def setUp(self):
        """Create temporary directory for registry data."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_agents_persist(self):
        """Test that agents are persisted to file."""
        # Create registry and add data
        registry1 = AgentRegistry(data_dir=self.temp_dir)
        registry1.register_agent("persistent-agent", "session-xyz", teams=["team-1"])
        registry1.create_team("team-1")

        # Create new registry instance (simulates restart)
        registry2 = AgentRegistry(data_dir=self.temp_dir)
        agent = registry2.get_agent("persistent-agent")

        self.assertIsNotNone(agent)
        self.assertEqual(agent.session_id, "session-xyz")
        self.assertIn("team-1", agent.teams)

    def test_teams_persist(self):
        """Test that teams are persisted to file."""
        registry1 = AgentRegistry(data_dir=self.temp_dir)
        registry1.create_team("persistent-team", "A team that persists", "parent")

        registry2 = AgentRegistry(data_dir=self.temp_dir)
        team = registry2.get_team("persistent-team")

        self.assertIsNotNone(team)
        self.assertEqual(team.description, "A team that persists")
        self.assertEqual(team.parent_team, "parent")

    def test_files_created(self):
        """Test that JSONL files are created."""
        registry = AgentRegistry(data_dir=self.temp_dir)
        registry.register_agent("agent", "session")
        registry.create_team("team")
        registry.record_message_sent("test", ["agent"])

        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "agents.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "teams.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "messages.jsonl")))


if __name__ == "__main__":
    unittest.main()
