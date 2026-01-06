# iTerm2 API Enhancement Roadmap

> **Comprehensive analysis of iTerm2 Python API features to enhance iterm-mcp multi-agent orchestration**

## Executive Summary

This document synthesizes findings from comprehensive analysis of the iTerm2 Python API documentation (5,204 lines) to identify features that can enhance the iterm-mcp multi-agent orchestration system. We identified **40+ enhancement opportunities** across 6 major categories, prioritized by impact and implementation complexity.

---

## Priority Matrix Overview

| Priority | Category | Impact | Complexity | Timeline |
|----------|----------|--------|------------|----------|
| **P0** | Shell Integration | Critical | Medium | Phase 1 |
| **P0** | Broadcast Mode | Critical | Low | Phase 1 |
| **P0** | Window Arrangements | High | Medium | Phase 1 |
| **P1** | Session Variables | High | Low | Phase 1 |
| **P1** | Triggers & Automation | High | Medium | Phase 2 |
| **P1** | Visual Status System | High | Low | Phase 2 |
| **P2** | Hotkey Windows | Medium | Low | Phase 3 |
| **P2** | Dynamic Profiles | Medium | Medium | Phase 3 |
| **P3** | Coprocesses | Medium | High | Future |
| **P3** | Tmux Integration | Medium | High | Future |

---

## Phase 1: Critical Infrastructure (Immediate)

### 1.1 Shell Integration - Command Tracking

**Source**: Shell Integration/FinalTerm (lines 4952-5204)

**What it enables**: Precise command boundaries, exit status capture, prompt detection

**Current Gap**: Polling-based monitoring with unreliable pattern matching

**Implementation**:

```python
# core/shell_integration.py

from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
import asyncio
import time

@dataclass
class CommandExecution:
    """Represents a single command execution with shell integration data."""
    command: str
    start_time: float
    end_time: Optional[float] = None
    exit_status: Optional[int] = None
    output_start_line: Optional[int] = None
    output_end_line: Optional[int] = None

    @property
    def duration(self) -> Optional[float]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def success(self) -> bool:
        return self.exit_status == 0

class ShellIntegrationMonitor:
    """
    Monitor shell integration marks for precise command tracking.

    FTCS Mark Sequence:
    1. FTCS_PROMPT (OSC 133;A) - Prompt starts
    2. FTCS_COMMAND_START (OSC 133;B) - User input starts
    3. FTCS_COMMAND_EXECUTED (OSC 133;C) - Command execution begins
    4. FTCS_COMMAND_FINISHED (OSC 133;D;[exit]) - Command completes
    """

    def __init__(self, session: 'ItermSession'):
        self.session = session
        self.current_execution: Optional[CommandExecution] = None
        self.command_history: list[CommandExecution] = []
        self._callbacks: list[Callable] = []

    async def is_shell_integration_installed(self) -> bool:
        """Check if shell integration is available in this session."""
        try:
            # Shell integration sets specific variables
            value = await self.session.session.async_get_variable(
                "session.terminalStateIsCurrent"
            )
            return value is not None
        except Exception:
            return False

    async def is_at_shell_prompt(self) -> bool:
        """
        Check if session is at shell prompt (ready for input).

        More reliable than polling is_processing.
        """
        if hasattr(self.session.session, 'async_get_is_at_shell_prompt'):
            return await self.session.session.async_get_is_at_shell_prompt()
        return False  # Fallback if shell integration not available

    async def execute_and_wait(
        self,
        command: str,
        timeout: float = 30.0
    ) -> CommandExecution:
        """
        Execute command and reliably wait for completion.

        Uses shell integration marks instead of pattern matching.
        """
        # Create execution record
        self.current_execution = CommandExecution(
            command=command,
            start_time=time.time()
        )

        # Send command
        await self.session.send_text(command, execute=True)

        # Wait for shell prompt (command completion)
        start = time.time()
        while time.time() - start < timeout:
            if await self.is_at_shell_prompt():
                self.current_execution.end_time = time.time()

                # Get exit status via variable
                exit_status = await self.session.session.async_get_variable(
                    "session.last_command_exit_status"
                )
                self.current_execution.exit_status = int(exit_status or 0)

                # Store in history
                execution = self.current_execution
                self.command_history.append(execution)
                self.current_execution = None

                # Notify callbacks
                await self._notify_completion(execution)

                return execution

            await asyncio.sleep(0.1)

        raise TimeoutError(f"Command did not complete within {timeout}s")

    def on_command_complete(
        self,
        callback: Callable[[CommandExecution], Awaitable[None]]
    ):
        """Register callback for command completion events."""
        self._callbacks.append(callback)

    async def _notify_completion(self, execution: CommandExecution):
        """Notify all registered callbacks."""
        for callback in self._callbacks:
            try:
                await callback(execution)
            except Exception as e:
                _logger.error(f"Callback error: {e}")
```

### 1.2 Broadcast Input Mode

**Source**: Menu Items (lines 2448-3800)

**What it enables**: Send identical input to multiple sessions simultaneously

**Current Gap**: Must send commands individually to each session

**Implementation**:

```python
# core/broadcast.py

from enum import Enum
from typing import List, Optional
import iterm2

class BroadcastMode(Enum):
    OFF = "off"
    CURRENT_TAB = "current_tab"
    ALL_TABS = "all_tabs"
    SELECTED_PANES = "selected_panes"

class BroadcastManager:
    """
    Manage broadcast input mode for multi-agent coordination.

    Broadcast modes enable sending the same keystrokes to multiple
    sessions simultaneously - critical for parallel deployments,
    synchronized testing, and team-wide commands.
    """

    def __init__(self, terminal: 'ItermTerminal'):
        self.terminal = terminal
        self._broadcast_mode = BroadcastMode.OFF
        self._selected_sessions: List[str] = []

    async def set_broadcast_mode(
        self,
        mode: BroadcastMode,
        show_indicator: bool = True
    ) -> None:
        """
        Enable/disable broadcast input mode.

        Args:
            mode: Broadcast mode to set
            show_indicator: Show red stripe on receiving sessions
        """
        app = await iterm2.async_get_app(self.terminal.connection)
        window = app.current_terminal_window

        if mode == BroadcastMode.ALL_TABS:
            # All panes in all tabs receive input
            await window.async_set_broadcast_domains(
                [iterm2.BroadcastDomain.ALL_PANES]
            )
        elif mode == BroadcastMode.CURRENT_TAB:
            # Only panes in current tab
            await window.async_set_broadcast_domains(
                [iterm2.BroadcastDomain.CURRENT_TAB]
            )
        elif mode == BroadcastMode.SELECTED_PANES:
            # Specific selected panes
            domains = [
                iterm2.BroadcastDomain.SELECTED_PANES
            ]
            await window.async_set_broadcast_domains(domains)
        else:
            # Turn off broadcasting
            await window.async_set_broadcast_domains([])

        self._broadcast_mode = mode

    async def broadcast_to_team(
        self,
        team_name: str,
        command: str
    ) -> None:
        """
        Send command to all agents in a team simultaneously.

        More efficient than cascading for identical commands.
        """
        # Get team sessions
        team_sessions = await self.terminal.get_team_sessions(team_name)

        if not team_sessions:
            raise ValueError(f"No sessions found for team: {team_name}")

        # Group sessions by tab
        tabs = {}
        for session in team_sessions:
            tab_id = await self._get_tab_id(session)
            if tab_id not in tabs:
                tabs[tab_id] = []
            tabs[tab_id].append(session)

        # Enable broadcast for team's tabs
        if len(tabs) == 1:
            # All in one tab - use current tab broadcast
            await self.set_broadcast_mode(BroadcastMode.CURRENT_TAB)

            # Focus one of the team's sessions
            await team_sessions[0].focus()

            # Send command (goes to all panes in tab)
            await team_sessions[0].send_text(command, execute=True)
        else:
            # Multiple tabs - use parallel write
            # (broadcast doesn't work across windows/tabs easily)
            await self._parallel_write(team_sessions, command)

        # Disable broadcast after operation
        await self.set_broadcast_mode(BroadcastMode.OFF)

    async def synchronized_command(
        self,
        sessions: List['ItermSession'],
        command: str,
        wait_for_all: bool = True
    ) -> List[CommandExecution]:
        """
        Execute identical command across sessions with synchronization.

        All sessions receive input at nearly the same time.
        """
        results = []

        # Enable broadcast for these sessions
        await self._select_sessions(sessions)
        await self.set_broadcast_mode(BroadcastMode.SELECTED_PANES)

        # Send command via any session (broadcast duplicates it)
        await sessions[0].send_text(command, execute=True)

        # Disable broadcast
        await self.set_broadcast_mode(BroadcastMode.OFF)

        if wait_for_all:
            # Wait for all to complete using shell integration
            for session in sessions:
                if hasattr(session, 'shell_monitor'):
                    result = await session.shell_monitor.wait_for_prompt()
                    results.append(result)

        return results
```

### 1.3 Window Arrangements

**Source**: Menu Items (lines 1587-1593) + Profiles (line 151-153)

**What it enables**: Save/restore complete orchestration layouts

**Current Gap**: Must recreate layouts manually each session

**Implementation**:

```python
# core/arrangements.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import json
import iterm2

@dataclass
class ArrangementMetadata:
    """Metadata stored with an arrangement."""
    name: str
    description: str
    created_at: str
    agent_count: int
    team_names: List[str]
    workflow_type: Optional[str] = None

class ArrangementManager:
    """
    Manage window arrangements for orchestration workflows.

    Arrangements save the complete state of windows, tabs, panes,
    and their positions - enabling one-click restoration of complex
    multi-agent setups.
    """

    def __init__(self, terminal: 'ItermTerminal'):
        self.terminal = terminal
        self._arrangements_dir = Path.home() / ".iterm-mcp" / "arrangements"
        self._arrangements_dir.mkdir(parents=True, exist_ok=True)

    async def save_arrangement(
        self,
        name: str,
        description: str = "",
        workflow_type: Optional[str] = None
    ) -> ArrangementMetadata:
        """
        Save current window arrangement with agent metadata.

        Args:
            name: Name for the arrangement
            description: Human-readable description
            workflow_type: Optional workflow classification

        Returns:
            Metadata about saved arrangement
        """
        app = await iterm2.async_get_app(self.terminal.connection)

        # Collect agent metadata from sessions
        teams = set()
        agent_count = 0

        for window in app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    agent_name = await session.async_get_variable("user.agent.name")
                    if agent_name:
                        agent_count += 1
                        team = await session.async_get_variable("user.agent.team")
                        if team:
                            teams.add(team)

        # Save via iTerm2 API
        await app.async_save_window_arrangement(name)

        # Store our metadata
        metadata = ArrangementMetadata(
            name=name,
            description=description,
            created_at=datetime.now().isoformat(),
            agent_count=agent_count,
            team_names=list(teams),
            workflow_type=workflow_type
        )

        metadata_path = self._arrangements_dir / f"{name}.json"
        with open(metadata_path, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)

        return metadata

    async def restore_arrangement(
        self,
        name: str,
        as_tabs: bool = False,
        re_register_agents: bool = True
    ) -> List['ItermSession']:
        """
        Restore a saved arrangement and optionally re-register agents.

        Args:
            name: Name of arrangement to restore
            as_tabs: If True, restore as tabs in current window
            re_register_agents: If True, re-register agents from session metadata

        Returns:
            List of restored sessions
        """
        app = await iterm2.async_get_app(self.terminal.connection)

        # Restore via iTerm2
        await app.async_restore_window_arrangement(name, as_tabs=as_tabs)

        # Allow iTerm2 to create sessions
        await asyncio.sleep(0.5)

        # Discover and wrap restored sessions
        restored_sessions = []

        for window in app.windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    wrapped = ItermSession(
                        session=session,
                        max_lines=self.terminal.default_max_lines
                    )

                    if re_register_agents:
                        # Re-register agent from stored variables
                        agent_name = await session.async_get_variable("user.agent.name")
                        if agent_name:
                            role = await session.async_get_variable("user.agent.role")
                            team = await session.async_get_variable("user.agent.team")

                            self.terminal.agent_registry.register_agent(
                                name=agent_name,
                                session_id=wrapped.id,
                                teams=[team] if team else []
                            )

                    restored_sessions.append(wrapped)
                    self.terminal.sessions[wrapped.id] = wrapped

        return restored_sessions

    async def list_arrangements(self) -> List[ArrangementMetadata]:
        """List all saved arrangements with metadata."""
        arrangements = []

        for path in self._arrangements_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                arrangements.append(ArrangementMetadata(**data))

        return arrangements

    async def create_workflow_template(
        self,
        template_name: str,
        config: Dict[str, Any]
    ) -> str:
        """
        Create a reusable workflow template.

        Config example:
        {
            "teams": [
                {"name": "backend", "agents": 3, "role": "builder"},
                {"name": "frontend", "agents": 2, "role": "builder"}
            ],
            "layout": "quad",
            "include_manager": True
        }
        """
        # Create layout based on config
        sessions = []

        for team_config in config.get("teams", []):
            team_name = team_config["name"]
            agent_count = team_config.get("agents", 1)
            role = team_config.get("role", "builder")

            for i in range(agent_count):
                agent_name = f"{team_name}-{i+1}"
                session = await self.terminal.create_agent_session(
                    role=role,
                    agent_name=agent_name
                )
                await session.set_agent_variable("team", team_name)
                sessions.append(session)

        if config.get("include_manager"):
            manager = await self.terminal.create_agent_session(
                role="orchestrator",
                agent_name="manager"
            )
            sessions.insert(0, manager)

        # Save as arrangement
        await self.save_arrangement(
            name=f"template_{template_name}",
            description=f"Workflow template: {template_name}",
            workflow_type="template"
        )

        return template_name
```

---

## Phase 2: Enhanced Automation (Next)

### 2.1 Session Variables for Agent Metadata

**Source**: Reference Objects (lines 1948-1951)

**What it enables**: Store agent identity, role, status in session itself

**Implementation**:

```python
# Add to core/session.py ItermSession class

class AgentVariables:
    """Namespace for agent session variables."""
    NAME = "user.agent.name"
    ROLE = "user.agent.role"
    TEAM = "user.agent.team"
    STATUS = "user.agent.status"
    WORKFLOW_ID = "user.agent.workflow_id"
    TASK_ID = "user.agent.task_id"
    MANAGER = "user.agent.manager"

async def set_agent_identity(
    self,
    agent_name: str,
    role: str,
    team: Optional[str] = None,
    manager: Optional[str] = None
) -> None:
    """
    Set comprehensive agent identity on the session.

    These variables persist with the session and can be:
    - Queried by other agents
    - Used in badge interpolation
    - Restored after arrangements reload
    """
    await self.session.async_set_variable(AgentVariables.NAME, agent_name)
    await self.session.async_set_variable(AgentVariables.ROLE, role)

    if team:
        await self.session.async_set_variable(AgentVariables.TEAM, team)
    if manager:
        await self.session.async_set_variable(AgentVariables.MANAGER, manager)

    # Set initial status
    await self.set_agent_status("idle")

    # Update badge with variable interpolation
    badge = (
        f"\\(user.agent.name) [\\(user.agent.role)]\\n"
        f"Status: \\(user.agent.status)"
    )
    await self.set_badge(badge)

async def set_agent_status(self, status: str) -> None:
    """Update agent status and visual indicators."""
    await self.session.async_set_variable(AgentVariables.STATUS, status)

    # Update visual appearance based on status
    status_visuals = {
        "idle": {"transparency": 0.3, "tab_color": (100, 100, 100)},
        "running": {"transparency": 0.0, "tab_color": (100, 150, 255)},
        "blocked": {"transparency": 0.2, "tab_color": (255, 200, 100)},
        "error": {"transparency": 0.0, "tab_color": (255, 100, 100)},
        "success": {"transparency": 0.1, "tab_color": (100, 255, 100)},
    }

    if status in status_visuals:
        visual = status_visuals[status]
        await self.set_transparency(visual["transparency"])
        await self.set_tab_color(*visual["tab_color"])

async def get_agent_identity(self) -> Dict[str, Optional[str]]:
    """Get all agent identity information."""
    return {
        "name": await self.session.async_get_variable(AgentVariables.NAME),
        "role": await self.session.async_get_variable(AgentVariables.ROLE),
        "team": await self.session.async_get_variable(AgentVariables.TEAM),
        "status": await self.session.async_get_variable(AgentVariables.STATUS),
        "workflow_id": await self.session.async_get_variable(AgentVariables.WORKFLOW_ID),
        "task_id": await self.session.async_get_variable(AgentVariables.TASK_ID),
        "manager": await self.session.async_get_variable(AgentVariables.MANAGER),
    }
```

### 2.2 Trigger-Based Automation

**Source**: Profiles (lines 159-163, 1479-1483)

**What it enables**: Automatic responses to output patterns

**Implementation**:

```python
# core/triggers.py

from dataclasses import dataclass
from typing import List, Callable, Optional, Pattern
import re

@dataclass
class TriggerAction:
    """Action to take when trigger fires."""
    action_type: str  # "notify", "highlight", "send_text", "callback"
    parameter: str
    callback: Optional[Callable] = None

@dataclass
class OrchestrationTrigger:
    """A trigger for automated orchestration responses."""
    name: str
    pattern: Pattern
    actions: List[TriggerAction]
    instant: bool = True  # Fire immediately vs wait for line completion

class TriggerManager:
    """
    Manage triggers for automated orchestration responses.

    Triggers execute actions based on regex matches in terminal output:
    - Error detection and alerts
    - Progress tracking
    - Workflow state transitions
    - Auto-recovery commands
    """

    # Pre-built trigger templates
    TEMPLATES = {
        "error_detection": {
            "pattern": r"(?i)(error|exception|failed|fatal)",
            "actions": [
                TriggerAction("highlight", "red"),
                TriggerAction("notify", "Error detected"),
            ]
        },
        "build_success": {
            "pattern": r"(?i)(build succeeded|built successfully|compilation complete)",
            "actions": [
                TriggerAction("highlight", "green"),
                TriggerAction("notify", "Build completed"),
            ]
        },
        "test_results": {
            "pattern": r"(\d+) passed.*?(\d+) failed",
            "actions": [
                TriggerAction("notify", "Test results: \\1 passed, \\2 failed"),
            ]
        },
        "progress_percent": {
            "pattern": r"(\d+)%",
            "actions": [
                TriggerAction("callback", "update_progress"),
            ]
        }
    }

    def __init__(self, session: 'ItermSession'):
        self.session = session
        self.triggers: List[OrchestrationTrigger] = []
        self._callbacks: Dict[str, Callable] = {}

    async def add_trigger(
        self,
        name: str,
        pattern: str,
        actions: List[Dict[str, str]],
        instant: bool = True
    ) -> None:
        """Add a trigger to the session profile."""
        trigger = OrchestrationTrigger(
            name=name,
            pattern=re.compile(pattern),
            actions=[TriggerAction(**a) for a in actions],
            instant=instant
        )

        self.triggers.append(trigger)

        # Also set on iTerm2 profile for native processing
        profile = await self.session.session.async_get_profile()

        iterm_trigger = {
            "regex": pattern,
            "instant": instant,
            "parameter": actions[0]["parameter"] if actions else "",
        }

        # Map action types to iTerm2 trigger actions
        if actions[0]["action_type"] == "highlight":
            iterm_trigger["action"] = "HighlightTextAction"
        elif actions[0]["action_type"] == "notify":
            iterm_trigger["action"] = "PostNotificationAction"
        elif actions[0]["action_type"] == "send_text":
            iterm_trigger["action"] = "SendTextAction"
        elif actions[0]["action_type"] == "callback":
            iterm_trigger["action"] = "InvokeScriptFunctionAction"
            iterm_trigger["parameter"] = f"orchestration_callback:{actions[0]['parameter']}"

        # Get existing triggers and append
        existing = await profile.async_get_triggers() or []
        existing.append(iterm_trigger)
        await profile.async_set_triggers(existing)

    async def add_template(self, template_name: str) -> None:
        """Add a pre-built trigger template."""
        if template_name not in self.TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")

        template = self.TEMPLATES[template_name]
        await self.add_trigger(
            name=template_name,
            pattern=template["pattern"],
            actions=[asdict(a) for a in template["actions"]]
        )

    async def setup_workflow_triggers(
        self,
        workflow_transitions: List[Dict[str, str]]
    ) -> None:
        """
        Set up triggers for workflow state transitions.

        Example transitions:
        [
            {"pattern": "Build complete", "next_state": "testing"},
            {"pattern": "All tests passed", "next_state": "deployment"},
        ]
        """
        for transition in workflow_transitions:
            await self.add_trigger(
                name=f"workflow_{transition['next_state']}",
                pattern=transition["pattern"],
                actions=[{
                    "action_type": "callback",
                    "parameter": f"transition_to:{transition['next_state']}"
                }]
            )

    def register_callback(self, name: str, callback: Callable) -> None:
        """Register a callback for trigger actions."""
        self._callbacks[name] = callback
```

---

## Phase 3: Advanced Features (Future)

### 3.1 Hotkey Windows for Orchestration Console

**Source**: Reference Objects (lines 1707-1708, 1782-1792)

```python
# core/hotkey_console.py

class OrchestrationConsole:
    """
    Hotkey-accessible orchestration dashboard.

    A global hotkey (e.g., Cmd+Shift+O) shows/hides a floating
    dashboard window with:
    - All agent statuses
    - Active workflows
    - Team overview
    - Quick commands
    """

    CONSOLE_PROFILE = "Orchestration Console"
    DEFAULT_HOTKEY = "cmd+shift+o"

    def __init__(self, terminal: 'ItermTerminal'):
        self.terminal = terminal
        self.console_session: Optional['ItermSession'] = None

    async def setup(self, hotkey: str = DEFAULT_HOTKEY) -> 'ItermSession':
        """Create and configure the orchestration console."""
        # First, create the profile with hotkey
        await self._create_console_profile(hotkey)

        # Create the hotkey window
        app = await iterm2.async_get_app(self.terminal.connection)
        window = await app.async_create_hotkey_window(self.CONSOLE_PROFILE)

        session = window.current_tab.current_session

        self.console_session = ItermSession(
            session=session,
            name="Orchestrator Console",
            max_lines=100
        )

        # Configure console appearance
        await self.console_session.set_badge("Dashboard")
        await self.console_session.set_transparency(0.1)

        # Start dashboard display
        await self._start_dashboard()

        return self.console_session

    async def toggle(self) -> None:
        """Toggle console visibility."""
        if self.console_session:
            window = await self._get_console_window()
            if window:
                await window.async_toggle()

    async def _start_dashboard(self) -> None:
        """Start the dashboard refresh loop."""
        dashboard_script = '''
        while true; do
            clear
            echo "=== ORCHESTRATION DASHBOARD ==="
            echo ""
            echo "AGENTS:"
            # Would integrate with actual agent listing
            echo "  Running: 3  |  Idle: 2  |  Error: 0"
            echo ""
            echo "WORKFLOWS:"
            echo "  Active: 1  |  Completed: 5"
            echo ""
            echo "Press Cmd+Shift+O to hide"
            sleep 2
        done
        '''
        await self.console_session.send_text(dashboard_script, execute=True)
```

### 3.2 Coprocess for Logging

**Source**: Profiles (lines 169-171)

```python
# core/coprocess.py

class LoggingCoprocess:
    """
    Coprocess that logs all session output to database.

    A coprocess runs alongside a session, receiving all output
    as stdin and optionally sending responses as keyboard input.
    """

    async def attach_logger(
        self,
        session: 'ItermSession',
        log_path: str
    ) -> None:
        """Attach a logging coprocess to a session."""
        # Python script that logs stdin to file
        logger_script = f'''
import sys
from datetime import datetime

with open("{log_path}", "a") as log:
    for line in sys.stdin:
        timestamp = datetime.now().isoformat()
        log.write(f"{{timestamp}} | {{line}}")
        log.flush()
'''

        await session.session.async_start_coprocess(
            command=f"python3 -c '{logger_script}'"
        )

    async def attach_auto_responder(
        self,
        session: 'ItermSession',
        patterns: Dict[str, str]
    ) -> None:
        """
        Attach a coprocess that auto-responds to patterns.

        Args:
            patterns: Dict mapping regex patterns to response commands
        """
        patterns_json = json.dumps(patterns)

        responder_script = f'''
import sys
import re
import json

patterns = json.loads('{patterns_json}')

for line in sys.stdin:
    for pattern, response in patterns.items():
        if re.search(pattern, line):
            print(response)  # Output becomes keyboard input
            sys.stdout.flush()
'''

        await session.session.async_start_coprocess(
            command=f"python3 -c '{responder_script}'"
        )
```

---

## MCP Tool Additions

Based on the analysis, here are new MCP tools to expose:

### New Tools to Add

```python
# iterm_mcpy/fastmcp_server.py additions

@mcp.tool()
async def set_broadcast_mode(
    mode: Literal["off", "current_tab", "all_tabs"],
    ctx: Context
) -> str:
    """Enable broadcast input to multiple sessions simultaneously."""

@mcp.tool()
async def save_arrangement(
    name: str,
    description: str = "",
    ctx: Context
) -> str:
    """Save current window arrangement for later restoration."""

@mcp.tool()
async def restore_arrangement(
    name: str,
    as_tabs: bool = False,
    ctx: Context
) -> str:
    """Restore a previously saved arrangement."""

@mcp.tool()
async def list_arrangements(ctx: Context) -> List[Dict]:
    """List all saved arrangements with metadata."""

@mcp.tool()
async def execute_with_shell_integration(
    session_target: Dict,
    command: str,
    timeout: int = 30,
    ctx: Context
) -> Dict:
    """
    Execute command using shell integration for reliable completion detection.

    Returns command output, exit status, and duration.
    """

@mcp.tool()
async def add_workflow_triggers(
    session_target: Dict,
    transitions: List[Dict[str, str]],
    ctx: Context
) -> str:
    """
    Add triggers for workflow state transitions.

    Triggers fire when patterns match in output.
    """

@mcp.tool()
async def synchronized_broadcast(
    team: str,
    command: str,
    wait_for_all: bool = True,
    ctx: Context
) -> List[Dict]:
    """
    Send identical command to all team members simultaneously.

    Uses broadcast mode for synchronized execution.
    """

@mcp.tool()
async def toggle_orchestration_console(ctx: Context) -> str:
    """Toggle visibility of the orchestration dashboard hotkey window."""

@mcp.tool()
async def get_session_context(
    session_target: Dict,
    ctx: Context
) -> Dict:
    """
    Get full context for a session (host, user, directory, agent info).

    Uses shell integration variables when available.
    """

@mcp.tool()
async def lock_split_pane(
    session_target: Dict,
    dimension: Literal["width", "height"],
    locked: bool = True,
    ctx: Context
) -> str:
    """Lock/unlock a split pane to prevent auto-resizing."""
```

---

## Implementation Roadmap

### Phase 1 (Weeks 1-2)
- [ ] Shell Integration monitor class
- [ ] Broadcast mode management
- [ ] Window arrangements save/restore
- [ ] Session variables for agent metadata
- [ ] MCP tools for new features

### Phase 2 (Weeks 3-4)
- [ ] Trigger system implementation
- [ ] Visual status system
- [ ] Split pane locking
- [ ] Line info precise reading

### Phase 3 (Weeks 5-6)
- [ ] Hotkey console implementation
- [ ] Coprocess logging
- [ ] Dynamic profile generation
- [ ] Advanced visual feedback

### Future
- [ ] Tmux integration for persistence
- [ ] Multi-monitor workspace management
- [ ] Profile-based agent templates
- [ ] Advanced annotation system

---

## Summary

This roadmap identifies 40+ enhancement opportunities from the iTerm2 Python API that can transform iterm-mcp into a more powerful multi-agent orchestration platform. The highest-impact additions are:

1. **Shell Integration** - Reliable command tracking without polling
2. **Broadcast Mode** - Synchronized multi-agent execution
3. **Window Arrangements** - Saveable/restorable workflow templates
4. **Session Variables** - Embedded agent identity and status
5. **Triggers** - Automated responses to output patterns

These features align with the existing architecture and will significantly improve both the developer experience and the capabilities for complex multi-agent workflows.
