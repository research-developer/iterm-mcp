"""Tests for the typed message-based communication system.

Tests cover:
- Base AgentMessage class functionality
- Message types for terminal operations
- Message handler registration and routing
- MessageRouter send/publish patterns
- Message serialization/deserialization
"""

import pytest
from datetime import datetime, timezone

from core.messaging import (
    # Base types
    AgentMessage,
    MessagePriority,
    # Terminal messages
    TerminalCommand,
    TerminalOutput,
    TerminalReadRequest,
    ControlCharacterMessage,
    SpecialKeyMessage,
    # Session messages
    SessionStatusRequest,
    SessionStatusResponse,
    SessionListRequest,
    FocusSessionMessage,
    # Agent orchestration messages
    BroadcastNotification,
    AgentTaskRequest,
    AgentTaskResponse,
    WaitForAgentMessage,
    ErrorMessage,
    # Routing
    MessageRouter,
    message_handler,
    topic_handler,
    get_handlers,
    get_topic_handlers,
    clear_handlers,
    # Utilities
    create_terminal_command,
    create_broadcast,
    MESSAGE_TYPES,
    serialize_message,
    deserialize_message,
)
from core.models import SessionTarget, ReadTarget


class TestAgentMessage:
    """Tests for the base AgentMessage class."""

    def test_create_basic_message(self):
        """Test creating a basic message with required fields."""
        msg = AgentMessage(sender="test-agent")

        assert msg.sender == "test-agent"
        assert msg.message_id is not None
        assert msg.timestamp is not None
        assert msg.priority == MessagePriority.NORMAL
        assert msg.correlation_id is None
        assert msg.metadata == {}

    def test_message_with_all_fields(self):
        """Test creating a message with all fields specified."""
        msg = AgentMessage(
            sender="orchestrator",
            correlation_id="req-123",
            priority=MessagePriority.HIGH,
            metadata={"key": "value"},
        )

        assert msg.sender == "orchestrator"
        assert msg.correlation_id == "req-123"
        assert msg.priority == MessagePriority.HIGH
        assert msg.metadata == {"key": "value"}

    def test_message_id_unique(self):
        """Test that each message gets a unique ID."""
        msg1 = AgentMessage(sender="agent1")
        msg2 = AgentMessage(sender="agent2")

        assert msg1.message_id != msg2.message_id

    def test_create_response_id(self):
        """Test creating a correlation ID for responses."""
        msg = AgentMessage(sender="agent")
        response_id = msg.create_response_id()

        assert response_id == msg.message_id

    def test_content_hash_same_content(self):
        """Test that identical content produces the same hash."""
        msg1 = AgentMessage(sender="agent", metadata={"key": "value"})
        msg2 = AgentMessage(sender="agent", metadata={"key": "value"})

        # Hash should be the same despite different timestamps/IDs
        assert msg1.content_hash() == msg2.content_hash()

    def test_content_hash_different_content(self):
        """Test that different content produces different hashes."""
        msg1 = AgentMessage(sender="agent1")
        msg2 = AgentMessage(sender="agent2")

        assert msg1.content_hash() != msg2.content_hash()

    def test_serialization(self):
        """Test message serialization to JSON-compatible dict."""
        msg = AgentMessage(
            sender="test",
            priority=MessagePriority.HIGH,
            metadata={"foo": "bar"},
        )

        data = msg.model_dump(mode="json")

        assert data["sender"] == "test"
        assert data["priority"] == "high"
        assert data["metadata"] == {"foo": "bar"}


class TestTerminalMessages:
    """Tests for terminal operation message types."""

    def test_terminal_command_creation(self):
        """Test creating a TerminalCommand message."""
        target = SessionTarget(agent="claude-1")
        cmd = TerminalCommand(
            sender="orchestrator",
            session_target=target,
            command="echo hello",
            timeout=60,
            wait_for_completion=True,
        )

        assert cmd.sender == "orchestrator"
        assert cmd.session_target.agent == "claude-1"
        assert cmd.command == "echo hello"
        assert cmd.timeout == 60
        assert cmd.wait_for_completion is True

    def test_terminal_command_defaults(self):
        """Test TerminalCommand default values."""
        cmd = TerminalCommand(
            sender="test",
            session_target=SessionTarget(session_id="sess-1"),
            command="ls",
        )

        assert cmd.timeout == 30
        assert cmd.wait_for_completion is True
        assert cmd.execute is True

    def test_terminal_output_creation(self):
        """Test creating a TerminalOutput response."""
        output = TerminalOutput(
            sender="terminal-service",
            session_id="sess-123",
            session_name="main",
            output="hello world\n",
            duration=0.5,
            line_count=1,
        )

        assert output.session_id == "sess-123"
        assert output.session_name == "main"
        assert output.output == "hello world\n"
        assert output.duration == 0.5
        assert output.truncated is False

    def test_terminal_read_request(self):
        """Test creating a TerminalReadRequest."""
        request = TerminalReadRequest(
            sender="agent",
            targets=[
                ReadTarget(agent="claude-1"),
                ReadTarget(agent="claude-2"),
            ],
            max_lines=100,
            filter_pattern=r"ERROR.*",
        )

        assert len(request.targets) == 2
        assert request.max_lines == 100
        assert request.filter_pattern == r"ERROR.*"

    def test_control_character_message(self):
        """Test creating a ControlCharacterMessage."""
        msg = ControlCharacterMessage(
            sender="orchestrator",
            session_target=SessionTarget(agent="claude-1"),
            character="c",
        )

        assert msg.character == "c"

    def test_special_key_message(self):
        """Test creating a SpecialKeyMessage."""
        msg = SpecialKeyMessage(
            sender="orchestrator",
            session_target=SessionTarget(agent="claude-1"),
            key="enter",
        )

        assert msg.key == "enter"


class TestSessionMessages:
    """Tests for session management message types."""

    def test_session_status_request(self):
        """Test creating a SessionStatusRequest."""
        request = SessionStatusRequest(
            sender="monitor",
            session_target=SessionTarget(agent="claude-1"),
        )

        assert request.session_target.agent == "claude-1"

    def test_session_status_response(self):
        """Test creating a SessionStatusResponse."""
        response = SessionStatusResponse(
            sender="terminal-service",
            session_id="sess-123",
            session_name="main",
            agent="claude-1",
            is_processing=True,
            is_at_prompt=False,
        )

        assert response.is_processing is True
        assert response.is_at_prompt is False

    def test_session_list_request(self):
        """Test creating a SessionListRequest."""
        request = SessionListRequest(
            sender="dashboard",
            include_agents=True,
            team_filter="backend",
        )

        assert request.include_agents is True
        assert request.team_filter == "backend"

    def test_focus_session_message(self):
        """Test creating a FocusSessionMessage."""
        msg = FocusSessionMessage(
            sender="orchestrator",
            session_target=SessionTarget(agent="claude-1"),
            bring_to_front=True,
        )

        assert msg.bring_to_front is True


class TestOrchestrationMessages:
    """Tests for agent orchestration message types."""

    def test_broadcast_notification(self):
        """Test creating a BroadcastNotification."""
        notification = BroadcastNotification(
            sender="coordinator",
            topic="agent.status",
            payload={"status": "ready", "agent": "claude-1"},
            target_teams=["backend"],
        )

        assert notification.topic == "agent.status"
        assert notification.payload["status"] == "ready"
        assert notification.target_teams == ["backend"]
        assert notification.exclude_sender is True

    def test_agent_task_request(self):
        """Test creating an AgentTaskRequest."""
        task = AgentTaskRequest(
            sender="orchestrator",
            task_type="code_review",
            task_description="Review the authentication module",
            parameters={"file": "auth.py", "focus": "security"},
            target_agent="claude-1",
            timeout=120,
        )

        assert task.task_type == "code_review"
        assert task.parameters["file"] == "auth.py"
        assert task.target_agent == "claude-1"

    def test_agent_task_response(self):
        """Test creating an AgentTaskResponse."""
        response = AgentTaskResponse(
            sender="claude-1",
            task_id="task-123",
            success=True,
            result={"issues": [], "approved": True},
            duration=45.5,
        )

        assert response.success is True
        assert response.result["approved"] is True

    def test_wait_for_agent_message(self):
        """Test creating a WaitForAgentMessage."""
        msg = WaitForAgentMessage(
            sender="orchestrator",
            target_agent="claude-1",
            timeout=60,
            include_output=True,
        )

        assert msg.target_agent == "claude-1"
        assert msg.timeout == 60

    def test_error_message(self):
        """Test creating an ErrorMessage."""
        error = ErrorMessage(
            sender="router",
            error_code="SESSION_NOT_FOUND",
            error_message="Session 'unknown' does not exist",
            original_message_id="req-123",
            recoverable=False,
        )

        assert error.error_code == "SESSION_NOT_FOUND"
        assert error.recoverable is False


class TestMessageHandlerDecorator:
    """Tests for the @message_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def teardown_method(self):
        """Clear handlers after each test."""
        clear_handlers()

    def test_register_handler(self):
        """Test registering a handler with the decorator."""
        @message_handler(TerminalCommand)
        async def handle_command(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="test",
                session_id="sess-1",
                output="handled",
            )

        handlers = get_handlers(TerminalCommand)
        assert len(handlers) == 1
        assert handlers[0] == handle_command

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers for the same message type."""
        @message_handler(TerminalCommand)
        async def handler1(msg: TerminalCommand) -> None:
            pass

        @message_handler(TerminalCommand)
        async def handler2(msg: TerminalCommand) -> None:
            pass

        handlers = get_handlers(TerminalCommand)
        assert len(handlers) == 2

    def test_no_handlers_for_unregistered_type(self):
        """Test that unregistered message types have no handlers."""
        handlers = get_handlers(TerminalCommand)
        assert len(handlers) == 0


class TestTopicHandlerDecorator:
    """Tests for the @topic_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def teardown_method(self):
        """Clear handlers after each test."""
        clear_handlers()

    def test_register_topic_handler(self):
        """Test registering a topic handler."""
        @topic_handler("agent.status")
        async def on_status(notification: BroadcastNotification):
            pass

        handlers = get_topic_handlers("agent.status")
        assert len(handlers) == 1

    def test_multiple_topic_handlers(self):
        """Test registering multiple handlers for the same topic."""
        @topic_handler("agent.status")
        async def handler1(notification: BroadcastNotification):
            pass

        @topic_handler("agent.status")
        async def handler2(notification: BroadcastNotification):
            pass

        handlers = get_topic_handlers("agent.status")
        assert len(handlers) == 2


class TestMessageRouter:
    """Tests for the MessageRouter class."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def teardown_method(self):
        """Clear handlers after each test."""
        clear_handlers()

    @pytest.mark.asyncio
    async def test_send_with_handler(self):
        """Test sending a message that has a registered handler."""
        router = MessageRouter(deduplicate=False)

        @message_handler(TerminalCommand)
        async def handle_command(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="test-service",
                session_id="sess-1",
                output=f"Executed: {msg.command}",
            )

        response = await router.send(
            TerminalCommand(
                sender="test",
                session_target=SessionTarget(session_id="sess-1"),
                command="echo hello",
            )
        )

        assert response is not None
        assert isinstance(response, TerminalOutput)
        assert "Executed: echo hello" in response.output

    @pytest.mark.asyncio
    async def test_send_without_handler(self):
        """Test that sending without a handler raises an error."""
        router = MessageRouter()

        with pytest.raises(ValueError, match="No handlers registered"):
            await router.send(
                TerminalCommand(
                    sender="test",
                    session_target=SessionTarget(session_id="sess-1"),
                    command="echo hello",
                )
            )

    @pytest.mark.asyncio
    async def test_send_with_correlation_id(self):
        """Test that responses get correlation IDs from requests."""
        router = MessageRouter(deduplicate=False)

        @message_handler(TerminalCommand)
        async def handle_command(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="test",
                session_id="sess-1",
                output="ok",
            )

        request = TerminalCommand(
            sender="test",
            session_target=SessionTarget(session_id="sess-1"),
            command="echo",
        )
        response = await router.send(request)

        assert response.correlation_id == request.message_id

    @pytest.mark.asyncio
    async def test_send_deduplication(self):
        """Test that duplicate messages are skipped."""
        router = MessageRouter(deduplicate=True)
        call_count = 0

        @message_handler(TerminalCommand)
        async def handle_command(msg: TerminalCommand) -> TerminalOutput:
            nonlocal call_count
            call_count += 1
            return TerminalOutput(
                sender="test",
                session_id="sess-1",
                output="ok",
            )

        cmd = TerminalCommand(
            sender="test",
            session_target=SessionTarget(session_id="sess-1"),
            command="echo hello",
        )

        # First send should work
        response1 = await router.send(cmd)
        assert response1 is not None
        assert call_count == 1

        # Second send of same content should be skipped due to deduplication
        response2 = await router.send(cmd)
        assert response2 is None
        # Verify handler was NOT called again (would be 2 if dedup failed)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_send_multi(self):
        """Test sending a message and collecting all handler responses."""
        router = MessageRouter(deduplicate=False)

        @message_handler(TerminalCommand)
        async def handler1(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="handler1",
                session_id="sess-1",
                output="response1",
            )

        @message_handler(TerminalCommand)
        async def handler2(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="handler2",
                session_id="sess-1",
                output="response2",
            )

        responses = await router.send_multi(
            TerminalCommand(
                sender="test",
                session_target=SessionTarget(session_id="sess-1"),
                command="echo",
            )
        )

        assert len(responses) == 2
        senders = {r.sender for r in responses}
        assert "handler1" in senders
        assert "handler2" in senders

    @pytest.mark.asyncio
    async def test_publish_topic(self):
        """Test publishing a notification to a topic."""
        router = MessageRouter()
        received = []

        @topic_handler("test.topic")
        async def on_notification(notification: BroadcastNotification):
            received.append(notification)

        count = await router.publish(
            topic="test.topic",
            payload={"message": "hello"},
            sender="test",
        )

        assert count == 1
        assert len(received) == 1
        assert received[0].payload["message"] == "hello"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting a pre-constructed notification."""
        router = MessageRouter()
        received = []

        @topic_handler("agent.update")
        async def on_update(notification: BroadcastNotification):
            received.append(notification)

        notification = BroadcastNotification(
            sender="coordinator",
            topic="agent.update",
            payload={"agent": "claude-1", "status": "idle"},
        )

        count = await router.broadcast(notification)

        assert count == 1
        assert received[0].sender == "coordinator"

    @pytest.mark.asyncio
    async def test_handler_error_returns_error_message(self):
        """Test that handler errors are wrapped in ErrorMessage."""
        router = MessageRouter(deduplicate=False)

        @message_handler(TerminalCommand)
        async def failing_handler(msg: TerminalCommand) -> TerminalOutput:
            raise RuntimeError("Something went wrong")

        response = await router.send(
            TerminalCommand(
                sender="test",
                session_target=SessionTarget(session_id="sess-1"),
                command="fail",
            )
        )

        assert isinstance(response, ErrorMessage)
        assert response.error_code == "HANDLER_ERROR"
        assert "Something went wrong" in response.error_message

    def test_register_handler_programmatically(self):
        """Test registering a handler without the decorator."""
        router = MessageRouter()

        async def my_handler(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(
                sender="test",
                session_id="sess-1",
                output="ok",
            )

        router.register_handler(TerminalCommand, my_handler)

        assert router.has_handler(TerminalCommand) is True

    def test_has_handler(self):
        """Test checking if a handler exists for a message type."""
        router = MessageRouter()

        assert router.has_handler(TerminalCommand) is False

        @message_handler(TerminalCommand)
        async def handle(msg: TerminalCommand) -> None:
            pass

        assert router.has_handler(TerminalCommand) is True


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_terminal_command(self):
        """Test the create_terminal_command helper."""
        cmd = create_terminal_command(
            sender="test",
            agent="claude-1",
            command="echo hello",
            timeout=60,
        )

        assert cmd.sender == "test"
        assert cmd.session_target.agent == "claude-1"
        assert cmd.command == "echo hello"
        assert cmd.timeout == 60

    def test_create_terminal_command_with_session_id(self):
        """Test creating a command with session ID."""
        cmd = create_terminal_command(
            sender="test",
            session_id="sess-123",
            command="ls",
        )

        assert cmd.session_target.session_id == "sess-123"

    def test_create_broadcast(self):
        """Test the create_broadcast helper."""
        notification = create_broadcast(
            sender="coordinator",
            topic="status.update",
            payload={"key": "value"},
            teams=["backend"],
        )

        assert notification.sender == "coordinator"
        assert notification.topic == "status.update"
        assert notification.payload == {"key": "value"}
        assert notification.target_teams == ["backend"]


class TestMessageSerialization:
    """Tests for message serialization/deserialization."""

    def test_serialize_message(self):
        """Test serializing a message to JSON-compatible dict."""
        cmd = TerminalCommand(
            sender="test",
            session_target=SessionTarget(agent="claude-1"),
            command="echo hello",
        )

        data = serialize_message(cmd)

        assert data["_type"] == "TerminalCommand"
        assert data["sender"] == "test"
        assert data["command"] == "echo hello"

    def test_deserialize_message(self):
        """Test deserializing a message from dict."""
        data = {
            "_type": "TerminalCommand",
            "sender": "test",
            "session_target": {"agent": "claude-1"},
            "command": "echo hello",
            "timeout": 30,
            "wait_for_completion": True,
            "execute": True,
            "message_id": "test-id",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "priority": "normal",
            "correlation_id": None,
            "metadata": {},
        }

        msg = deserialize_message(data)

        assert isinstance(msg, TerminalCommand)
        assert msg.sender == "test"
        assert msg.command == "echo hello"

    def test_deserialize_unknown_type(self):
        """Test that deserializing unknown type raises error."""
        data = {"_type": "UnknownMessage", "sender": "test"}

        with pytest.raises(ValueError, match="Unknown message type"):
            deserialize_message(data)

    def test_deserialize_missing_type(self):
        """Test that deserializing without _type raises error."""
        data = {"sender": "test"}

        with pytest.raises(ValueError, match="must include '_type' field"):
            deserialize_message(data)

    def test_roundtrip_serialization(self):
        """Test that serialize -> deserialize produces equivalent message."""
        original = TerminalCommand(
            sender="test",
            session_target=SessionTarget(agent="claude-1"),
            command="echo hello",
            timeout=60,
            metadata={"key": "value"},
        )

        serialized = serialize_message(original)
        restored = deserialize_message(serialized)

        assert isinstance(restored, TerminalCommand)
        assert restored.sender == original.sender
        assert restored.command == original.command
        assert restored.timeout == original.timeout
        assert restored.metadata == original.metadata

    def test_message_types_registry(self):
        """Test that MESSAGE_TYPES contains all message classes."""
        expected_types = [
            "AgentMessage",
            "TerminalCommand",
            "TerminalOutput",
            "BroadcastNotification",
            "ErrorMessage",
        ]

        for type_name in expected_types:
            assert type_name in MESSAGE_TYPES


class TestMessagePriority:
    """Tests for message priority handling."""

    def test_priority_values(self):
        """Test that priority values are correct."""
        assert MessagePriority.LOW == "low"
        assert MessagePriority.NORMAL == "normal"
        assert MessagePriority.HIGH == "high"
        assert MessagePriority.URGENT == "urgent"

    def test_message_with_priority(self):
        """Test creating messages with different priorities."""
        normal = AgentMessage(sender="test")
        urgent = AgentMessage(sender="test", priority=MessagePriority.URGENT)

        assert normal.priority == MessagePriority.NORMAL
        assert urgent.priority == MessagePriority.URGENT
