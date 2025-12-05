"""Core functionality for iTerm2 integration."""

from .session import ItermSession
from .terminal import ItermTerminal
from .layouts import LayoutManager, LayoutType
from .agents import (
    Agent,
    Team,
    AgentRegistry,
    SendTarget,
    CascadingMessage,
    MessageRecord
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
    CascadeMessageRequest,
    CascadeResult,
    CascadeMessageResponse,
    RegisterAgentRequest,
    CreateTeamRequest,
    SetActiveSessionRequest,
)

__all__ = [
    # Core classes
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
    'CascadeMessageRequest',
    'CascadeResult',
    'CascadeMessageResponse',
    'RegisterAgentRequest',
    'CreateTeamRequest',
    'SetActiveSessionRequest',
]