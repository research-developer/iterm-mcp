"""gRPC client for iTerm MCP service."""

import grpc
from typing import Dict, List, Optional

# Import from local generated files
from . import iterm_mcp_pb2
from . import iterm_mcp_pb2_grpc


class ITermClient:
    """Client for interacting with iTerm MCP gRPC service."""

    def __init__(self, host: str = 'localhost', port: int = 50051):
        """Initialize the client.

        Args:
            host: Server host
            port: Server port
        """
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = iterm_mcp_pb2_grpc.ITermServiceStub(self.channel)

    def close(self):
        """Close the gRPC channel."""
        self.channel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ==================== Helpers ====================

    def _build_session_target(self, target: Dict) -> iterm_mcp_pb2.SessionTarget:
        return iterm_mcp_pb2.SessionTarget(
            session_id=target.get('session_id', ''),
            name=target.get('name', ''),
            agent=target.get('agent', ''),
            team=target.get('team', '')
        )

    def _build_session_message(self, msg: Dict) -> iterm_mcp_pb2.SessionMessage:
        targets = [self._build_session_target(t) for t in msg.get('targets', [])]

        use_encoding_value = msg.get('use_encoding', False)
        if isinstance(use_encoding_value, bool):
            use_encoding_str = 'true' if use_encoding_value else 'false'
        else:
            use_encoding_str = str(use_encoding_value)

        return iterm_mcp_pb2.SessionMessage(
            content=msg.get('content', ''),
            targets=targets,
            condition=msg.get('condition', ''),
            execute=msg.get('execute', True),
            use_encoding=use_encoding_str
        )

    def _build_write_request(
        self,
        messages: List[Dict],
        parallel: bool = True,
        skip_duplicates: bool = True
    ) -> iterm_mcp_pb2.WriteToSessionsRequest:
        session_messages = [self._build_session_message(msg) for msg in messages]
        return iterm_mcp_pb2.WriteToSessionsRequest(
            messages=session_messages,
            parallel=parallel,
            skip_duplicates=skip_duplicates
        )

    def _build_read_request(
        self,
        targets: Optional[List[Dict]] = None,
        parallel: bool = True,
        filter_pattern: Optional[str] = None
    ) -> iterm_mcp_pb2.ReadSessionsRequest:
        read_targets = []
        for t in (targets or []):
            read_targets.append(
                iterm_mcp_pb2.ReadTarget(
                    session_id=t.get('session_id', ''),
                    name=t.get('name', ''),
                    agent=t.get('agent', ''),
                    team=t.get('team', ''),
                    max_lines=t.get('max_lines', 0)
                )
            )

        return iterm_mcp_pb2.ReadSessionsRequest(
            targets=read_targets,
            parallel=parallel,
            filter_pattern=filter_pattern or ''
        )

    def _build_create_sessions_request(
        self,
        sessions: List[Dict],
        layout: str = "SINGLE",
        window_id: Optional[str] = None
    ) -> iterm_mcp_pb2.CreateSessionsRequest:
        session_configs = []
        for s in sessions:
            config = iterm_mcp_pb2.SessionConfig(
                name=s.get('name', ''),
                agent=s.get('agent', ''),
                team=s.get('team', ''),
                command=s.get('command', ''),
                max_lines=s.get('max_lines', 0),
                monitor=s.get('monitor', False)
            )
            session_configs.append(config)

        return iterm_mcp_pb2.CreateSessionsRequest(
            sessions=session_configs,
            layout=layout,
            window_id=window_id or ''
        )

    def _build_cascade_request(
        self,
        broadcast: Optional[str] = None,
        teams: Optional[Dict[str, str]] = None,
        agents: Optional[Dict[str, str]] = None,
        skip_duplicates: bool = True,
        execute: bool = True,
    ) -> iterm_mcp_pb2.CascadeMessageRequest:
        return iterm_mcp_pb2.CascadeMessageRequest(
            broadcast=broadcast or '',
            teams=teams or {},
            agents=agents or {},
            skip_duplicates=skip_duplicates,
            execute=execute,
        )

    # ==================== Session Operations ====================

    def list_sessions(self) -> List[iterm_mcp_pb2.Session]:
        """List all available sessions."""
        response = self.stub.ListSessions(iterm_mcp_pb2.Empty())
        return list(response.sessions)

    def focus_session(self, identifier: str) -> bool:
        """Focus a specific session.

        Args:
            identifier: Session ID, name, or agent name
        """
        response = self.stub.FocusSession(
            iterm_mcp_pb2.SessionIdentifier(identifier=identifier)
        )
        return response.success

    def check_session_status(self, identifier: str) -> iterm_mcp_pb2.SessionStatus:
        """Check status of a session."""
        return self.stub.CheckSessionStatus(
            iterm_mcp_pb2.SessionIdentifier(identifier=identifier)
        )

    def set_active_session(
        self,
        session_id: Optional[str] = None,
        name: Optional[str] = None,
        agent: Optional[str] = None
    ) -> bool:
        """Set the active session.

        Args:
            session_id: Session ID to set active
            name: Session name to set active
            agent: Agent name to set active
        """
        request = iterm_mcp_pb2.SetActiveSessionRequest()
        if session_id:
            request.session_id = session_id
        elif name:
            request.name = name
        elif agent:
            request.agent = agent

        response = self.stub.SetActiveSession(request)
        return response.success

    # ==================== Create Sessions ====================

    def create_sessions(
        self,
        sessions: List[Dict],
        layout: str = "SINGLE",
        window_id: Optional[str] = None
    ) -> iterm_mcp_pb2.CreateSessionsResponse:
        """Create multiple sessions with optional layout.

        Args:
            sessions: List of session configs (name, agent, team, command, etc.)
            layout: Layout type (SINGLE, HORIZONTAL_SPLIT, VERTICAL_SPLIT, QUAD)
            window_id: Optional window ID to create in
        """
        request = self._build_create_sessions_request(sessions, layout, window_id)
        return self.stub.CreateSessions(request)

    # ==================== Write/Read Operations ====================

    def write_to_sessions(
        self,
        messages: List[Dict],
        parallel: bool = True,
        skip_duplicates: bool = True
    ) -> iterm_mcp_pb2.WriteToSessionsResponse:
        """Write messages to one or more sessions.

        Args:
            messages: List of message dicts with content, targets, condition, etc.
            parallel: Execute sends in parallel
            skip_duplicates: Skip duplicate messages
        """
        request = self._build_write_request(messages, parallel, skip_duplicates)
        return self.stub.WriteToSessions(request)

    def read_sessions(
        self,
        targets: Optional[List[Dict]] = None,
        parallel: bool = True,
        filter_pattern: Optional[str] = None
    ) -> iterm_mcp_pb2.ReadSessionsResponse:
        """Read output from one or more sessions.

        Args:
            targets: List of target dicts (session_id, name, agent, team, max_lines)
            parallel: Read in parallel
            filter_pattern: Regex pattern to filter output
        """
        request = self._build_read_request(targets, parallel, filter_pattern)
        return self.stub.ReadSessions(request)

    def send_control_character(
        self,
        control_char: str,
        session_id: Optional[str] = None,
        name: Optional[str] = None,
        agent: Optional[str] = None,
        team: Optional[str] = None
    ) -> bool:
        """Send a control character to a session.

        Args:
            control_char: Control character to send (e.g., 'c' for Ctrl+C)
            session_id: Target session ID
            name: Target session name
            agent: Target agent name
            team: Target team name
        """
        target = iterm_mcp_pb2.SessionTarget(
            session_id=session_id or '',
            name=name or '',
            agent=agent or '',
            team=team or ''
        )
        request = iterm_mcp_pb2.ControlCharRequest(
            target=target,
            control_char=control_char
        )
        response = self.stub.SendControlCharacter(request)
        return response.success

    # ==================== Agent Management ====================

    def register_agent(
        self,
        name: str,
        session_id: str,
        teams: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> iterm_mcp_pb2.Agent:
        """Register a new agent.

        Args:
            name: Unique agent name
            session_id: iTerm session ID
            teams: List of team names
            metadata: Optional metadata
        """
        request = iterm_mcp_pb2.RegisterAgentRequest(
            name=name,
            session_id=session_id,
            teams=teams or [],
            metadata=metadata or {}
        )
        return self.stub.RegisterAgent(request)

    def list_agents(self, team: Optional[str] = None) -> List[iterm_mcp_pb2.Agent]:
        """List all agents, optionally filtered by team."""
        request = iterm_mcp_pb2.ListAgentsRequest(team=team or '')
        response = self.stub.ListAgents(request)
        return list(response.agents)

    def remove_agent(self, name: str) -> bool:
        """Remove an agent."""
        response = self.stub.RemoveAgent(
            iterm_mcp_pb2.AgentIdentifier(name=name)
        )
        return response.success

    # ==================== Team Management ====================

    def create_team(
        self,
        name: str,
        description: str = "",
        parent_team: Optional[str] = None
    ) -> iterm_mcp_pb2.Team:
        """Create a new team.

        Args:
            name: Unique team name
            description: Team description
            parent_team: Parent team name for hierarchy
        """
        request = iterm_mcp_pb2.CreateTeamRequest(
            name=name,
            description=description,
            parent_team=parent_team or ''
        )
        return self.stub.CreateTeam(request)

    def list_teams(self) -> List[iterm_mcp_pb2.Team]:
        """List all teams."""
        response = self.stub.ListTeams(iterm_mcp_pb2.Empty())
        return list(response.teams)

    def remove_team(self, name: str) -> bool:
        """Remove a team."""
        response = self.stub.RemoveTeam(
            iterm_mcp_pb2.TeamIdentifier(name=name)
        )
        return response.success

    def assign_agent_to_team(self, agent_name: str, team_name: str) -> bool:
        """Assign an agent to a team."""
        response = self.stub.AssignAgentToTeam(
            iterm_mcp_pb2.AgentTeamAssignment(
                agent_name=agent_name,
                team_name=team_name
            )
        )
        return response.success

    def remove_agent_from_team(self, agent_name: str, team_name: str) -> bool:
        """Remove an agent from a team."""
        response = self.stub.RemoveAgentFromTeam(
            iterm_mcp_pb2.AgentTeamAssignment(
                agent_name=agent_name,
                team_name=team_name
            )
        )
        return response.success

    # ==================== Cascade Messages ====================

    def send_cascade_message(
        self,
        broadcast: Optional[str] = None,
        teams: Optional[Dict[str, str]] = None,
        agents: Optional[Dict[str, str]] = None,
        skip_duplicates: bool = True,
        execute: bool = True
    ) -> iterm_mcp_pb2.CascadeMessageResponse:
        """Send cascading messages to agents/teams.

        Args:
            broadcast: Message to ALL agents
            teams: Dict of team_name -> message
            agents: Dict of agent_name -> message
            skip_duplicates: Skip duplicate messages
            execute: Press Enter after sending
        """
        request = self._build_cascade_request(broadcast, teams, agents, skip_duplicates, execute)
        return self.stub.SendCascadeMessage(request)

    def orchestrate_playbook(self, playbook: Dict) -> iterm_mcp_pb2.OrchestrateResponse:
        """Execute a playbook (layout + commands + cascade + reads)."""

        playbook_msg = iterm_mcp_pb2.Playbook()

        layout = playbook.get('layout')
        if layout:
            playbook_msg.layout.CopyFrom(
                self._build_create_sessions_request(
                    layout.get('sessions', []),
                    layout.get('layout', 'SINGLE'),
                    layout.get('window_id')
                )
            )

        for command in playbook.get('commands', []):
            write_request = self._build_write_request(
                command.get('messages', []),
                command.get('parallel', True),
                command.get('skip_duplicates', True)
            )
            playbook_msg.commands.append(
                iterm_mcp_pb2.PlaybookCommand(
                    name=command.get('name', 'commands'),
                    messages=write_request.messages,
                    parallel=write_request.parallel,
                    skip_duplicates=write_request.skip_duplicates,
                )
            )

        cascade = playbook.get('cascade')
        if cascade:
            playbook_msg.cascade.CopyFrom(
                self._build_cascade_request(
                    cascade.get('broadcast'),
                    cascade.get('teams'),
                    cascade.get('agents'),
                    cascade.get('skip_duplicates', True),
                    cascade.get('execute', True)
                )
            )

        reads = playbook.get('reads')
        if reads:
            playbook_msg.reads.CopyFrom(
                self._build_read_request(
                    reads.get('targets'),
                    reads.get('parallel', True),
                    reads.get('filter_pattern')
                )
            )

        request = iterm_mcp_pb2.OrchestrateRequest(playbook=playbook_msg)
        return self.stub.OrchestratePlaybook(request)

    # ==================== Backward Compatibility ====================

    def create_layout(self, layout_type: str, session_names: List[str]) -> List[iterm_mcp_pb2.Session]:
        """Create a layout (backward compatibility wrapper).

        Deprecated: Use create_sessions instead.
        """
        sessions = [{'name': name} for name in session_names]
        response = self.create_sessions(sessions, layout=layout_type)
        # Convert to Session format for compatibility
        result = []
        for s in response.sessions:
            session = iterm_mcp_pb2.Session(
                id=s.session_id,
                name=s.name,
                persistent_id=s.persistent_id,
                agent=s.agent
            )
            result.append(session)
        return result

    def write_to_terminal(
        self,
        session_identifier: str,
        command: str,
        wait_for_prompt: bool = False
    ) -> bool:
        """Write to terminal (backward compatibility wrapper).

        Deprecated: Use write_to_sessions instead.
        """
        messages = [{
            'content': command,
            'targets': [{'name': session_identifier}],
            'execute': True
        }]
        response = self.write_to_sessions(messages, parallel=False)
        return response.sent_count > 0

    def read_terminal_output(
        self,
        session_identifier: str,
        max_lines: int = 100
    ) -> str:
        """Read terminal output (backward compatibility wrapper).

        Deprecated: Use read_sessions instead.
        """
        targets = [{'name': session_identifier, 'max_lines': max_lines}]
        response = self.read_sessions(targets, parallel=False)
        if response.outputs:
            return response.outputs[0].content
        return ""
