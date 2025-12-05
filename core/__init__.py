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
