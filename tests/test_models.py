"""Tests for Pydantic API models."""

import unittest
from pydantic import ValidationError

from core.models import (
    SessionTarget,
    SessionMessage,
    WriteToSessionsRequest,
    WriteResult,
    WriteToSessionsResponse,
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
    Playbook,
    PlaybookCommand,
    OrchestrateRequest,
    WaitForAgentRequest,
    WaitResult,
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

    def test_encoding_default_is_false(self):
        """Test that use_encoding defaults to False (no base64 encoding)."""
        msg = SessionMessage(content="echo 'hello world'")
        self.assertFalse(msg.use_encoding)


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


class TestWriteResponses(unittest.TestCase):
    """Test write result and response models."""

    def test_write_result_defaults(self):
        """Default write result flags are false/None."""
        result = WriteResult(session_id="abc", session_name="main")
        self.assertFalse(result.success)
        self.assertFalse(result.skipped)
        self.assertIsNone(result.error)

    def test_write_response_counts(self):
        """WriteToSessionsResponse computes counts."""
        response = WriteToSessionsResponse(
            results=[
                WriteResult(session_id="1", session_name="a", success=True),
                WriteResult(session_id="2", session_name="b", skipped=True, skipped_reason="duplicate"),
                WriteResult(session_id="3", session_name="c", success=False, error="boom"),
            ],
            sent_count=1,
            skipped_count=1,
            error_count=1,
        )
        self.assertEqual(response.sent_count, 1)
        self.assertEqual(response.skipped_count, 1)
        self.assertEqual(response.error_count, 1)


class TestPlaybookModels(unittest.TestCase):
    """Test playbook orchestration models."""

    def test_playbook_structure(self):
        """Playbook nests layout, commands, cascade, and reads."""
        playbook = Playbook(
            layout=CreateSessionsRequest(sessions=[SessionConfig(name="one")], layout="SINGLE"),
            commands=[
                PlaybookCommand(
                    name="setup",
                    messages=[SessionMessage(content="echo hi", targets=[SessionTarget(name="one")])],
                    parallel=False,
                )
            ],
            cascade=CascadeMessageRequest(broadcast="hello"),
            reads=ReadSessionsRequest(targets=[ReadTarget(name="one")]),
        )

        request = OrchestrateRequest(playbook=playbook)
        self.assertEqual(request.playbook.commands[0].name, "setup")
        self.assertEqual(request.playbook.commands[0].parallel, False)
        self.assertIsNotNone(request.playbook.cascade.broadcast)


class TestWaitForAgentRequest(unittest.TestCase):
    """Test WaitForAgentRequest model."""

    def test_minimal_request(self):
        """Test minimal request with just agent name."""
        request = WaitForAgentRequest(agent="codex-1")
        self.assertEqual(request.agent, "codex-1")
        self.assertEqual(request.wait_up_to, 30)  # default
        self.assertTrue(request.return_output)  # default
        self.assertTrue(request.summary_on_timeout)  # default

    def test_custom_timeout(self):
        """Test request with custom timeout."""
        request = WaitForAgentRequest(agent="agent-1", wait_up_to=60)
        self.assertEqual(request.wait_up_to, 60)

    def test_minimum_timeout(self):
        """Test minimum timeout value (1 second)."""
        request = WaitForAgentRequest(agent="agent-1", wait_up_to=1)
        self.assertEqual(request.wait_up_to, 1)

    def test_maximum_timeout(self):
        """Test maximum timeout value (600 seconds = 10 minutes)."""
        request = WaitForAgentRequest(agent="agent-1", wait_up_to=600)
        self.assertEqual(request.wait_up_to, 600)

    def test_timeout_below_minimum_raises_error(self):
        """Test that timeout below 1 raises validation error."""
        with self.assertRaises(ValidationError):
            WaitForAgentRequest(agent="agent-1", wait_up_to=0)

    def test_timeout_above_maximum_raises_error(self):
        """Test that timeout above 600 raises validation error."""
        with self.assertRaises(ValidationError):
            WaitForAgentRequest(agent="agent-1", wait_up_to=601)

    def test_disable_output(self):
        """Test disabling output return."""
        request = WaitForAgentRequest(agent="agent-1", return_output=False)
        self.assertFalse(request.return_output)

    def test_disable_summary(self):
        """Test disabling summary on timeout."""
        request = WaitForAgentRequest(agent="agent-1", summary_on_timeout=False)
        self.assertFalse(request.summary_on_timeout)

    def test_full_request(self):
        """Test fully specified request."""
        request = WaitForAgentRequest(
            agent="build-agent",
            wait_up_to=120,
            return_output=True,
            summary_on_timeout=True
        )
        self.assertEqual(request.agent, "build-agent")
        self.assertEqual(request.wait_up_to, 120)
        self.assertTrue(request.return_output)
        self.assertTrue(request.summary_on_timeout)


class TestWaitResult(unittest.TestCase):
    """Test WaitResult model."""

    def test_completed_result(self):
        """Test result when agent completed successfully."""
        result = WaitResult(
            agent="codex-1",
            completed=True,
            timed_out=False,
            elapsed_seconds=5.2,
            status="idle",
            output="Build complete\nAll tests passed",
            summary="Agent completed successfully",
            can_continue_waiting=False
        )
        self.assertTrue(result.completed)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.status, "idle")
        self.assertFalse(result.can_continue_waiting)

    def test_timeout_result(self):
        """Test result when wait timed out."""
        result = WaitResult(
            agent="codex-1",
            completed=False,
            timed_out=True,
            elapsed_seconds=30.0,
            status="running",
            output="Building modules... 847/1203 complete",
            summary="Build in progress: 70% complete",
            can_continue_waiting=True
        )
        self.assertFalse(result.completed)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.status, "running")
        self.assertTrue(result.can_continue_waiting)

    def test_error_result(self):
        """Test result when error occurred."""
        result = WaitResult(
            agent="unknown-agent",
            completed=False,
            timed_out=False,
            elapsed_seconds=0,
            status="error",
            summary="Agent 'unknown-agent' not found",
            can_continue_waiting=False
        )
        self.assertEqual(result.status, "error")
        self.assertFalse(result.can_continue_waiting)

    def test_blocked_status(self):
        """Test result with blocked status."""
        result = WaitResult(
            agent="blocked-agent",
            completed=False,
            timed_out=True,
            elapsed_seconds=30.0,
            status="blocked",
            summary="Waiting for user input",
            can_continue_waiting=True
        )
        self.assertEqual(result.status, "blocked")

    def test_unknown_status(self):
        """Test result with unknown status."""
        result = WaitResult(
            agent="mystery-agent",
            completed=False,
            timed_out=False,
            elapsed_seconds=0,
            status="unknown",
            summary="Session not found",
            can_continue_waiting=False
        )
        self.assertEqual(result.status, "unknown")

    def test_optional_output(self):
        """Test result with no output."""
        result = WaitResult(
            agent="agent-1",
            completed=True,
            timed_out=False,
            elapsed_seconds=2.5,
            status="idle",
            can_continue_waiting=False
        )
        self.assertIsNone(result.output)

    def test_optional_summary(self):
        """Test result with no summary."""
        result = WaitResult(
            agent="agent-1",
            completed=True,
            timed_out=False,
            elapsed_seconds=2.5,
            status="idle",
            can_continue_waiting=False
        )
        self.assertIsNone(result.summary)

    def test_json_serialization(self):
        """Test JSON serialization works correctly."""
        result = WaitResult(
            agent="codex-1",
            completed=True,
            timed_out=False,
            elapsed_seconds=10.5,
            status="idle",
            output="Done",
            summary="Task completed",
            can_continue_waiting=False
        )
        json_str = result.model_dump_json()
        self.assertIn('"agent":"codex-1"', json_str.replace(" ", ""))
        self.assertIn('"completed":true', json_str.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
