"""Lightweight telemetry aggregation for panes, agents, and teams."""

from typing import Any, Dict, List, Optional

from core.agents import AgentRegistry
from core.session import ItermSession
from core.terminal import ItermTerminal
from utils.logging import ItermLogManager


class TelemetryEmitter:
    """Emit aggregated telemetry derived from session logs and registry state."""

    def __init__(
        self,
        log_manager: Optional[ItermLogManager],
        agent_registry: AgentRegistry,
    ) -> None:
        self.log_manager = log_manager
        self.agent_registry = agent_registry

    def _pane_entries(self, sessions: List[ItermSession]) -> List[Dict[str, Any]]:
        telemetry = self.log_manager.get_session_telemetry() if self.log_manager else {}
        panes: List[Dict[str, Any]] = []

        for session in sessions:
            session_metrics = telemetry.get(session.id, {})
            agent = self.agent_registry.get_agent_by_session(session.id)
            panes.append(
                {
                    "id": session.id,
                    "name": session.name,
                    "persistent_id": session.persistent_id,
                    "agent": agent.name if agent else None,
                    "command_count": session_metrics.get("command_count", 0),
                    "output_lines": session_metrics.get("output_line_count", 0),
                    "recent_errors": session_metrics.get("recent_errors", []),
                    "last_command_at": session_metrics.get("last_command_at"),
                    "last_output_at": session_metrics.get("last_output_at"),
                    "queue_depth": 1 if getattr(session, "is_processing", False) else 0,
                }
            )

        return panes

    def _team_hierarchy(self) -> List[Dict[str, Any]]:
        teams = []
        for team in self.agent_registry.list_teams():
            teams.append(
                {
                    "name": team.name,
                    "description": team.description,
                    "parent": team.parent_team,
                    "members": [a.name for a in self.agent_registry.list_agents(team=team.name)],
                    "hierarchy": self.agent_registry.get_team_hierarchy(team.name),
                }
            )
        return teams

    def dashboard_state(
        self, terminal: ItermTerminal, max_messages: int = 10
    ) -> Dict[str, Any]:
        sessions = list(terminal.sessions.values())
        agents = self.agent_registry.list_agents()

        return {
            "agents_online": len(agents),
            "pane_count": len(sessions),
            "panes": self._pane_entries(sessions),
            "recent_messages": self.agent_registry.get_recent_messages(limit=max_messages),
            "teams": self._team_hierarchy(),
            "active_session": self.agent_registry.active_session,
        }

    def format_tui(self, state: Dict[str, Any]) -> str:
        lines = [
            "=== iTerm MCP Telemetry Dashboard ===",
            f"Agents online: {state.get('agents_online', 0)}",
            f"Panes tracked: {state.get('pane_count', 0)}",
            "",
            "Team hierarchy:",
        ]

        teams = state.get("teams", [])
        if not teams:
            lines.append("  (no teams registered)")
        else:
            for team in teams:
                lineage = " -> ".join(team.get("hierarchy", []))
                members = ", ".join(team.get("members", [])) or "(no members)"
                lines.append(f"  - {team['name']} [{lineage}] :: {members}")

        lines.append("\nPane health:")
        panes = state.get("panes", [])
        if not panes:
            lines.append("  (no active panes discovered)")
        else:
            for pane in panes:
                lines.append(
                    f"  - {pane['name']} ({pane['id']}) cmds={pane['command_count']} "
                    f"out={pane['output_lines']} queue={pane['queue_depth']}"
                )
                if pane.get("recent_errors"):
                    latest_error = pane["recent_errors"][0]
                    lines.append(f"      last error: {latest_error}")

        messages = state.get("recent_messages", [])
        lines.append("\nRecent message hashes:")
        if not messages:
            lines.append("  (no message history yet)")
        else:
            for msg in messages:
                recipients = ", ".join(msg.get("recipients", []))
                lines.append(
                    f"  - {msg['content_hash'][:10]}... -> {recipients} @ {msg['timestamp']}"
                )

        return "\n".join(lines)
