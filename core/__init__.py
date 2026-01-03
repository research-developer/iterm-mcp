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
    # Workflow event models
    TriggerEventRequest,
    TriggerEventResponse,
    EventInfo,
    WorkflowEventInfo,
    ListWorkflowEventsResponse,
    EventHistoryEntry,
    GetEventHistoryRequest,
    GetEventHistoryResponse,
    PatternSubscriptionRequest,
    PatternSubscriptionResponse,
)
from .flows import (
    # Core classes
    Event,
    EventResult,
    EventPriority,
    EventBus,
    Flow,
    FlowManager,
    ListenerInfo,
    ListenerRegistry,
    # Decorators
    start,
    listen,
    router,
    on_output,
    # Functions
    trigger,
    trigger_and_wait,
    get_event_bus,
    get_flow_manager,
    list_workflow_events,
    get_event_history,
    # Example flow
    BuildResult,
    DeployResult,
    BuildDeployFlow,
)

# Type checking imports for IDE support
if TYPE_CHECKING:
    from .session import ItermSession
    from .terminal import ItermTerminal
    from .layouts import LayoutManager, LayoutType

# Lazy loading for iterm2-dependent modules
_lazy_modules = {
    'ItermSession': '.session',
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
    # Agent management
    'Agent',
    'Team',
    'AgentRegistry',
    'SendTarget',
    'CascadingMessage',
    'MessageRecord',
    'SessionTagLockManager',
    'FocusCooldownManager',
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
    # Workflow event models
    'TriggerEventRequest',
    'TriggerEventResponse',
    'EventInfo',
    'WorkflowEventInfo',
    'ListWorkflowEventsResponse',
    'EventHistoryEntry',
    'GetEventHistoryRequest',
    'GetEventHistoryResponse',
    'PatternSubscriptionRequest',
    'PatternSubscriptionResponse',
    # Event-driven flow control
    'Event',
    'EventResult',
    'EventPriority',
    'EventBus',
    'Flow',
    'FlowManager',
    'ListenerInfo',
    'ListenerRegistry',
    'start',
    'listen',
    'router',
    'on_output',
    'trigger',
    'trigger_and_wait',
    'get_event_bus',
    'get_flow_manager',
    'list_workflow_events',
    'get_event_history',
    'BuildResult',
    'DeployResult',
    'BuildDeployFlow',
]
