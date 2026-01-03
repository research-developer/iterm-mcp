"""Core functionality for iTerm2 integration.

Uses lazy imports to avoid loading iterm2 when only using agents/models.
"""

from typing import TYPE_CHECKING

# Always import these (no external deps)
from .agents import (
    Agent,
    Team,
    AgentRegistry,
    SendTarget,
    CascadingMessage,
    MessageRecord
)
from .tags import SessionTagLockManager, FocusCooldownManager
from .profiles import (
    ProfileManager,
    TeamProfile,
    TeamProfileColor,
    ColorDistributor,
    get_profile_manager,
    MCP_AGENT_PROFILE_NAME,
    MCP_AGENT_PROFILE_GUID,
)
from .feedback import (
    # Enums
    FeedbackCategory,
    FeedbackStatus,
    FeedbackTriggerType,
    # Models
    FeedbackContext,
    FeedbackEntry,
    FeedbackConfig,
    ErrorThresholdConfig,
    PeriodicConfig,
    PatternConfig,
    GitHubConfig,
    # Core classes
    FeedbackHookManager,
    FeedbackCollector,
    FeedbackRegistry,
    FeedbackForker,
    GitHubIntegration,
)
from .models import (
    # Role-based session specialization
    SessionRole,
    RoleConfig,
    DEFAULT_ROLE_CONFIGS,
    # Session and message models
    SessionTarget,
    SessionMessage,
    WriteToSessionsRequest,
    ReadTarget,
    ReadSessionsRequest,
    SessionOutput,
    ReadSessionsResponse,
    SessionConfig,
    CreateSessionsRequest,
    CreatedSession,
    CreateSessionsResponse,
    WriteResult,
    WriteToSessionsResponse,
    CascadeMessageRequest,
    CascadeResult,
    CascadeMessageResponse,
    RegisterAgentRequest,
    CreateTeamRequest,
    SetActiveSessionRequest,
    PlaybookCommand,
    Playbook,
    PlaybookCommandResult,
    OrchestrateRequest,
    OrchestrateResponse,
    # Manager models
    CreateManagerRequest,
    CreateManagerResponse,
    DelegateTaskRequest,
    TaskResultResponse,
    TaskStepSpec,
    TaskPlanSpec,
    ExecutePlanRequest,
    PlanResultResponse,
    AddWorkerRequest,
    RemoveWorkerRequest,
    ManagerInfoResponse,
)
from .manager import (
    SessionRole,
    TaskStatus,
    TaskResult,
    TaskStep,
    TaskPlan,
    PlanResult,
    DelegationStrategy,
    ManagerAgent,
    ManagerRegistry,
)
from .roles import (
    RoleManager,
    SessionRoleAssignment,
    RolePermissionError,
)

# Message-based communication
from .messaging import (
    # Base types
    AgentMessage,
    MessagePriority,
    # Terminal messages
    TerminalCommand,
    TerminalOutput,
    TerminalReadRequest,
    TerminalReadResponse,
    ControlCharacterMessage,
    SpecialKeyMessage,
    # Session messages
    SessionStatusRequest,
    SessionStatusResponse,
    SessionListRequest,
    SessionListResponse,
    FocusSessionMessage,
    # Agent orchestration messages
    BroadcastNotification,
    AgentTaskRequest,
    AgentTaskResponse,
    WaitForAgentMessage,
    WaitForAgentResponse,
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

# Type checking imports for IDE support
if TYPE_CHECKING:
    from .session import (
        ItermSession,
        ExpectResult,
        ExpectTimeout,
        ExpectError,
        ExpectTimeoutError,
    )
    from .terminal import ItermTerminal
    from .layouts import LayoutManager, LayoutType

# Lazy loading for iterm2-dependent modules
_lazy_modules = {
    'ItermSession': '.session',
    'ExpectResult': '.session',
    'ExpectTimeout': '.session',
    'ExpectError': '.session',
    'ExpectTimeoutError': '.session',
    'ItermTerminal': '.terminal',
    'LayoutManager': '.layouts',
    'LayoutType': '.layouts',
}

_loaded = {}


def __getattr__(name: str):
    """Lazy load iterm2-dependent classes on first access."""
    if name in _lazy_modules:
        if name not in _loaded:
            import importlib
            module_name = _lazy_modules[name]
            module = importlib.import_module(module_name, package=__name__)
            _loaded[name] = getattr(module, name)
        return _loaded[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core classes (lazy loaded)
    'ItermSession',
    'ItermTerminal',
    'LayoutManager',
    'LayoutType',
    # Expect-style pattern matching
    'ExpectResult',
    'ExpectTimeout',
    'ExpectError',
    'ExpectTimeoutError',
    # Agent management
    'Agent',
    'Team',
    'AgentRegistry',
    'SendTarget',
    'CascadingMessage',
    'MessageRecord',
    'SessionTagLockManager',
    'FocusCooldownManager',
    # Role-based session specialization
    'SessionRole',
    'RoleConfig',
    'DEFAULT_ROLE_CONFIGS',
    'RoleManager',
    'SessionRoleAssignment',
    'RolePermissionError',
    # Profile management
    'ProfileManager',
    'TeamProfile',
    'TeamProfileColor',
    'ColorDistributor',
    'get_profile_manager',
    'MCP_AGENT_PROFILE_NAME',
    'MCP_AGENT_PROFILE_GUID',
    # Feedback system
    'FeedbackCategory',
    'FeedbackStatus',
    'FeedbackTriggerType',
    'FeedbackContext',
    'FeedbackEntry',
    'FeedbackConfig',
    'ErrorThresholdConfig',
    'PeriodicConfig',
    'PatternConfig',
    'GitHubConfig',
    'FeedbackHookManager',
    'FeedbackCollector',
    'FeedbackRegistry',
    'FeedbackForker',
    'GitHubIntegration',
    # Manager agent classes
    'SessionRole',
    'TaskStatus',
    'TaskResult',
    'TaskStep',
    'TaskPlan',
    'PlanResult',
    'DelegationStrategy',
    'ManagerAgent',
    'ManagerRegistry',
    # API models
    'SessionTarget',
    'SessionMessage',
    'WriteToSessionsRequest',
    'ReadTarget',
    'ReadSessionsRequest',
    'SessionOutput',
    'ReadSessionsResponse',
    'SessionConfig',
    'CreateSessionsRequest',
    'CreatedSession',
    'CreateSessionsResponse',
    'WriteResult',
    'WriteToSessionsResponse',
    'CascadeMessageRequest',
    'CascadeResult',
    'CascadeMessageResponse',
    'RegisterAgentRequest',
    'CreateTeamRequest',
    'SetActiveSessionRequest',
    'PlaybookCommand',
    'Playbook',
    'PlaybookCommandResult',
    'OrchestrateRequest',
    'OrchestrateResponse',
    # Manager API models
    'CreateManagerRequest',
    'CreateManagerResponse',
    'DelegateTaskRequest',
    'TaskResultResponse',
    'TaskStepSpec',
    'TaskPlanSpec',
    'ExecutePlanRequest',
    'PlanResultResponse',
    'AddWorkerRequest',
    'RemoveWorkerRequest',
    'ManagerInfoResponse',
    # Message-based communication
    'AgentMessage',
    'MessagePriority',
    'TerminalCommand',
    'TerminalOutput',
    'TerminalReadRequest',
    'TerminalReadResponse',
    'ControlCharacterMessage',
    'SpecialKeyMessage',
    'SessionStatusRequest',
    'SessionStatusResponse',
    'SessionListRequest',
    'SessionListResponse',
    'FocusSessionMessage',
    'BroadcastNotification',
    'AgentTaskRequest',
    'AgentTaskResponse',
    'WaitForAgentMessage',
    'WaitForAgentResponse',
    'ErrorMessage',
    'MessageRouter',
    'message_handler',
    'topic_handler',
    'get_handlers',
    'get_topic_handlers',
    'clear_handlers',
    'create_terminal_command',
    'create_broadcast',
    'MESSAGE_TYPES',
    'serialize_message',
    'deserialize_message',
]
