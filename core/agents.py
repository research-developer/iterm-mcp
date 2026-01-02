"""Agent and Team management for multi-session orchestration."""

import hashlib
import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .tags import SessionTagLockManager


class Agent(BaseModel):
    """Represents a Claude agent tied to a terminal session."""

    name: str = Field(..., description="Unique name for the agent")
    session_id: str = Field(..., description="iTerm session ID this agent controls")
    teams: List[str] = Field(default_factory=list, description="Teams this agent belongs to")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, str] = Field(default_factory=dict, description="Optional metadata")

    def is_member_of(self, team: str) -> bool:
        """Check if agent is a member of the specified team."""
        return team in self.teams


class Team(BaseModel):
    """Represents a named group of agents."""

    name: str = Field(..., description="Unique team name")
    description: str = Field(default="", description="Team description")
    parent_team: Optional[str] = Field(default=None, description="Parent team for cascading")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageRecord(BaseModel):
    """Tracks sent messages for deduplication."""

    content_hash: str = Field(..., description="SHA256 hash of message content")
    recipients: List[str] = Field(..., description="Agent names that received this message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SendTarget(BaseModel):
    """Specifies a target for message dispatch."""

    # Can target by agent name, team name, or both
    agent: Optional[str] = Field(default=None, description="Specific agent name")
    team: Optional[str] = Field(default=None, description="Team name (sends to all members)")
    condition: Optional[str] = Field(default=None, description="Regex pattern - only send if matches")
    message: Optional[str] = Field(default=None, description="Override message for this target")


class CascadingMessage(BaseModel):
    """A message that can cascade through team hierarchy."""

    broadcast: Optional[str] = Field(default=None, description="Message sent to ALL agents")
    teams: Dict[str, str] = Field(default_factory=dict, description="Team-specific messages")
    agents: Dict[str, str] = Field(default_factory=dict, description="Agent-specific messages")


class AgentRegistry:
    """Manages agents, teams, and message deduplication with JSONL persistence."""

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_message_history: int = 1000,
        lock_manager: Optional["SessionTagLockManager"] = None,
    ):
        """Initialize the agent registry.

        Args:
            data_dir: Directory for JSONL files. Defaults to ~/.iterm-mcp/
            max_message_history: Max messages to keep for deduplication
        """
        if data_dir is None:
            data_dir = os.path.expanduser("~/.iterm-mcp")

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.agents_file = self.data_dir / "agents.jsonl"
        self.teams_file = self.data_dir / "teams.jsonl"
        self.messages_file = self.data_dir / "messages.jsonl"

        # In-memory caches
        self._agents: Dict[str, Agent] = {}
        self._teams: Dict[str, Team] = {}
        self._message_history: deque = deque(maxlen=max_message_history)

        # Active session tracking
        self._active_session: Optional[str] = None
        self.lock_manager = lock_manager

        # Load existing data
        self._load_data()

    def attach_lock_manager(self, lock_manager: "SessionTagLockManager") -> None:
        """Attach a lock manager after initialization."""
        self.lock_manager = lock_manager

    def _load_data(self) -> None:
        """Load agents and teams from JSONL files."""
        # Load agents
        if self.agents_file.exists():
            with open(self.agents_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        agent = Agent(**data)
                        self._agents[agent.name] = agent

        # Load teams
        if self.teams_file.exists():
            with open(self.teams_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        team = Team(**data)
                        self._teams[team.name] = team

        # Load recent messages for deduplication
        if self.messages_file.exists():
            with open(self.messages_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        record = MessageRecord(**data)
                        self._message_history.append(record)

    def _save_agents(self) -> None:
        """Persist all agents to JSONL file."""
        with open(self.agents_file, 'w') as f:
            for agent in self._agents.values():
                f.write(agent.model_dump_json() + '\n')

    def _save_teams(self) -> None:
        """Persist all teams to JSONL file."""
        with open(self.teams_file, 'w') as f:
            for team in self._teams.values():
                f.write(team.model_dump_json() + '\n')

    def _append_message(self, record: MessageRecord) -> None:
        """Append a message record to history and file."""
        self._message_history.append(record)
        with open(self.messages_file, 'a') as f:
            f.write(record.model_dump_json() + '\n')

    # ==================== Agent Management ====================

    def register_agent(
        self,
        name: str,
        session_id: str,
        teams: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Agent:
        """Register a new agent or update existing one.

        Args:
            name: Unique agent name
            session_id: iTerm session ID
            teams: Optional list of team names
            metadata: Optional metadata dict

        Returns:
            The created/updated Agent
        """
        agent = Agent(
            name=name,
            session_id=session_id,
            teams=teams or [],
            metadata=metadata or {}
        )
        self._agents[name] = agent
        self._save_agents()
        return agent

    def get_agent(self, name: str) -> Optional[Agent]:
        """Get agent by name."""
        return self._agents.get(name)

    def get_agent_by_session(self, session_id: str) -> Optional[Agent]:
        """Get agent by session ID."""
        for agent in self._agents.values():
            if agent.session_id == session_id:
                return agent
        return None

    def remove_agent(self, name: str) -> bool:
        """Remove an agent. Returns True if removed."""
        if name in self._agents:
            del self._agents[name]
            self._save_agents()
            if self.lock_manager:
                self.lock_manager.release_locks_by_agent(name)
            return True
        return False

    def list_agents(self, team: Optional[str] = None) -> List[Agent]:
        """List all agents, optionally filtered by team."""
        if team is None:
            return list(self._agents.values())
        return [a for a in self._agents.values() if team in a.teams]

    def assign_to_team(self, agent_name: str, team_name: str) -> bool:
        """Add agent to a team. Returns True if successful."""
        agent = self._agents.get(agent_name)
        if agent and team_name not in agent.teams:
            agent.teams.append(team_name)
            self._save_agents()
            return True
        return False

    def remove_from_team(self, agent_name: str, team_name: str) -> bool:
        """Remove agent from a team. Returns True if successful."""
        agent = self._agents.get(agent_name)
        if agent and team_name in agent.teams:
            agent.teams.remove(team_name)
            self._save_agents()
            return True
        return False

    # ==================== Team Management ====================

    def create_team(
        self,
        name: str,
        description: str = "",
        parent_team: Optional[str] = None
    ) -> Team:
        """Create a new team.

        Args:
            name: Unique team name
            description: Team description
            parent_team: Optional parent team for hierarchy

        Returns:
            The created Team
        """
        team = Team(name=name, description=description, parent_team=parent_team)
        self._teams[name] = team
        self._save_teams()
        return team

    def get_team(self, name: str) -> Optional[Team]:
        """Get team by name."""
        return self._teams.get(name)

    def remove_team(self, name: str) -> bool:
        """Remove a team. Returns True if removed."""
        if name in self._teams:
            del self._teams[name]
            self._save_teams()
            # Also remove team from all agents
            for agent in self._agents.values():
                if name in agent.teams:
                    agent.teams.remove(name)
            self._save_agents()
            return True
        return False

    def list_teams(self) -> List[Team]:
        """List all teams."""
        return list(self._teams.values())

    def get_child_teams(self, parent_name: str) -> List[Team]:
        """Get all teams that have the specified parent."""
        return [t for t in self._teams.values() if t.parent_team == parent_name]

    def get_team_hierarchy(self, team_name: str) -> List[str]:
        """Get team hierarchy from root to specified team.

        Returns list of team names from top-most parent to the given team.
        """
        hierarchy = []
        current = team_name

        while current:
            hierarchy.insert(0, current)
            team = self._teams.get(current)
            if team:
                current = team.parent_team
            else:
                break

        return hierarchy

    # ==================== Active Session ====================

    @property
    def active_session(self) -> Optional[str]:
        """Get the currently active session ID."""
        return self._active_session

    @active_session.setter
    def active_session(self, session_id: Optional[str]) -> None:
        """Set the active session ID."""
        self._active_session = session_id

    def get_active_agent(self) -> Optional[Agent]:
        """Get the agent for the active session."""
        if self._active_session:
            return self.get_agent_by_session(self._active_session)
        return None

    # ==================== Message Deduplication ====================

    @staticmethod
    def _hash_message(content: str) -> str:
        """Create a hash of message content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def was_message_sent(self, content: str, recipient: str) -> bool:
        """Check if this exact message was already sent to this recipient.

        Args:
            content: Message content
            recipient: Agent name

        Returns:
            True if message was previously sent to this recipient
        """
        content_hash = self._hash_message(content)

        for record in self._message_history:
            if record.content_hash == content_hash and recipient in record.recipients:
                return True
        return False

    def record_message_sent(self, content: str, recipients: List[str]) -> None:
        """Record that a message was sent to recipients.

        Args:
            content: Message content
            recipients: List of agent names that received the message
        """
        record = MessageRecord(
            content_hash=self._hash_message(content),
            recipients=recipients
        )
        self._append_message(record)

    def filter_unsent_recipients(self, content: str, recipients: List[str]) -> List[str]:
        """Filter recipients to only those who haven't received this message.

        Args:
            content: Message content
            recipients: List of potential recipient agent names

        Returns:
            List of agent names who haven't received this message
        """
        content_hash = self._hash_message(content)
        already_received: Set[str] = set()

        for record in self._message_history:
            if record.content_hash == content_hash:
                already_received.update(record.recipients)

        return [r for r in recipients if r not in already_received]

    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, str]]:
        """Expose recent message hashes for telemetry dashboards."""

        recent = list(self._message_history)[-limit:]
        return [
            {
                "content_hash": record.content_hash,
                "recipients": record.recipients,
                "timestamp": record.timestamp.isoformat(),
            }
            for record in recent
        ]

    # ==================== Cascading Messages ====================

    def resolve_cascade_targets(self, cascade: CascadingMessage) -> Dict[str, List[str]]:
        """Resolve a cascading message to specific agent targets.

        This builds a mapping of message -> list of agent names, handling:
        1. Broadcast messages go to all agents
        2. Team messages go to team members
        3. Agent-specific messages override team/broadcast

        Messages are deduplicated so agents only receive the most specific message.

        Args:
            cascade: The cascading message specification

        Returns:
            Dict mapping message content to list of agent names
        """
        # Track which agents have been assigned a message (most specific wins)
        agent_messages: Dict[str, str] = {}  # agent_name -> message

        # 1. Start with broadcast (least specific)
        if cascade.broadcast:
            for agent in self._agents.values():
                agent_messages[agent.name] = cascade.broadcast

        # 2. Apply team messages (more specific)
        for team_name, message in cascade.teams.items():
            for agent in self.list_agents(team=team_name):
                agent_messages[agent.name] = message

        # 3. Apply agent-specific messages (most specific)
        for agent_name, message in cascade.agents.items():
            if agent_name in self._agents:
                agent_messages[agent_name] = message

        # Invert to get message -> [agents]
        message_targets: Dict[str, List[str]] = {}
        for agent_name, message in agent_messages.items():
            if message not in message_targets:
                message_targets[message] = []
            message_targets[message].append(agent_name)

        return message_targets

    def get_session_ids_for_agents(self, agent_names: List[str]) -> List[str]:
        """Convert agent names to session IDs.

        Args:
            agent_names: List of agent names

        Returns:
            List of session IDs (preserves order, skips unknown agents)
        """
        session_ids = []
        for name in agent_names:
            agent = self._agents.get(name)
            if agent:
                session_ids.append(agent.session_id)
        return session_ids
