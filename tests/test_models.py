"""Tests for Pydantic API models."""

import unittest
from pydantic import ValidationError

from core.models import (
    SessionTarget,
    SessionMessage,
    WriteToSessionsRequest,
    ReadTarget,
    ReadSessionsRequest,
    SessionOutput,
    SessionConfig,
    CreateSessionsRequest,
    CascadeMessageRequest,
    CascadeResult,
    RegisterAgentRequest,
    CreateTeamRequest,
    SetActiveSessionRequest,
)


class TestSessionTarget(unittest.TestCase):
    """Test SessionTarget model."""

    def test_empty_target_raises_error(self):
        """Test that empty target raises validation error."""
        with self.assertRaises(ValidationError) as context:
            SessionTarget()
        self.assertIn("At least one identifier", str(context.exception))

    def test_target_by_session_id(self):
        """Test targeting by session ID."""
        target = SessionTarget(session_id="abc-123")
        self.assertEqual(target.session_id, "abc-123")

    def test_target_by_name(self):
        """Test targeting by name."""
        target = SessionTarget(name="MainSession")
        self.assertEqual(target.name, "MainSession")

    def test_target_by_agent(self):
        """Test targeting by agent name."""
        target = SessionTarget(agent="alice")
        self.assertEqual(target.agent, "alice")

    def test_target_by_team(self):
        """Test targeting by team name."""
        target = SessionTarget(team="frontend")
        self.assertEqual(target.team, "frontend")


class TestSessionMessage(unittest.TestCase):
    """Test SessionMessage model."""

    def test_simple_message(self):
        """Test creating a simple message."""
        msg = SessionMessage(content="ls -la")
        self.assertEqual(msg.content, "ls -la")
        self.assertEqual(msg.targets, [])
        self.assertTrue(msg.execute)

    def test_message_with_targets(self):
        """Test message with multiple targets."""
        msg = SessionMessage(
            content="echo hello",
            targets=[
                SessionTarget(name="Session1"),
                SessionTarget(name="Session2")
            ]
        )
        self.assertEqual(len(msg.targets), 2)

    def test_message_with_condition(self):
        """Test message with regex condition."""
        msg = SessionMessage(
            content="npm install",
            condition=r"\$\s*$"  # Match shell prompt
        )
        self.assertEqual(msg.condition, r"\$\s*$")

    def test_invalid_regex_condition(self):
        """Test that invalid regex raises error."""
        with self.assertRaises(ValidationError):
            SessionMessage(
                content="test",
                condition="[invalid("  # Invalid regex
            )

    def test_message_no_execute(self):
        """Test message without pressing Enter."""
        msg = SessionMessage(content="partial input", execute=False)
        self.assertFalse(msg.execute)

    def test_encoding_options(self):
        """Test use_encoding options."""
        msg_auto = SessionMessage(content="test", use_encoding="auto")
        msg_true = SessionMessage(content="test", use_encoding=True)
        msg_false = SessionMessage(content="test", use_encoding=False)

        self.assertEqual(msg_auto.use_encoding, "auto")
        self.assertTrue(msg_true.use_encoding)
        self.assertFalse(msg_false.use_encoding)


class TestWriteToSessionsRequest(unittest.TestCase):
    """Test WriteToSessionsRequest model."""

    def test_single_message(self):
        """Test request with single message."""
        request = WriteToSessionsRequest(
            messages=[SessionMessage(content="pwd")]
        )
        self.assertEqual(len(request.messages), 1)
        self.assertTrue(request.parallel)
        self.assertTrue(request.skip_duplicates)

    def test_multiple_messages_sequential(self):
        """Test sequential message execution."""
        request = WriteToSessionsRequest(
            messages=[
                SessionMessage(content="cd /tmp"),
                SessionMessage(content="ls")
            ],
            parallel=False
        )
        self.assertFalse(request.parallel)

    def test_allow_duplicates(self):
        """Test disabling duplicate skipping."""
        request = WriteToSessionsRequest(
            messages=[SessionMessage(content="test")],
            skip_duplicates=False
        )
        self.assertFalse(request.skip_duplicates)


class TestReadTarget(unittest.TestCase):
    """Test ReadTarget model."""

    def test_read_target_with_max_lines(self):
        """Test read target with line limit."""
        target = ReadTarget(name="Session1", max_lines=50)
        self.assertEqual(target.max_lines, 50)


class TestReadSessionsRequest(unittest.TestCase):
    """Test ReadSessionsRequest model."""

    def test_empty_request(self):
        """Test empty request (reads active session)."""
        request = ReadSessionsRequest()
        self.assertEqual(request.targets, [])
        self.assertTrue(request.parallel)

    def test_with_filter(self):
        """Test request with output filter."""
        request = ReadSessionsRequest(
            filter_pattern=r"ERROR|WARN"
        )
        self.assertEqual(request.filter_pattern, r"ERROR|WARN")

    def test_invalid_filter_regex(self):
        """Test that invalid filter regex raises error."""
        with self.assertRaises(ValidationError):
            ReadSessionsRequest(filter_pattern="[invalid(")


class TestSessionOutput(unittest.TestCase):
    """Test SessionOutput model."""

    def test_output_model(self):
        """Test creating session output."""
        output = SessionOutput(
            session_id="abc-123",
            name="MainSession",
            content="Hello World\n",
            line_count=1
        )
        self.assertEqual(output.session_id, "abc-123")
        self.assertFalse(output.truncated)

    def test_truncated_output(self):
        """Test output marked as truncated."""
        output = SessionOutput(
            session_id="xyz",
            name="Session",
            content="...",
            line_count=100,
            truncated=True
        )
        self.assertTrue(output.truncated)


class TestSessionConfig(unittest.TestCase):
    """Test SessionConfig model."""

    def test_minimal_config(self):
        """Test minimal session configuration."""
        config = SessionConfig(name="TestSession")
        self.assertEqual(config.name, "TestSession")
        self.assertIsNone(config.agent)
        self.assertIsNone(config.command)
        self.assertFalse(config.monitor)

    def test_full_config(self):
        """Test full session configuration."""
        config = SessionConfig(
            name="AgentSession",
            agent="alice",
            team="frontend",
            command="cd ~/project",
            max_lines=200,
            monitor=True
        )
        self.assertEqual(config.agent, "alice")
        self.assertEqual(config.team, "frontend")
        self.assertEqual(config.command, "cd ~/project")
        self.assertTrue(config.monitor)


class TestCreateSessionsRequest(unittest.TestCase):
    """Test CreateSessionsRequest model."""

    def test_single_session(self):
        """Test creating single session request."""
        request = CreateSessionsRequest(
            sessions=[SessionConfig(name="Session1")]
        )
        self.assertEqual(len(request.sessions), 1)
        self.assertEqual(request.layout, "SINGLE")

    def test_multi_session_layout(self):
        """Test multi-session with layout."""
        request = CreateSessionsRequest(
            sessions=[
                SessionConfig(name="Left"),
                SessionConfig(name="Right")
            ],
            layout="HORIZONTAL_SPLIT"
        )
        self.assertEqual(request.layout, "HORIZONTAL_SPLIT")


class TestCascadeMessageRequest(unittest.TestCase):
    """Test CascadeMessageRequest model."""

    def test_broadcast_only(self):
        """Test broadcast message only."""
        request = CascadeMessageRequest(
            broadcast="Hello all agents!"
        )
        self.assertEqual(request.broadcast, "Hello all agents!")
        self.assertEqual(request.teams, {})
        self.assertEqual(request.agents, {})

    def test_team_messages(self):
        """Test team-specific messages."""
        request = CascadeMessageRequest(
            teams={
                "frontend": "Work on UI",
                "backend": "Work on API"
            }
        )
        self.assertEqual(len(request.teams), 2)

    def test_full_cascade(self):
        """Test full cascade with all levels."""
        request = CascadeMessageRequest(
            broadcast="General info",
            teams={"frontend": "Frontend specific"},
            agents={"alice": "Alice's task"}
        )
        self.assertIsNotNone(request.broadcast)
        self.assertEqual(len(request.teams), 1)
        self.assertEqual(len(request.agents), 1)


class TestCascadeResult(unittest.TestCase):
    """Test CascadeResult model."""

    def test_successful_delivery(self):
        """Test successful message delivery result."""
        result = CascadeResult(
            agent="alice",
            session_id="session-1",
            message_type="broadcast",
            delivered=True
        )
        self.assertTrue(result.delivered)
        self.assertIsNone(result.skipped_reason)

    def test_skipped_delivery(self):
        """Test skipped message delivery."""
        result = CascadeResult(
            agent="bob",
            session_id="session-2",
            message_type="team",
            delivered=False,
            skipped_reason="duplicate"
        )
        self.assertFalse(result.delivered)
        self.assertEqual(result.skipped_reason, "duplicate")


class TestRegisterAgentRequest(unittest.TestCase):
    """Test RegisterAgentRequest model."""

    def test_minimal_registration(self):
        """Test minimal agent registration."""
        request = RegisterAgentRequest(
            name="agent-1",
            session_id="session-abc"
        )
        self.assertEqual(request.name, "agent-1")
        self.assertEqual(request.teams, [])

    def test_full_registration(self):
        """Test full agent registration."""
        request = RegisterAgentRequest(
            name="agent-1",
            session_id="session-abc",
            teams=["team-a", "team-b"],
            metadata={"role": "coordinator"}
        )
        self.assertEqual(len(request.teams), 2)
        self.assertEqual(request.metadata["role"], "coordinator")


class TestCreateTeamRequest(unittest.TestCase):
    """Test CreateTeamRequest model."""

    def test_simple_team(self):
        """Test simple team creation."""
        request = CreateTeamRequest(name="engineering")
        self.assertEqual(request.name, "engineering")
        self.assertEqual(request.description, "")
        self.assertIsNone(request.parent_team)

    def test_nested_team(self):
        """Test nested team creation."""
        request = CreateTeamRequest(
            name="frontend",
            description="Frontend team",
            parent_team="engineering"
        )
        self.assertEqual(request.parent_team, "engineering")


class TestSetActiveSessionRequest(unittest.TestCase):
    """Test SetActiveSessionRequest model."""

    def test_by_session_id(self):
        """Test setting active by session ID."""
        request = SetActiveSessionRequest(session_id="xyz-123")
        self.assertEqual(request.session_id, "xyz-123")

    def test_by_agent(self):
        """Test setting active by agent name."""
        request = SetActiveSessionRequest(agent="alice")
        self.assertEqual(request.agent, "alice")

    def test_by_name(self):
        """Test setting active by session name."""
        request = SetActiveSessionRequest(name="MainSession")
        self.assertEqual(request.name, "MainSession")


if __name__ == "__main__":
    unittest.main()
