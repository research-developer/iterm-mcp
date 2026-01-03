"""Pydantic models for MCP session operations API."""

import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

# Supported AI agent CLI types
AgentType = Literal["claude", "gemini", "codex", "copilot"]


# ============================================================================
# ROLE-BASED SESSION SPECIALIZATION
# ============================================================================

class SessionRole(str, Enum):
    """Predefined roles for session specialization.

    Roles define the purpose and capabilities of a session, guiding
    what tools and commands are appropriate for that session.
    """

    DEVOPS = "devops"
    BUILDER = "builder"
    DEBUGGER = "debugger"
    RESEARCHER = "researcher"
    TESTER = "tester"
    ORCHESTRATOR = "orchestrator"
    MONITOR = "monitor"
    CUSTOM = "custom"  # For user-defined roles


class RoleConfig(BaseModel):
    """Detailed configuration for a session role.

    Defines the capabilities, restrictions, and default behavior
    for a session with a specific role.
    """

    role: SessionRole = Field(..., description="The role type")
    description: str = Field(
        default="",
        description="Human-readable description of this role's purpose"
    )
    available_tools: List[str] = Field(
        default_factory=list,
        description="List of tool names this role can use (empty = all tools)"
    )
    restricted_tools: List[str] = Field(
        default_factory=list,
        description="List of tool names this role cannot use"
    )
    default_commands: List[str] = Field(
        default_factory=list,
        description="Commands to run when session starts"
    )
    environment: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set for this role"
    )
    can_spawn_agents: bool = Field(
        default=False,
        description="Whether this role can create new agent sessions"
    )
    can_modify_roles: bool = Field(
        default=False,
        description="Whether this role can modify other sessions' roles"
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Role priority (1=highest, 5=lowest) for resource allocation"
    )


# Default role configurations for common roles
DEFAULT_ROLE_CONFIGS: Dict[SessionRole, RoleConfig] = {
    SessionRole.DEVOPS: RoleConfig(
        role=SessionRole.DEVOPS,
        description="DevOps engineer handling infrastructure, deployments, and system operations",
        available_tools=["docker", "kubectl", "terraform", "ansible", "aws", "gcloud", "az"],
        can_spawn_agents=False,
        can_modify_roles=False,
        priority=2,
    ),
    SessionRole.BUILDER: RoleConfig(
        role=SessionRole.BUILDER,
        description="Build specialist handling compilation, packaging, and artifacts",
        available_tools=["npm", "yarn", "pip", "cargo", "go", "make", "docker", "git"],
        default_commands=["cd /project"],
        can_spawn_agents=False,
        priority=3,
    ),
    SessionRole.DEBUGGER: RoleConfig(
        role=SessionRole.DEBUGGER,
        description="Debug specialist for investigating issues and analyzing logs",
        available_tools=["gdb", "lldb", "strace", "dtrace", "tail", "grep", "awk", "jq"],
        can_spawn_agents=False,
        priority=2,
    ),
    SessionRole.RESEARCHER: RoleConfig(
        role=SessionRole.RESEARCHER,
        description="Research assistant for gathering information and analysis",
        available_tools=["curl", "wget", "git", "grep", "find", "cat", "less"],
        restricted_tools=["rm", "docker", "kubectl"],
        can_spawn_agents=False,
        priority=4,
    ),
    SessionRole.TESTER: RoleConfig(
        role=SessionRole.TESTER,
        description="Testing specialist for running tests and quality assurance",
        available_tools=["pytest", "jest", "mocha", "cargo", "go", "npm", "make"],
        can_spawn_agents=False,
        priority=3,
    ),
    SessionRole.ORCHESTRATOR: RoleConfig(
        role=SessionRole.ORCHESTRATOR,
        description="Orchestration coordinator managing other agents and workflows",
        available_tools=[],  # All tools available
        can_spawn_agents=True,
        can_modify_roles=True,
        priority=1,
    ),
    SessionRole.MONITOR: RoleConfig(
        role=SessionRole.MONITOR,
        description="Monitoring agent for observing and reporting on system state",
        available_tools=["tail", "grep", "ps", "top", "htop", "docker", "kubectl"],
        restricted_tools=["rm", "kill", "pkill"],
        can_spawn_agents=False,
        priority=4,
    ),
}

# Agent CLI launch commands
AGENT_CLI_COMMANDS: Dict[str, str] = {
    "claude": "claude",
    "gemini": "gemini",
    "codex": "codex",
    "copilot": "gh copilot",
}


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
    requesting_agent: Optional[str] = Field(
        default=None,
        description="Agent initiating the write (used for lock enforcement)"
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
    agent_type: Optional[AgentType] = Field(
        default=None,
        description="AI agent CLI to launch: claude, gemini, codex, or copilot"
    )
    team: Optional[str] = Field(default=None, description="Team to assign agent to")
    command: Optional[str] = Field(default=None, description="Initial command to run")
    max_lines: Optional[int] = Field(default=None, description="Max output lines")
    monitor: bool = Field(default=False, description="Start monitoring")
    role: Optional[SessionRole] = Field(
        default=None,
        description="Role for this session (e.g., BUILDER, DEBUGGER, DEVOPS)"
    )
    role_config: Optional[RoleConfig] = Field(
        default=None,
        description="Custom role configuration (overrides default for the role)"
    )


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


# ============================================================================
# NOTIFICATION MODELS
# ============================================================================

NotificationLevel = Literal["info", "warning", "error", "success", "blocked"]


class AgentNotification(BaseModel):
    """A notification from an agent about its status."""

    agent: str = Field(..., description="Agent name")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the notification was created")
    level: NotificationLevel = Field(..., description="Notification severity level")
    summary: str = Field(..., max_length=100, description="One-line summary")
    context: Optional[str] = Field(default=None, description="Additional context for follow-up")
    action_hint: Optional[str] = Field(default=None, description="Suggested next action")


class GetNotificationsRequest(BaseModel):
    """Request to get recent notifications."""

    limit: int = Field(default=10, ge=1, le=100, description="Max notifications to return")
    level: Optional[NotificationLevel] = Field(default=None, description="Filter by level")
    agent: Optional[str] = Field(default=None, description="Filter by agent")
    since: Optional[datetime] = Field(default=None, description="Only notifications after this time")


class GetNotificationsResponse(BaseModel):
    """Response containing notifications."""

    notifications: List[AgentNotification] = Field(..., description="Recent notifications")
    total_count: int = Field(..., description="Total matching notifications")
    has_more: bool = Field(default=False, description="More notifications available")


# ============================================================================
# WAIT FOR AGENT MODELS
# ============================================================================

AgentStatus = Literal["idle", "running", "blocked", "error", "unknown"]


class WaitForAgentRequest(BaseModel):
    """Request to wait for an agent to complete."""

    agent: str = Field(..., description="Agent name to wait for")
    wait_up_to: int = Field(default=30, ge=1, le=600, description="Max seconds to wait")
    return_output: bool = Field(default=True, description="Include recent output on timeout")
    summary_on_timeout: bool = Field(default=True, description="Generate progress summary if timed out")


class WaitResult(BaseModel):
    """Result of waiting for an agent."""

    agent: str = Field(..., description="Agent name")
    completed: bool = Field(..., description="True if agent finished/became idle")
    timed_out: bool = Field(..., description="True if wait_up_to was exceeded")
    elapsed_seconds: float = Field(..., description="How long we waited")
    status: AgentStatus = Field(..., description="Current agent status")
    output: Optional[str] = Field(default=None, description="Recent output if requested")
    summary: Optional[str] = Field(default=None, description="Progress summary if timed out")
    can_continue_waiting: bool = Field(
        default=True,
        description="Hint: is it worth waiting more?"
    )


# ============================================================================
# MANAGER AGENT MODELS (MCP API)
# ============================================================================

SessionRoleType = Literal[
    "builder", "tester", "devops", "reviewer",
    "researcher", "writer", "analyst", "coordinator", "general"
]

DelegationStrategyType = Literal[
    "round_robin", "role_based", "least_busy", "random", "priority"
]

TaskStatusType = Literal[
    "pending", "in_progress", "completed", "failed", "skipped", "validation_failed"
]


class CreateManagerRequest(BaseModel):
    """Request to create a manager agent."""

    name: str = Field(..., description="Unique name for the manager")
    workers: List[str] = Field(default_factory=list, description="Worker agent names")
    delegation_strategy: DelegationStrategyType = Field(
        default="role_based",
        description="Strategy for selecting workers"
    )
    worker_roles: Dict[str, SessionRoleType] = Field(
        default_factory=dict,
        description="Mapping of worker names to their roles"
    )
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class CreateManagerResponse(BaseModel):
    """Response from creating a manager."""

    name: str = Field(..., description="Manager name")
    workers: List[str] = Field(..., description="Registered workers")
    delegation_strategy: str = Field(..., description="Delegation strategy")
    created: bool = Field(default=True, description="Whether creation succeeded")


class DelegateTaskRequest(BaseModel):
    """Request to delegate a task through a manager."""

    manager: str = Field(..., description="Manager name")
    task: str = Field(..., description="Task description/command to execute")
    role: Optional[SessionRoleType] = Field(default=None, description="Required worker role")
    validation: Optional[str] = Field(
        default=None,
        description="Validation: regex pattern or 'success'"
    )
    timeout_seconds: Optional[int] = Field(default=None, description="Execution timeout")
    retry_count: int = Field(default=0, ge=0, le=5, description="Retries on failure")


class TaskResultResponse(BaseModel):
    """Response containing task execution result."""

    task_id: str = Field(..., description="Unique task identifier")
    task: str = Field(..., description="Task that was executed")
    worker: str = Field(..., description="Worker that executed the task")
    status: TaskStatusType = Field(..., description="Task status")
    success: bool = Field(..., description="Whether task succeeded")
    output: Optional[str] = Field(default=None, description="Task output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration")
    validation_passed: Optional[bool] = Field(default=None, description="Validation result")
    validation_message: Optional[str] = Field(default=None, description="Validation message")


class TaskStepSpec(BaseModel):
    """Specification for a single task step in a plan."""

    id: str = Field(..., description="Unique step identifier")
    task: str = Field(..., description="Task description to execute")
    role: Optional[SessionRoleType] = Field(default=None, description="Required worker role")
    optional: bool = Field(default=False, description="Whether failure should stop plan")
    depends_on: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    validation: Optional[str] = Field(default=None, description="Validation pattern or 'success'")
    timeout_seconds: Optional[int] = Field(default=None, description="Max execution time")
    retry_count: int = Field(default=0, ge=0, le=5, description="Retries on failure")


class TaskPlanSpec(BaseModel):
    """Specification for a multi-step task plan."""

    name: str = Field(..., description="Plan name")
    description: Optional[str] = Field(default=None, description="Plan description")
    steps: List[TaskStepSpec] = Field(..., min_length=1, description="Steps to execute")
    parallel_groups: List[List[str]] = Field(
        default_factory=list,
        description="Groups of step IDs that can run in parallel"
    )
    stop_on_failure: bool = Field(default=True, description="Stop on first failure")


class ExecutePlanRequest(BaseModel):
    """Request to execute a task plan."""

    manager: str = Field(..., description="Manager name")
    plan: TaskPlanSpec = Field(..., description="Plan to execute")


class PlanResultResponse(BaseModel):
    """Response containing plan execution results."""

    plan_name: str = Field(..., description="Name of the executed plan")
    success: bool = Field(..., description="Whether plan completed successfully")
    results: List[TaskResultResponse] = Field(..., description="Results for each step")
    duration_seconds: Optional[float] = Field(default=None, description="Total duration")
    stopped_early: bool = Field(default=False, description="Whether plan stopped early")
    stop_reason: Optional[str] = Field(default=None, description="Reason for early stop")


class AddWorkerRequest(BaseModel):
    """Request to add a worker to a manager."""

    manager: str = Field(..., description="Manager name")
    worker: str = Field(..., description="Worker agent name")
    role: Optional[SessionRoleType] = Field(default=None, description="Worker role")


class RemoveWorkerRequest(BaseModel):
    """Request to remove a worker from a manager."""

    manager: str = Field(..., description="Manager name")
    worker: str = Field(..., description="Worker agent name")


class ManagerInfoResponse(BaseModel):
    """Information about a manager agent."""

    name: str = Field(..., description="Manager name")
    workers: List[str] = Field(..., description="Worker names")
    worker_roles: Dict[str, str] = Field(..., description="Worker role mappings")
    delegation_strategy: str = Field(..., description="Delegation strategy")
    created_at: str = Field(..., description="Creation timestamp")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Metadata")


# ============================================================================
# SESSION INFO MODELS (Issue #52)
# ============================================================================


class SessionInfo(BaseModel):
    """Extended session information including tags and locks."""

    session_id: str = Field(..., description="The session ID")
    name: str = Field(..., description="Session name")
    persistent_id: Optional[str] = Field(default=None, description="Persistent ID for reconnection")
    agent: Optional[str] = Field(default=None, description="Registered agent name")
    team: Optional[str] = Field(default=None, description="Primary team (first team if multiple)")
    teams: List[str] = Field(default_factory=list, description="All teams the agent belongs to")
    is_processing: bool = Field(default=False, description="Whether a command is running")

    # Tag and lock information
    tags: List[str] = Field(default_factory=list, description="Session tags")
    locked: bool = Field(default=False, description="Whether session is locked")
    locked_by: Optional[str] = Field(default=None, description="Agent holding the lock")
    locked_at: Optional[datetime] = Field(default=None, description="When the lock was acquired")
    pending_access_requests: int = Field(default=0, description="Number of pending access requests")


class ListSessionsRequest(BaseModel):
    """Request parameters for list_sessions with filtering."""

    # Filter by tags
    tag: Optional[str] = Field(default=None, description="Single tag to filter by")
    tags: Optional[List[str]] = Field(default=None, description="Multiple tags to filter by")
    match: Literal["any", "all"] = Field(
        default="any",
        description="How to match multiple tags: 'any' (OR) or 'all' (AND)"
    )

    # Filter by lock status
    locked: Optional[bool] = Field(default=None, description="Filter by lock status")
    locked_by: Optional[str] = Field(default=None, description="Filter by lock owner")

    # Output format
    format: Literal["full", "compact"] = Field(
        default="full",
        description="Output format: 'full' for JSON, 'compact' for one-line-per-session"
    )

    # Existing filter
    agents_only: bool = Field(default=False, description="Only show sessions with registered agents")


class ListSessionsResponse(BaseModel):
    """Response from list_sessions."""

    sessions: List[SessionInfo] = Field(..., description="Matching sessions")
    total_count: int = Field(..., description="Total number of matching sessions")
    filter_applied: bool = Field(default=False, description="Whether any filters were applied")
