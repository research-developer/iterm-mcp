"""Typed message-based communication pattern for agent orchestration.

This module implements AutoGen-style message-based communication where:
- Agents never directly invoke methods on each other
- All communication is through serializable Pydantic messages
- Request/response and pub/sub patterns are supported
- Type-based routing with handler decorators

Example usage:
    from core.messaging import (
        MessageRouter,
        TerminalCommand,
        TerminalOutput,
        message_handler,
    )

    router = MessageRouter()

    @message_handler(TerminalCommand)
    async def handle_command(message: TerminalCommand) -> TerminalOutput:
        # Execute the command
        output = await execute_in_session(message.session_target, message.command)
        return TerminalOutput(
            sender="terminal-service",
            session_id=message.session_target.session_id,
            output=output,
            correlation_id=message.correlation_id
        )

    # Send a command
    response = await router.send(TerminalCommand(
        sender="orchestrator",
        session_target=SessionTarget(agent="claude-1"),
        command="echo hello"
    ))
"""

import asyncio
import hashlib
import uuid
from abc import ABC
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Field

from .models import SessionTarget, ReadTarget


# Type variable for message types
M = TypeVar("M", bound="AgentMessage")
R = TypeVar("R", bound="AgentMessage")

# Handler type: async function that takes a message and optionally returns a response
HandlerFunc = Callable[[M], Awaitable[Optional[R]]]


# ============================================================================
# BASE MESSAGE TYPES
# ============================================================================


class MessagePriority(str, Enum):
    """Priority levels for message routing."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AgentMessage(BaseModel):
    """Base class for all agent messages.

    All inter-agent communication is through subclasses of this type.
    Messages are serializable via Pydantic for distributed execution.

    Attributes:
        sender: Name of the agent/service sending the message
        timestamp: When the message was created
        correlation_id: Optional ID to correlate request/response pairs
        message_id: Unique identifier for this message instance
        priority: Message priority for routing decisions
        metadata: Optional key-value metadata for extensibility
    """

    sender: str = Field(..., description="Name of the sending agent/service")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the message was created"
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="ID to correlate request/response pairs"
    )
    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this message"
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority for routing"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extensible metadata"
    )

    def create_response_id(self) -> str:
        """Create a correlation ID for responses to this message."""
        return self.message_id

    def content_hash(self) -> str:
        """Create a hash of message content for deduplication."""
        # Exclude timestamp and message_id from hash for content-based dedup
        data = self.model_dump(exclude={"timestamp", "message_id"})
        content = str(sorted(data.items()))
        return hashlib.sha256(content.encode()).hexdigest()

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
        },
    }


# ============================================================================
# TERMINAL OPERATION MESSAGES
# ============================================================================


class TerminalCommand(AgentMessage):
    """Request to execute a terminal command.

    This message type is used when an agent wants to execute
    a command in a terminal session.
    """

    session_target: SessionTarget = Field(
        ...,
        description="Target session for command execution"
    )
    command: str = Field(
        ...,
        description="The command to execute"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=600,
        description="Command timeout in seconds"
    )
    wait_for_completion: bool = Field(
        default=True,
        description="Whether to wait for command to complete"
    )
    execute: bool = Field(
        default=True,
        description="Whether to press Enter after sending"
    )


class TerminalOutput(AgentMessage):
    """Response containing terminal output.

    Returned after a TerminalCommand is processed.
    """

    session_id: str = Field(
        ...,
        description="Session that produced the output"
    )
    session_name: Optional[str] = Field(
        default=None,
        description="Human-readable session name"
    )
    output: str = Field(
        ...,
        description="The terminal output content"
    )
    exit_code: Optional[int] = Field(
        default=None,
        description="Exit code if available"
    )
    duration: float = Field(
        default=0.0,
        description="Execution duration in seconds"
    )
    truncated: bool = Field(
        default=False,
        description="Whether output was truncated"
    )
    line_count: int = Field(
        default=0,
        description="Number of lines in output"
    )


class TerminalReadRequest(AgentMessage):
    """Request to read terminal output without executing a command."""

    targets: List[ReadTarget] = Field(
        default_factory=list,
        description="Sessions to read from"
    )
    max_lines: Optional[int] = Field(
        default=None,
        description="Maximum lines to return per session"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern to filter output"
    )


class TerminalReadResponse(AgentMessage):
    """Response containing read terminal content."""

    outputs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Output from each session"
    )
    total_sessions: int = Field(
        default=0,
        description="Number of sessions read"
    )


class ControlCharacterMessage(AgentMessage):
    """Request to send a control character to a session."""

    session_target: SessionTarget = Field(
        ...,
        description="Target session"
    )
    character: str = Field(
        ...,
        description="Control character (e.g., 'c' for Ctrl+C)"
    )


class SpecialKeyMessage(AgentMessage):
    """Request to send a special key to a session."""

    session_target: SessionTarget = Field(
        ...,
        description="Target session"
    )
    key: str = Field(
        ...,
        description="Special key name (enter, tab, escape, up, down, etc.)"
    )


# ============================================================================
# SESSION MANAGEMENT MESSAGES
# ============================================================================


class SessionStatusRequest(AgentMessage):
    """Request to check session status."""

    session_target: SessionTarget = Field(
        ...,
        description="Target session to check"
    )


class SessionStatusResponse(AgentMessage):
    """Response with session status information."""

    session_id: str = Field(..., description="Session ID")
    session_name: Optional[str] = Field(default=None, description="Session name")
    agent: Optional[str] = Field(default=None, description="Registered agent name")
    is_processing: bool = Field(default=False, description="Whether session is busy")
    is_at_prompt: bool = Field(default=True, description="Whether at command prompt")
    line_count: int = Field(default=0, description="Current line count")


class SessionListRequest(AgentMessage):
    """Request to list available sessions."""

    include_agents: bool = Field(
        default=True,
        description="Include agent information"
    )
    team_filter: Optional[str] = Field(
        default=None,
        description="Filter by team name"
    )


class SessionListResponse(AgentMessage):
    """Response containing list of sessions."""

    sessions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of session information"
    )
    total_count: int = Field(default=0, description="Total session count")


class FocusSessionMessage(AgentMessage):
    """Request to focus a specific session."""

    session_target: SessionTarget = Field(
        ...,
        description="Session to focus"
    )
    bring_to_front: bool = Field(
        default=False,
        description="Also bring iTerm to front"
    )


# ============================================================================
# AGENT ORCHESTRATION MESSAGES
# ============================================================================


class BroadcastNotification(AgentMessage):
    """One-way notification to all agents or a specific topic.

    Used for pub/sub style communication where no response is expected.
    """

    topic: str = Field(
        ...,
        description="Topic/channel for the notification"
    )
    payload: Any = Field(
        ...,
        description="Notification payload (must be JSON-serializable)"
    )
    target_teams: List[str] = Field(
        default_factory=list,
        description="Specific teams to notify (empty = all)"
    )
    target_agents: List[str] = Field(
        default_factory=list,
        description="Specific agents to notify (empty = all)"
    )
    exclude_sender: bool = Field(
        default=True,
        description="Whether to exclude sender from receiving"
    )


class AgentTaskRequest(AgentMessage):
    """Request for an agent to perform a task.

    Generic task delegation message for agent-to-agent communication.
    """

    task_type: str = Field(
        ...,
        description="Type of task to perform"
    )
    task_description: str = Field(
        default="",
        description="Human-readable task description"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task parameters"
    )
    target_agent: Optional[str] = Field(
        default=None,
        description="Specific agent to handle the task"
    )
    target_team: Optional[str] = Field(
        default=None,
        description="Team to route the task to"
    )
    timeout: int = Field(
        default=60,
        description="Task timeout in seconds"
    )


class AgentTaskResponse(AgentMessage):
    """Response from an agent task."""

    task_id: str = Field(
        ...,
        description="ID of the task this responds to"
    )
    success: bool = Field(
        default=False,
        description="Whether the task succeeded"
    )
    result: Any = Field(
        default=None,
        description="Task result (if successful)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message (if failed)"
    )
    duration: float = Field(
        default=0.0,
        description="Task duration in seconds"
    )


class WaitForAgentMessage(AgentMessage):
    """Request to wait for an agent to become idle."""

    target_agent: str = Field(
        ...,
        description="Agent to wait for"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=600,
        description="Maximum wait time in seconds"
    )
    include_output: bool = Field(
        default=True,
        description="Include recent output in response"
    )


class WaitForAgentResponse(AgentMessage):
    """Response from waiting for an agent."""

    agent: str = Field(..., description="Agent name")
    completed: bool = Field(..., description="Whether agent became idle")
    timed_out: bool = Field(default=False, description="Whether wait timed out")
    elapsed: float = Field(default=0.0, description="Time waited in seconds")
    output: Optional[str] = Field(default=None, description="Recent output")


# ============================================================================
# ERROR MESSAGES
# ============================================================================


class ErrorMessage(AgentMessage):
    """Error response message for failed operations."""

    error_code: str = Field(
        ...,
        description="Error code for programmatic handling"
    )
    error_message: str = Field(
        ...,
        description="Human-readable error description"
    )
    original_message_id: Optional[str] = Field(
        default=None,
        description="ID of the message that caused the error"
    )
    recoverable: bool = Field(
        default=True,
        description="Whether the error is recoverable"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details"
    )


# ============================================================================
# MESSAGE HANDLER REGISTRY
# ============================================================================


# Global handler registry: maps message types to handler functions
_handlers: Dict[Type[AgentMessage], List[HandlerFunc]] = {}

# Topic subscription registry: maps topics to handler functions
_topic_handlers: Dict[str, List[Callable[[BroadcastNotification], Awaitable[None]]]] = {}


def message_handler(message_type: Type[M]) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to register a message handler.

    Handlers are called when messages of the specified type are routed
    through the MessageRouter.

    Args:
        message_type: The message class to handle

    Returns:
        Decorator function

    Example:
        @message_handler(TerminalCommand)
        async def handle_command(message: TerminalCommand) -> TerminalOutput:
            output = await execute_command(message)
            return TerminalOutput(
                sender="service",
                session_id=message.session_target.session_id,
                output=output
            )
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        if message_type not in _handlers:
            _handlers[message_type] = []
        _handlers[message_type].append(func)
        return func
    return decorator


def topic_handler(topic: str) -> Callable:
    """Decorator to register a topic subscription handler.

    Handlers are called when BroadcastNotification messages with
    matching topics are published.

    Args:
        topic: The topic to subscribe to

    Returns:
        Decorator function

    Example:
        @topic_handler("agent.status")
        async def on_status_update(notification: BroadcastNotification):
            print(f"Agent {notification.sender} status: {notification.payload}")
    """
    def decorator(func: Callable[[BroadcastNotification], Awaitable[None]]):
        if topic not in _topic_handlers:
            _topic_handlers[topic] = []
        _topic_handlers[topic].append(func)
        return func
    return decorator


def get_handlers(message_type: Type[M]) -> List[HandlerFunc]:
    """Get all registered handlers for a message type."""
    return _handlers.get(message_type, [])


def get_topic_handlers(topic: str) -> List[Callable[[BroadcastNotification], Awaitable[None]]]:
    """Get all registered handlers for a topic."""
    return _topic_handlers.get(topic, [])


def clear_handlers() -> None:
    """Clear all registered handlers. Useful for testing."""
    _handlers.clear()
    _topic_handlers.clear()


# ============================================================================
# MESSAGE ROUTER
# ============================================================================


class MessageRouter:
    """Routes messages to registered handlers.

    The router is the central hub for message-based communication.
    It supports:
    - Request/response patterns (send)
    - Pub/sub patterns (publish)
    - Message deduplication
    - Correlation ID tracking

    Example:
        router = MessageRouter()

        # Register a handler
        @message_handler(TerminalCommand)
        async def handle_cmd(msg: TerminalCommand) -> TerminalOutput:
            return TerminalOutput(...)

        # Send a request
        response = await router.send(TerminalCommand(...))

        # Publish a notification
        await router.publish("status.update", {"agent": "claude-1", "status": "idle"})
    """

    def __init__(self, deduplicate: bool = True, max_history: int = 1000):
        """Initialize the message router.

        Args:
            deduplicate: Enable message deduplication
            max_history: Maximum messages to track for deduplication
        """
        self._deduplicate = deduplicate
        self._message_history: Set[str] = set()
        self._max_history = max_history
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def send(
        self,
        message: M,
        timeout: Optional[float] = None
    ) -> Optional[AgentMessage]:
        """Send a message and optionally wait for response.

        Args:
            message: The message to send
            timeout: Optional timeout for waiting on response

        Returns:
            Response message if a handler returns one, None otherwise

        Raises:
            ValueError: If no handlers are registered for the message type
            TimeoutError: If timeout is exceeded waiting for response
        """
        # Check for deduplication
        if self._deduplicate:
            content_hash = message.content_hash()
            if content_hash in self._message_history:
                return None  # Duplicate, skip
            self._message_history.add(content_hash)

            # Limit history size
            if len(self._message_history) > self._max_history:
                # Remove oldest entries (approximately)
                excess = len(self._message_history) - self._max_history
                for _ in range(excess):
                    self._message_history.pop()

        # Get handlers for this message type
        handlers = get_handlers(type(message))

        if not handlers:
            # Check parent types
            for msg_type in type(message).__mro__:
                if msg_type in _handlers:
                    handlers = _handlers[msg_type]
                    break

        if not handlers:
            raise ValueError(f"No handlers registered for {type(message).__name__}")

        # Call handlers and collect responses
        responses = []
        for handler in handlers:
            try:
                response = await handler(message)
                if response is not None:
                    # Set correlation ID if not already set
                    if response.correlation_id is None:
                        response.correlation_id = message.message_id
                    responses.append(response)
            except Exception as e:
                # Return error message on handler failure
                error_response = ErrorMessage(
                    sender="router",
                    error_code="HANDLER_ERROR",
                    error_message=str(e),
                    original_message_id=message.message_id,
                    correlation_id=message.message_id,
                )
                responses.append(error_response)

        # Return first response (or None if no responses)
        return responses[0] if responses else None

    async def send_multi(
        self,
        message: M,
        timeout: Optional[float] = None
    ) -> List[AgentMessage]:
        """Send a message and collect all handler responses.

        Unlike send(), this returns responses from ALL handlers.

        Args:
            message: The message to send
            timeout: Optional timeout

        Returns:
            List of all responses from handlers
        """
        handlers = get_handlers(type(message))

        if not handlers:
            return []

        responses = []
        for handler in handlers:
            try:
                response = await handler(message)
                if response is not None:
                    if response.correlation_id is None:
                        response.correlation_id = message.message_id
                    responses.append(response)
            except Exception as e:
                responses.append(ErrorMessage(
                    sender="router",
                    error_code="HANDLER_ERROR",
                    error_message=str(e),
                    original_message_id=message.message_id,
                ))

        return responses

    async def publish(
        self,
        topic: str,
        payload: Any,
        sender: str = "router",
        target_teams: Optional[List[str]] = None,
        target_agents: Optional[List[str]] = None,
    ) -> int:
        """Publish a notification to topic subscribers.

        This is fire-and-forget - notifications don't return responses.

        Args:
            topic: The topic/channel name
            payload: Notification payload (must be JSON-serializable)
            sender: Name of the sender
            target_teams: Optional specific teams to notify
            target_agents: Optional specific agents to notify

        Returns:
            Number of handlers that received the notification
        """
        notification = BroadcastNotification(
            sender=sender,
            topic=topic,
            payload=payload,
            target_teams=target_teams or [],
            target_agents=target_agents or [],
        )

        handlers = get_topic_handlers(topic)
        delivered = 0

        for handler in handlers:
            try:
                await handler(notification)
                delivered += 1
            except Exception:
                # Log but don't fail on notification errors
                pass

        return delivered

    async def broadcast(
        self,
        notification: BroadcastNotification
    ) -> int:
        """Broadcast a pre-constructed notification.

        Args:
            notification: The notification to broadcast

        Returns:
            Number of handlers that received the notification
        """
        handlers = get_topic_handlers(notification.topic)
        delivered = 0

        for handler in handlers:
            try:
                await handler(notification)
                delivered += 1
            except Exception:
                pass

        return delivered

    def register_handler(
        self,
        message_type: Type[M],
        handler: HandlerFunc
    ) -> None:
        """Programmatically register a message handler.

        Alternative to using the @message_handler decorator.

        Args:
            message_type: The message class to handle
            handler: Async handler function
        """
        if message_type not in _handlers:
            _handlers[message_type] = []
        _handlers[message_type].append(handler)

    def register_topic_handler(
        self,
        topic: str,
        handler: Callable[[BroadcastNotification], Awaitable[None]]
    ) -> None:
        """Programmatically register a topic handler.

        Alternative to using the @topic_handler decorator.

        Args:
            topic: Topic to subscribe to
            handler: Async handler function
        """
        if topic not in _topic_handlers:
            _topic_handlers[topic] = []
        _topic_handlers[topic].append(handler)

    def has_handler(self, message_type: Type[M]) -> bool:
        """Check if handlers are registered for a message type."""
        return message_type in _handlers and len(_handlers[message_type]) > 0


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def create_terminal_command(
    sender: str,
    session_id: Optional[str] = None,
    agent: Optional[str] = None,
    team: Optional[str] = None,
    command: str = "",
    timeout: int = 30,
    wait: bool = True,
) -> TerminalCommand:
    """Create a TerminalCommand with common defaults.

    Args:
        sender: Name of the sending agent
        session_id: Direct session ID (optional)
        agent: Agent name to target (optional)
        team: Team name to target (optional)
        command: The command to execute
        timeout: Command timeout in seconds
        wait: Whether to wait for completion

    Returns:
        Configured TerminalCommand message
    """
    target = SessionTarget(
        session_id=session_id,
        agent=agent,
        team=team,
    )
    return TerminalCommand(
        sender=sender,
        session_target=target,
        command=command,
        timeout=timeout,
        wait_for_completion=wait,
    )


def create_broadcast(
    sender: str,
    topic: str,
    payload: Any,
    teams: Optional[List[str]] = None,
    agents: Optional[List[str]] = None,
) -> BroadcastNotification:
    """Create a broadcast notification with common defaults.

    Args:
        sender: Name of the sending agent
        topic: Notification topic
        payload: Notification payload
        teams: Optional target teams
        agents: Optional target agents

    Returns:
        Configured BroadcastNotification message
    """
    return BroadcastNotification(
        sender=sender,
        topic=topic,
        payload=payload,
        target_teams=teams or [],
        target_agents=agents or [],
    )


# ============================================================================
# MESSAGE TYPE REGISTRY (for serialization/deserialization)
# ============================================================================


# Registry of all message types for dynamic deserialization
MESSAGE_TYPES: Dict[str, Type[AgentMessage]] = {
    "AgentMessage": AgentMessage,
    "TerminalCommand": TerminalCommand,
    "TerminalOutput": TerminalOutput,
    "TerminalReadRequest": TerminalReadRequest,
    "TerminalReadResponse": TerminalReadResponse,
    "ControlCharacterMessage": ControlCharacterMessage,
    "SpecialKeyMessage": SpecialKeyMessage,
    "SessionStatusRequest": SessionStatusRequest,
    "SessionStatusResponse": SessionStatusResponse,
    "SessionListRequest": SessionListRequest,
    "SessionListResponse": SessionListResponse,
    "FocusSessionMessage": FocusSessionMessage,
    "BroadcastNotification": BroadcastNotification,
    "AgentTaskRequest": AgentTaskRequest,
    "AgentTaskResponse": AgentTaskResponse,
    "WaitForAgentMessage": WaitForAgentMessage,
    "WaitForAgentResponse": WaitForAgentResponse,
    "ErrorMessage": ErrorMessage,
}


def deserialize_message(data: Dict[str, Any]) -> AgentMessage:
    """Deserialize a message from JSON data.

    The data must include a '_type' field indicating the message class name.

    Args:
        data: JSON data with '_type' field

    Returns:
        Deserialized message instance

    Raises:
        ValueError: If message type is unknown
    """
    type_name = data.pop("_type", None)
    if type_name is None:
        raise ValueError("Message data must include '_type' field")

    message_class = MESSAGE_TYPES.get(type_name)
    if message_class is None:
        raise ValueError(f"Unknown message type: {type_name}")

    return message_class(**data)


def serialize_message(message: AgentMessage) -> Dict[str, Any]:
    """Serialize a message to JSON-compatible dict.

    Includes '_type' field for deserialization.

    Args:
        message: Message to serialize

    Returns:
        JSON-compatible dictionary
    """
    data = message.model_dump(mode="json")
    data["_type"] = type(message).__name__
    return data
