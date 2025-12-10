"""Pydantic models for MCP session operations API."""

import re
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class SessionTarget(BaseModel):
    """Identifies a session target for operations."""

    # Multiple ways to identify a session
    session_id: Optional[str] = Field(default=None, description="Direct session ID")
    name: Optional[str] = Field(default=None, description="Session name")
    agent: Optional[str] = Field(default=None, description="Agent name")
    team: Optional[str] = Field(default=None, description="Team name (targets all members)")

    @field_validator('session_id', 'name', 'agent', 'team', mode='before')
    @classmethod
    def at_least_one_identifier(cls, v, info):
        """Ensure at least one identifier is provided (validated at model level)."""
        return v

    @model_validator(mode='after')
    def check_at_least_one(self):
        """Validate that at least one identifier is provided."""
        if not any([self.session_id, self.name, self.agent, self.team]):
            raise ValueError("At least one identifier (session_id, name, agent, or team) must be provided")
        return self


class SessionMessage(BaseModel):
    """A message to send to one or more sessions."""

    content: str = Field(..., description="The text/command to send")
    targets: List[SessionTarget] = Field(
        default_factory=list,
        description="Target sessions. Empty = use active session"
    )
    condition: Optional[str] = Field(
        default=None,
        description="Regex pattern - only send if session output matches"
    )
    execute: bool = Field(
        default=True,
        description="Whether to press Enter after sending"
    )
    use_encoding: Union[bool, str] = Field(
        default=False,
        description="Base64 encoding: False (default, direct send), 'auto' (smart), True (always)"
    )

    @field_validator('condition', mode='before')
    @classmethod
    def validate_regex(cls, v):
        """Validate that condition is a valid regex pattern."""
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v


class WriteToSessionsRequest(BaseModel):
    """Request to write messages to sessions."""

    messages: List[SessionMessage] = Field(
        ...,
        description="List of messages to send"
    )
    parallel: bool = Field(
        default=True,
        description="Execute sends in parallel (True) or sequentially (False)"
    )
    skip_duplicates: bool = Field(
        default=True,
        description="Skip sending if message was already sent to target"
    )


class ReadTarget(BaseModel):
    """Target specification for reading session output."""

    session_id: Optional[str] = Field(default=None, description="Direct session ID")
    name: Optional[str] = Field(default=None, description="Session name")
    agent: Optional[str] = Field(default=None, description="Agent name")
    team: Optional[str] = Field(default=None, description="Team name (reads all members)")
    max_lines: Optional[int] = Field(default=None, description="Override default max lines")


class ReadSessionsRequest(BaseModel):
    """Request to read output from sessions."""

    targets: List[ReadTarget] = Field(
        default_factory=list,
        description="Target sessions. Empty = use active session"
    )
    parallel: bool = Field(
        default=True,
        description="Read sessions in parallel"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern to filter output lines"
    )

    @field_validator('filter_pattern', mode='before')
    @classmethod
    def validate_filter_regex(cls, v):
        """Validate that filter_pattern is a valid regex."""
        if v is not None:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid filter regex pattern: {e}")
        return v


class SessionOutput(BaseModel):
    """Output from a single session read."""

    session_id: str = Field(..., description="The session ID")
    name: str = Field(..., description="Session name")
    agent: Optional[str] = Field(default=None, description="Agent name if registered")
    content: str = Field(..., description="Terminal output content")
    line_count: int = Field(..., description="Number of lines returned")
    truncated: bool = Field(default=False, description="Whether output was truncated")


class ReadSessionsResponse(BaseModel):
    """Response from reading sessions."""

    outputs: List[SessionOutput] = Field(..., description="Output from each session")
    total_sessions: int = Field(..., description="Number of sessions read")


class SessionConfig(BaseModel):
    """Configuration for creating a new session."""

    name: str = Field(..., description="Name for the session")
    agent: Optional[str] = Field(default=None, description="Agent name to register")
    team: Optional[str] = Field(default=None, description="Team to assign agent to")
    command: Optional[str] = Field(default=None, description="Initial command to run")
    max_lines: Optional[int] = Field(default=None, description="Max output lines")
    monitor: bool = Field(default=False, description="Start monitoring")


class CreateSessionsRequest(BaseModel):
    """Request to create multiple sessions."""

    sessions: List[SessionConfig] = Field(
        ...,
        description="Session configurations"
    )
    layout: str = Field(
        default="SINGLE",
        description="Layout type: SINGLE, HORIZONTAL_SPLIT, VERTICAL_SPLIT, QUAD, etc."
    )
    window_id: Optional[str] = Field(
        default=None,
        description="Create in existing window (None = new window)"
    )


class CreatedSession(BaseModel):
    """Information about a created session."""

    session_id: str = Field(..., description="The session ID")
    name: str = Field(..., description="Session name")
    agent: Optional[str] = Field(default=None, description="Registered agent name")
    persistent_id: str = Field(..., description="Persistent ID for reconnection")


class CreateSessionsResponse(BaseModel):
    """Response from creating sessions."""

    sessions: List[CreatedSession] = Field(..., description="Created sessions")
    window_id: str = Field(default="", description="Window ID containing sessions")


class WriteResult(BaseModel):
    """Result of writing to a single session."""

    session_id: str = Field(..., description="The session ID")
    session_name: Optional[str] = Field(default=None, description="The session name")
    success: bool = Field(default=False, description="Whether the write succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    skipped: bool = Field(default=False, description="Whether the write was skipped")
    skipped_reason: Optional[str] = Field(default=None, description="Reason for skipping")


class WriteToSessionsResponse(BaseModel):
    """Response from writing to sessions."""

    results: List[WriteResult] = Field(..., description="Results for each target session")
    sent_count: int = Field(..., description="Number of successful sends")
    skipped_count: int = Field(..., description="Number of skipped sends")
    error_count: int = Field(..., description="Number of errors")


class CascadeMessageRequest(BaseModel):
    """Request to send cascading messages to agents/teams."""

    broadcast: Optional[str] = Field(
        default=None,
        description="Message sent to ALL agents"
    )
    teams: Dict[str, str] = Field(
        default_factory=dict,
        description="Team-specific messages: {team_name: message}"
    )
    agents: Dict[str, str] = Field(
        default_factory=dict,
        description="Agent-specific messages: {agent_name: message}"
    )
    skip_duplicates: bool = Field(
        default=True,
        description="Skip if message already sent to target"
    )
    execute: bool = Field(
        default=True,
        description="Press Enter after sending"
    )


class CascadeResult(BaseModel):
    """Result of a cascade message delivery."""

    agent: str = Field(..., description="Agent name")
    session_id: str = Field(..., description="Session ID")
    message_type: str = Field(..., description="broadcast, team, or agent")
    delivered: bool = Field(..., description="Whether message was delivered")
    skipped_reason: Optional[str] = Field(
        default=None,
        description="Reason if skipped (e.g., 'duplicate', 'condition_not_met')"
    )


class CascadeMessageResponse(BaseModel):
    """Response from cascade message operation."""

    results: List[CascadeResult] = Field(..., description="Delivery results")
    delivered_count: int = Field(..., description="Number of messages delivered")
    skipped_count: int = Field(..., description="Number of messages skipped")


class RegisterAgentRequest(BaseModel):
    """Request to register an agent."""

    name: str = Field(..., description="Unique agent name")
    session_id: str = Field(..., description="iTerm session ID")
    teams: List[str] = Field(default_factory=list, description="Teams to join")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Optional metadata")


class CreateTeamRequest(BaseModel):
    """Request to create a team."""

    name: str = Field(..., description="Unique team name")
    description: str = Field(default="", description="Team description")
    parent_team: Optional[str] = Field(default=None, description="Parent team name")


class SetActiveSessionRequest(BaseModel):
    """Request to set the active session."""

    session_id: Optional[str] = Field(default=None, description="Session ID")
    agent: Optional[str] = Field(default=None, description="Agent name")
    name: Optional[str] = Field(default=None, description="Session name")
    focus: bool = Field(default=False, description="Also bring the session to the foreground in iTerm")


class PlaybookCommand(BaseModel):
    """A named block of commands in a playbook."""

    name: str = Field(default="commands", description="Label for the command block")
    messages: List[SessionMessage] = Field(..., description="Messages to send")
    parallel: bool = Field(default=True, description="Send messages in parallel")
    skip_duplicates: bool = Field(default=True, description="Skip duplicate agent deliveries")


class Playbook(BaseModel):
    """High-level orchestration plan."""

    layout: Optional[CreateSessionsRequest] = Field(default=None, description="Optional layout/session creation")
    commands: List[PlaybookCommand] = Field(default_factory=list, description="Ordered command blocks")
    cascade: Optional[CascadeMessageRequest] = Field(default=None, description="Optional cascade after commands")
    reads: Optional[ReadSessionsRequest] = Field(default=None, description="Optional final read operations")


class PlaybookCommandResult(BaseModel):
    """Result of running a playbook command block."""

    name: str = Field(..., description="Command block label")
    write_result: WriteToSessionsResponse = Field(..., description="Write results for the block")


class OrchestrateRequest(BaseModel):
    """Request to orchestrate a playbook."""

    playbook: Playbook = Field(..., description="Playbook to execute")


class OrchestrateResponse(BaseModel):
    """Response from orchestrating a playbook."""

    layout: Optional[CreateSessionsResponse] = Field(default=None, description="Layout creation result")
    commands: List[PlaybookCommandResult] = Field(default_factory=list, description="Command block results")
    cascade: Optional[CascadeMessageResponse] = Field(default=None, description="Cascade delivery result")
    reads: Optional[ReadSessionsResponse] = Field(default=None, description="Readback results")


# ============================================================================
# SESSION MODIFICATION MODELS
# ============================================================================

class ColorSpec(BaseModel):
    """RGB color specification."""

    red: int = Field(..., ge=0, le=255, description="Red component (0-255)")
    green: int = Field(..., ge=0, le=255, description="Green component (0-255)")
    blue: int = Field(..., ge=0, le=255, description="Blue component (0-255)")
    alpha: int = Field(default=255, ge=0, le=255, description="Alpha component (0-255)")


class SessionModification(BaseModel):
    """Modification settings for a session (appearance, focus, active state)."""

    # Target session (at least one required)
    session_id: Optional[str] = Field(default=None, description="Direct session ID")
    name: Optional[str] = Field(default=None, description="Session name")
    agent: Optional[str] = Field(default=None, description="Agent name")

    # Session state modifications
    set_active: bool = Field(default=False, description="Set this session as the active session")
    focus: bool = Field(default=False, description="Bring this session to the foreground in iTerm")

    # Appearance settings (all optional - only set what you want to change)
    background_color: Optional[ColorSpec] = Field(default=None, description="Background color")
    tab_color: Optional[ColorSpec] = Field(default=None, description="Tab color")
    tab_color_enabled: Optional[bool] = Field(default=None, description="Enable/disable tab color")
    cursor_color: Optional[ColorSpec] = Field(default=None, description="Cursor color")
    badge: Optional[str] = Field(default=None, description="Badge text (empty string to clear)")
    reset: bool = Field(default=False, description="Reset all colors to profile defaults")

    @model_validator(mode='after')
    def check_at_least_one_target(self):
        """Validate that at least one session identifier is provided."""
        if not any([self.session_id, self.name, self.agent]):
            raise ValueError("At least one identifier (session_id, name, or agent) must be provided")
        return self


class ModifySessionsRequest(BaseModel):
    """Request to modify multiple sessions (appearance, focus, active state)."""

    modifications: List[SessionModification] = Field(
        ...,
        description="List of session modifications"
    )


class ModificationResult(BaseModel):
    """Result of modifying a single session."""

    session_id: str = Field(..., description="The session ID")
    session_name: Optional[str] = Field(default=None, description="The session name")
    agent: Optional[str] = Field(default=None, description="Agent name if registered")
    success: bool = Field(default=False, description="Whether the modification succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    changes: List[str] = Field(default_factory=list, description="List of changes applied")


class ModifySessionsResponse(BaseModel):
    """Response from modifying sessions."""

    results: List[ModificationResult] = Field(..., description="Results for each session")
    success_count: int = Field(..., description="Number of successful modifications")
    error_count: int = Field(..., description="Number of errors")
