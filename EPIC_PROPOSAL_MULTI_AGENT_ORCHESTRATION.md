# Epic Proposal: Advanced Multi-Agent Orchestration with iTerm2 Python API

## Executive Summary

This epic proposes a comprehensive enhancement to the iTerm2 MCP server to create an intuitive, visual, and robust multi-agent orchestration platform. The goal is to enable multiple agents from different teams to work together seamlessly, with the terminal pane hierarchy representing team structure in a way that humans can easily understand and interact with.

**Vision:** Transform iTerm2 into a visual command center where:
- Executive agents coordinate team hierarchies through intuitive pane layouts
- Visual feedback (colors, badges, status bars) provides real-time agent state
- Humans can work with their executive assistant OR message individual agents directly
- The terminal itself becomes a living organizational chart
- Agents communicate through well-defined protocols with full observability

## Current State Analysis

### Strengths ✅
- **Solid Foundation**: gRPC server with 17 RPC methods, 31 MCP tools
- **Agent Registry**: Team hierarchy support with cascading messages
- **Parallel Operations**: Multi-session read/write capabilities
- **Persistence**: Session reconnection via persistent IDs
- **Good Test Coverage**: 88 passing unit tests for core functionality

### Gaps & Opportunities ⚠️
- **No Visual Hierarchy**: Panes don't visually represent team structure
- **Limited Observability**: No real-time visual feedback of agent states
- **Basic Communication**: Missing structured event system between agents
- **No Coordination Primitives**: Lack of synchronization, voting, consensus
- **Minimal Error Recovery**: No automatic recovery or health monitoring
- **Static Layouts**: No dynamic pane reorganization based on team changes
- **Limited iTerm2 API Usage**: Not leveraging colors, badges, profiles, monitors

## Epic Goals

Transform the iTerm MCP into a production-ready multi-agent orchestration platform that:

1. **Visually represents agent hierarchy** through intelligent pane layouts
2. **Provides real-time observability** using iTerm2's color, badge, and status bar APIs
3. **Enables sophisticated coordination** through event monitors and custom control sequences
4. **Ensures reliability** through health monitoring and automatic recovery
5. **Offers intuitive human interaction** via executive agents and direct messaging
6. **Maintains security** through proper isolation and audit trails

## Proposed Sub-Issues

---

## Sub-Issue 1: Visual Hierarchy & Dynamic Layout Management

**Title:** Implement visual team hierarchy with dynamic pane layouts

**Problem:**
Currently, panes are created statically and don't reflect the organizational structure of agents and teams. When team membership changes, layouts remain fixed. There's no visual indication of which pane belongs to which team or the team hierarchy.

**Solution:**
Leverage iTerm2's layout APIs, profiles, and visual properties to create a living organizational chart:

### Core Features:
1. **Hierarchical Layout Engine**
   - Map team hierarchy to nested pane structures (parent teams → larger splits)
   - Executive/coordinator agents in prominent positions (top-left, full-width)
   - Worker agents grouped by team with visual boundaries
   - Automatic layout recalculation when teams change

2. **Visual Team Identity**
   - Color-coded backgrounds by team (using `set_background_color`, `set_tab_color`)
   - Custom ANSI color schemes per team level
   - Team badges showing team name and member count
   - Border effects using unicode characters to delineate teams

3. **Dynamic Reorganization**
   - Monitor agent registry changes with file watchers
   - Automatically rearrange panes when agents join/leave teams
   - Smooth transitions using iTerm2's arrangement save/restore
   - Preserve window state during reorganization

4. **Named Arrangements**
   - Predefined templates: "Exec + 3 Teams", "Flat 8 Agents", "Matrix 4x4"
   - Save/restore team configurations via `iterm2.Arrangement`
   - Hot-swap layouts without disrupting sessions

### iTerm2 APIs to Use:
- `session.async_split_pane(vertical=True/False)` - Create hierarchy
- `LocalWriteOnlyProfile.set_background_color()` - Team colors
- `LocalWriteOnlyProfile.set_tab_color()` - Visual grouping
- `session.async_set_variable("user.team")` - Store metadata
- `iterm2.Arrangement.async_save/restore()` - Layout persistence
- `Tab.async_move_to_window()` - Reorganize on-the-fly

### Technical Approach:
```python
class HierarchicalLayoutEngine:
    """Dynamically creates pane layouts reflecting team hierarchy."""
    
    async def create_org_chart_layout(
        self,
        agent_registry: AgentRegistry,
        exec_agent: str,
        color_scheme: ColorScheme
    ) -> Dict[str, str]:
        """
        Creates a visual org chart:
        - Exec at top (full width)
        - Teams split vertically below
        - Each team's agents split horizontally
        """
        
    async def rebalance_layout(
        self,
        agent_registry: AgentRegistry,
        preserve_exec: bool = True
    ) -> None:
        """Reorganize panes when team membership changes."""
```

### Success Metrics:
- Layout automatically reflects team structure within 2 seconds of changes
- Visual differentiation between teams is clear at a glance
- No more than 2 layout transitions per team membership change
- Preserves session state during reorganization

---

## Sub-Issue 2: Real-Time Visual Agent Status System

**Title:** Implement comprehensive visual feedback using colors, badges, and status bars

**Problem:**
There's no way to see at a glance which agents are idle, working, blocked, or errored. Users must read logs or query sessions individually. The terminal looks static even when agents are actively working.

**Solution:**
Create a rich visual feedback system using iTerm2's rendering capabilities:

### Core Features:
1. **Color-Coded Agent States**
   - **Idle**: Dark gray background (`set_background_color(50, 50, 50)`)
   - **Thinking**: Blue pulse (`set_background_color(0, 50, 100)`)
   - **Working**: Green tint (`set_background_color(20, 80, 20)`)
   - **Waiting**: Yellow caution (`set_background_color(80, 80, 0)`)
   - **Error**: Red alert (`set_background_color(100, 20, 20)`)
   - **Success**: Bright green flash (`set_background_color(0, 150, 0)`)

2. **Dynamic Badges**
   - Display current task/tool being executed
   - Show queue depth for pending tasks
   - Display agent role/capabilities
   - Update via `set_badge_text()` and `set_badge_color()`

3. **Custom Status Bar Components**
   - Team-wide metrics (agents ready/busy/error)
   - Message queue status
   - Resource utilization (if measurable)
   - Last activity timestamp

4. **Attention Mechanisms**
   - Dock bounce on critical errors (`RequestAttention=yes`)
   - Firework animations for major milestones (`RequestAttention=fireworks`)
   - macOS notifications for human intervention needed (`\033]9;message\a`)
   - Tab color flash on state changes

5. **Output Pattern Recognition**
   - Monitor for tool invocations (`r'Tool:\s*(\w+)'`)
   - Detect errors (`r'ERROR:|FATAL:|Exception'`)
   - Track success patterns (`r'✓|SUCCESS|PASSED'`)
   - Update colors/badges automatically

### iTerm2 APIs to Use:
- `LocalWriteOnlyProfile.set_background_color()` - State colors
- `LocalWriteOnlyProfile.set_cursor_color()` - Active indicator
- `session.async_set_variable("user.status", status)` - Store state
- `iterm2.Alert()` - Modal notifications
- `session.async_inject("\033]9;message\033\\")` - System notifications
- `iterm2.StatusBarComponent` with `@iterm2.StatusBarRPC` - Custom metrics
- `session.get_screen_streamer()` - Pattern monitoring

### Technical Approach:
```python
class AgentStatusMonitor:
    """Monitors agent output and updates visual state."""
    
    STATUS_COLORS = {
        AgentState.IDLE: Color(50, 50, 50),
        AgentState.THINKING: Color(0, 50, 100),
        AgentState.WORKING: Color(20, 80, 20),
        AgentState.ERROR: Color(100, 20, 20),
    }
    
    async def monitor_agent_output(
        self,
        session: ItermSession,
        callback: Callable[[AgentState, str], None]
    ):
        """Monitor output and update visual state."""
        async with session.get_screen_streamer() as streamer:
            while True:
                contents = await streamer.async_get()
                state = self._detect_state(contents)
                await self._update_visual_state(session, state)

class StatusBarOrchestrator:
    """Custom status bar showing team metrics."""
    
    @iterm2.StatusBarRPC
    async def team_status(self, knobs):
        """Display: ● 5 ready, 2 working, 0 errors"""
        return f"● {ready} ready, {working} working, {errors} errors"
```

### Success Metrics:
- State changes visible within 500ms
- Badge updates reflect current task accurately
- Critical errors trigger immediate visual alerts
- Status bar provides at-a-glance team health

---

## Sub-Issue 3: Structured Inter-Agent Communication Protocol

**Title:** Implement event-driven communication using iTerm2 monitors and custom control sequences

**Problem:**
Agent communication is limited to broadcast messages and cascading priority. There's no event system, no request/response pattern, no acknowledgment mechanism. Agents can't easily coordinate complex workflows.

**Solution:**
Build a rich communication protocol using iTerm2's monitoring and IPC capabilities:

### Core Features:
1. **Custom Control Sequence Protocol**
   - Define message format: `\033]1337;Custom=id=mcp:type:payload\a`
   - Message types: REQUEST, RESPONSE, EVENT, BROADCAST, ACK
   - Structured JSON payloads for complex data
   - Encryption for sensitive coordination

2. **Event Monitors**
   - **New Session Monitor**: Auto-register new agents
   - **Termination Monitor**: Clean up on agent exit
   - **Focus Monitor**: Track which agent human is interacting with
   - **Prompt Monitor**: Detect command completion for synchronization
   - **Variable Monitor**: React to state changes in agents
   - **Custom Control Sequence Monitor**: Handle custom protocol

3. **Pub/Sub Event Bus**
   - Agents subscribe to topics: "task.completed", "error.critical"
   - Publish events visible to all subscribed agents
   - Topic hierarchy: "team.frontend.deploy.success"
   - Event history for late joiners

4. **Request/Response Pattern**
   - Agents send requests and await responses
   - Timeout handling with retries
   - Correlation IDs for tracking
   - Response routing to originating agent

5. **Coordination Primitives**
   - **Barriers**: Wait for all agents to reach checkpoint
   - **Voting**: Collect votes from team members
   - **Locks**: Distributed locking for shared resources
   - **Leader Election**: Designate coordinator dynamically

6. **User Variables as State**
   - Store agent state in `user.*` variables
   - Display in badges/titles: `\(user.currentTask)`
   - Monitor changes with `VariableMonitor`
   - Synchronize across agents

### iTerm2 APIs to Use:
- `iterm2.CustomControlSequenceMonitor` - Custom protocol
- `iterm2.NewSessionMonitor` - Auto-registration
- `iterm2.SessionTerminationMonitor` - Cleanup
- `iterm2.FocusMonitor` - Human interaction tracking
- `iterm2.PromptMonitor` - Command completion
- `iterm2.VariableMonitor` - State change reactions
- `session.async_set_variable()` / `async_get_variable()` - State storage

### Technical Approach:
```python
class AgentEventBus:
    """Pub/Sub event bus using custom control sequences."""
    
    def __init__(self, connection: iterm2.Connection):
        self.subscriptions: Dict[str, List[str]] = {}  # topic -> session_ids
        
    async def start_monitoring(self):
        """Monitor for custom control sequences."""
        pattern = r'^mcp:(EVENT|REQUEST|RESPONSE):(.+)$'
        async with iterm2.CustomControlSequenceMonitor(
            self.connection, "mcp-protocol", pattern
        ) as mon:
            while True:
                match = await mon.async_get()
                await self._route_message(match)
    
    async def publish(self, topic: str, payload: dict, session_id: str):
        """Publish event to all subscribers."""
        message = json.dumps({"topic": topic, "payload": payload})
        code = f"\033]1337;Custom=id=mcp-protocol:EVENT:{message}\a"
        
        for sub_session_id in self.subscriptions.get(topic, []):
            session = self.app.get_session_by_id(sub_session_id)
            await session.async_inject(code.encode())

class CoordinationPrimitives:
    """Distributed coordination utilities."""
    
    async def barrier(self, barrier_id: str, participants: List[str], timeout: int = 60):
        """Wait for all participants to reach barrier."""
        
    async def vote(self, vote_id: str, voters: List[str], options: List[str]) -> str:
        """Collect votes and return winning option."""
        
    async def acquire_lock(self, resource: str, agent: str, timeout: int = 30) -> bool:
        """Acquire distributed lock on resource."""
```

### Success Metrics:
- Event delivery latency < 100ms
- Request/response round-trip < 500ms
- 99.9% message delivery reliability
- Support for 50+ concurrent agents

---

## Sub-Issue 4: Proactive Health Monitoring & Auto-Recovery

**Title:** Implement agent health checks with automatic recovery mechanisms

**Problem:**
Agents can hang, crash, or become unresponsive with no detection. There's no automatic recovery. Humans must manually identify and restart failed agents.

**Solution:**
Create a comprehensive health monitoring system with self-healing capabilities:

### Core Features:
1. **Health Check System**
   - Periodic heartbeat via user variables
   - Timeout detection (no activity for N seconds)
   - Pattern-based health (look for "Agent ready", error patterns)
   - Resource monitoring (if measurable)

2. **Failure Detection**
   - **Hang Detection**: No output for configured timeout
   - **Crash Detection**: Session termination monitor
   - **Error Loop Detection**: Repeated errors in short time
   - **Performance Degradation**: Response time trending up

3. **Automatic Recovery Actions**
   - **Level 1**: Send wake-up signal (Ctrl+C)
   - **Level 2**: Restart agent in same session
   - **Level 3**: Create new session, migrate work
   - **Level 4**: Alert human intervention needed

4. **Circuit Breaker Pattern**
   - Track failure rates per agent/team
   - Open circuit after threshold failures
   - Prevent cascading failures
   - Half-open state for recovery attempts

5. **Graceful Degradation**
   - Reassign tasks from failed agents
   - Reduce load on struggling agents
   - Maintain critical path coverage

6. **Health Dashboard**
   - Dedicated monitor pane showing all agent health
   - Historical failure data
   - Recovery action log
   - Alert summary

### iTerm2 APIs to Use:
- `iterm2.SessionTerminationMonitor` - Detect crashes
- `session.get_screen_streamer()` - Monitor for activity
- `iterm2.PromptMonitor` - Track command execution
- `session.async_send_text()` - Send recovery commands
- `session.async_set_variable("user.health")` - Store health state
- `iterm2.Alert` - Notify on critical failures

### Technical Approach:
```python
class AgentHealthMonitor:
    """Monitors agent health and triggers recovery."""
    
    def __init__(self, recovery_policy: RecoveryPolicy):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.failure_counts: Dict[str, int] = {}
        
    async def monitor_agent_health(self, session: ItermSession):
        """Continuous health monitoring."""
        last_activity = time.time()
        
        async with session.get_screen_streamer() as streamer:
            while True:
                try:
                    await asyncio.wait_for(
                        streamer.async_get(),
                        timeout=self.heartbeat_interval
                    )
                    last_activity = time.time()
                except asyncio.TimeoutError:
                    if time.time() - last_activity > self.hang_timeout:
                        await self._initiate_recovery(session)
    
    async def _initiate_recovery(self, session: ItermSession):
        """Execute recovery strategy based on failure severity."""
        severity = self._assess_failure(session)
        
        if severity == FailureSeverity.HANG:
            # Try Ctrl+C first
            await session.send_control_character("c")
            await asyncio.sleep(5)
            if not await self._check_responsive(session):
                # Escalate to restart
                await self._restart_agent(session)

class CircuitBreaker:
    """Prevent cascading failures."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.state: Dict[str, CircuitState] = {}
        
    async def call(self, agent: str, operation: Callable):
        """Execute operation through circuit breaker."""
        if self.state.get(agent) == CircuitState.OPEN:
            raise CircuitOpenError(f"Circuit open for {agent}")
        
        try:
            result = await operation()
            self._record_success(agent)
            return result
        except Exception as e:
            self._record_failure(agent)
            raise
```

### Success Metrics:
- Detect agent failures within 30 seconds
- 80% of hangs recovered automatically
- < 1 minute mean time to recovery (MTTR)
- Zero undetected silent failures

---

## Sub-Issue 5: Executive Agent Interface & Human-in-the-Loop

**Title:** Create intuitive executive agent interface with seamless human collaboration

**Problem:**
There's no designated executive agent role. Humans can't easily switch between working with an executive assistant and messaging individual agents. No clear handoff between AI autonomy and human control.

**Solution:**
Design a sophisticated executive agent system with natural human interaction:

### Core Features:
1. **Executive Agent Role**
   - Dedicated pane (prominent position, distinct color)
   - Manages all other agents through delegation
   - Maintains global context and state
   - Routes human requests to appropriate agents

2. **Dual Interaction Modes**
   - **Executive Mode** (default): Human ↔ Executive ↔ Team
   - **Direct Mode**: Human ↔ Specific Agent (bypass executive)
   - Easy mode switching via keyboard shortcuts or commands
   - Visual indicator of current mode

3. **Natural Delegation**
   - Executive parses human intent
   - Routes tasks to competent agents
   - Aggregates results from multiple agents
   - Presents unified response to human

4. **Focus-Based Routing**
   - `FocusMonitor` tracks which pane human is viewing
   - Auto-route messages to focused agent
   - Executive monitors all panes for urgent issues
   - "Take control" feature for executive to jump in

5. **Handoff Protocol**
   - Clear handoff from human → executive → agent
   - Agents request human approval when needed
   - Executive summarizes for human review
   - Approval/rejection workflow

6. **Broadcast Domains**
   - Use `iterm2.broadcast.BroadcastDomain` for team-wide commands
   - Executive can broadcast to all or subset
   - Selective broadcast with agent filters

### iTerm2 APIs to Use:
- `iterm2.FocusMonitor` - Track human attention
- `iterm2.broadcast.BroadcastDomain` - Team broadcasts
- `session.async_send_text(suppress_broadcast=True)` - Private messages
- `LocalWriteOnlyProfile` with distinct colors for executive
- Custom keyboard bindings via profiles

### Technical Approach:
```python
class ExecutiveAgent:
    """Manages team of agents and interfaces with human."""
    
    def __init__(
        self,
        session: ItermSession,
        agent_registry: AgentRegistry,
        event_bus: AgentEventBus
    ):
        self.session = session
        self.context = GlobalContext()
        
    async def handle_human_request(self, request: str) -> str:
        """Parse, delegate, aggregate, respond."""
        # Parse intent
        intent = await self._parse_intent(request)
        
        # Delegate to agents
        if intent.requires_multiple_agents:
            results = await self._parallel_delegation(intent)
        else:
            results = await self._single_delegation(intent)
        
        # Aggregate and respond
        response = await self._synthesize_response(results)
        return response
    
    async def _parallel_delegation(self, intent: Intent) -> List[Result]:
        """Delegate to multiple agents in parallel."""
        tasks = []
        for agent_name in intent.required_agents:
            task = self.event_bus.send_request(
                agent_name,
                intent.to_agent_task()
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)

class HumanInteractionManager:
    """Manages human interaction modes."""
    
    def __init__(self, focus_monitor: iterm2.FocusMonitor):
        self.mode = InteractionMode.EXECUTIVE
        self.focused_agent: Optional[str] = None
        
    async def monitor_focus(self):
        """Track which agent pane human is focused on."""
        async with self.focus_monitor as mon:
            while True:
                update = await mon.async_get_next_update()
                if update.active_session_changed:
                    await self._handle_focus_change(
                        update.active_session_changed.session_id
                    )
```

### Success Metrics:
- < 2 seconds for executive to delegate tasks
- 95% of requests routed to correct agent
- Human can override/intervene at any time
- Clear visual distinction between modes

---

## Sub-Issue 6: Advanced Observability & Debug Infrastructure

**Title:** Implement comprehensive observability using iTerm2's rendering and monitoring capabilities

**Problem:**
Debugging multi-agent workflows is difficult. No trace of who did what when. No way to replay scenarios. Limited visibility into agent decision-making.

**Solution:**
Build a production-grade observability platform:

### Core Features:
1. **Distributed Tracing**
   - Trace ID propagation across agents
   - Parent/child relationship tracking
   - Span visualization in dedicated pane
   - OpenTelemetry compatibility

2. **Structured Logging**
   - JSON logs with agent ID, timestamp, context
   - Log aggregation across all agents
   - Search/filter capabilities
   - Real-time log streaming to monitor pane

3. **Audit Trail**
   - Every command sent to every agent
   - All inter-agent messages
   - Human interventions
   - State changes with before/after snapshots

4. **Replay Capability**
   - Record all terminal output
   - Replay sessions for debugging
   - Step through agent interactions
   - Diff tool for comparing runs

5. **Performance Metrics**
   - Agent response times
   - Message queue depths
   - Command execution histograms
   - Resource utilization (where measurable)

6. **Debug Pane**
   - Dedicated pane showing real-time metrics
   - Visualization of agent state machine
   - Message flow diagram
   - Error log with stack traces

### iTerm2 APIs to Use:
- `session.async_get_contents()` - Capture full history
- `session.get_screen_streamer()` - Real-time monitoring
- `iterm2.Transaction` - Atomic snapshots
- Custom status bar components for metrics
- Triggers for error pattern detection

### Technical Approach:
```python
class ObservabilityPlatform:
    """Comprehensive observability for multi-agent system."""
    
    def __init__(self, log_dir: Path):
        self.tracer = DistributedTracer()
        self.log_aggregator = LogAggregator()
        self.audit_trail = AuditTrail(log_dir)
        
    async def trace_agent_action(
        self,
        agent: str,
        action: str,
        parent_trace_id: Optional[str] = None
    ):
        """Create trace span for agent action."""
        span = self.tracer.start_span(
            name=f"{agent}.{action}",
            parent_id=parent_trace_id
        )
        
        try:
            yield span
        finally:
            span.finish()
            await self.audit_trail.record(span)

class DebugVisualization:
    """Real-time debug visualization in dedicated pane."""
    
    async def render_agent_state_machine(self, agents: List[Agent]):
        """ASCII art state machine diagram."""
        
    async def render_message_flow(self, last_n_messages: int = 20):
        """Show message flow between agents."""
        
    async def render_performance_dashboard(self):
        """Real-time metrics dashboard."""
```

### Success Metrics:
- 100% action traceability
- < 1MB log overhead per hour of operation
- Replay accuracy: exact terminal state reproduction
- Debug time reduced by 50%

---

## Sub-Issue 7: Security & Isolation Hardening

**Title:** Implement security boundaries and audit controls for multi-agent orchestration

**Problem:**
Agents share terminal context with no isolation. No access controls. No audit of privileged operations. Potential for agents to interfere with each other.

**Solution:**
Implement defense-in-depth security:

### Core Features:
1. **Agent Sandboxing**
   - Each agent in separate iTerm session (already done)
   - Buried sessions for background workers (invisible to UI)
   - Prevent agents from accessing other agents' sessions
   - Resource quotas if measurable

2. **Access Control**
   - Role-based permissions (exec, coordinator, worker)
   - Operation allowlists per agent type
   - Approval required for privileged operations
   - Human-in-the-loop for sensitive actions

3. **Audit Logging**
   - Cryptographic signatures on audit logs
   - Tamper-evident log chain
   - Log all privileged operations
   - Immutable audit trail

4. **Secrets Management**
   - Never log secrets to terminal
   - Redaction patterns for sensitive data
   - Encrypted storage for credentials
   - Secret rotation support

5. **Input Validation**
   - Sanitize all agent inputs
   - Command injection prevention
   - Shell escape validation
   - Regex for dangerous patterns

6. **Rate Limiting**
   - Prevent agent command flooding
   - Throttle message broadcast
   - Circuit breaker for misbehaving agents

### iTerm2 APIs to Use:
- `session.async_set_buried(True)` - Hide background workers
- `app.buried_sessions` - Access hidden sessions
- Base64 encoding for safe command execution (already implemented)

### Technical Approach:
```python
class SecurityManager:
    """Enforces security policies for agent operations."""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self.audit_log = AuditLog()
        self.rate_limiters: Dict[str, RateLimiter] = {}
        
    async def authorize_operation(
        self,
        agent: str,
        operation: str,
        params: dict
    ) -> bool:
        """Check if agent is authorized for operation."""
        role = self._get_agent_role(agent)
        
        if not self.policy.is_allowed(role, operation):
            await self.audit_log.record_denial(agent, operation, params)
            return False
        
        if self.policy.requires_approval(role, operation):
            approved = await self._request_human_approval(agent, operation)
            await self.audit_log.record_approval(agent, operation, approved)
            return approved
        
        return True
    
    async def sanitize_command(self, command: str) -> str:
        """Sanitize command for safe execution."""
        # Remove dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                raise SecurityViolation(f"Dangerous pattern: {pattern}")
        
        # Escape special characters
        return shlex.quote(command)
```

### Success Metrics:
- Zero unauthorized operations
- 100% audit coverage of privileged operations
- No secrets leaked to logs or terminal
- Rate limiting prevents DoS

---

## Implementation Roadmap

### Phase 1: Visual Foundation (Weeks 1-2)
- Sub-Issue 1: Visual Hierarchy & Dynamic Layouts
- Sub-Issue 2: Real-Time Visual Status System

**Deliverables:**
- Hierarchical layout engine
- Color-coded agent states
- Dynamic badges and status bars

### Phase 2: Communication & Coordination (Weeks 3-4)
- Sub-Issue 3: Structured Inter-Agent Communication
- Sub-Issue 5: Executive Agent Interface

**Deliverables:**
- Event bus with pub/sub
- Coordination primitives
- Executive agent delegation

### Phase 3: Reliability & Operations (Weeks 5-6)
- Sub-Issue 4: Health Monitoring & Auto-Recovery
- Sub-Issue 6: Advanced Observability

**Deliverables:**
- Health checks with auto-recovery
- Distributed tracing
- Debug visualization

### Phase 4: Hardening (Week 7)
- Sub-Issue 7: Security & Isolation
- Integration testing
- Performance optimization

**Deliverables:**
- Security boundaries
- Audit logging
- Load testing results

## Success Criteria

### Functional Requirements
- ✅ Visual hierarchy automatically reflects team structure
- ✅ Agent states visible at a glance through colors/badges
- ✅ Inter-agent communication latency < 100ms
- ✅ Health monitoring detects failures within 30 seconds
- ✅ Executive agent can delegate to any team member
- ✅ Complete audit trail of all operations
- ✅ Security policies enforced for all agents

### Non-Functional Requirements
- **Performance**: Support 50+ concurrent agents
- **Reliability**: 99.9% uptime for coordination services
- **Scalability**: Linear scaling up to 100 agents
- **Usability**: < 5 second learning curve for basic operations
- **Maintainability**: < 1 hour to add new agent type

### Technical Requirements
- 90%+ test coverage for new code
- Zero regressions in existing functionality
- API documentation for all public interfaces
- Example implementations for each feature

## Dependencies & Prerequisites

### External Dependencies
- iTerm2 3.5+ (for latest API features)
- Python 3.10+ (for modern async features)
- macOS (iTerm2 requirement)

### Internal Dependencies
- Current gRPC infrastructure remains
- Agent registry enhanced, not replaced
- Backward compatibility maintained

### Team Skills
- Deep iTerm2 API knowledge
- Async Python expertise
- Multi-agent systems experience
- UI/UX design for terminal interfaces

## Risks & Mitigations

### Risk 1: iTerm2 API Limitations
**Mitigation:** Prototype each feature first, have fallback approaches

### Risk 2: Performance at Scale
**Mitigation:** Early load testing, optimization budget in timeline

### Risk 3: Complexity Creep
**Mitigation:** Strict scope control, MVP per sub-issue, iterative releases

### Risk 4: Backward Compatibility
**Mitigation:** Feature flags, gradual rollout, deprecation notices

## Open Questions

1. Should we support Warp, Alacritty, or other terminals?
   - **Recommendation:** Start iTerm2-only, design for portability

2. How to handle 100+ agents on single screen?
   - **Recommendation:** Paging, filtering, multiple windows

3. Should executive be a privileged MCP client or just another agent?
   - **Recommendation:** Privileged with special capabilities

4. What's the ideal default team color scheme?
   - **Recommendation:** User-configurable, provide 3 presets

## Conclusion

This epic transforms iTerm MCP from a functional multi-agent orchestrator into an intuitive, visual, and robust platform for coordinating complex AI teams. By leveraging iTerm2's rich API—colors, badges, monitors, events—we create a terminal that's not just a command interface but a living organizational chart.

The proposed sub-issues are designed to be:
- **Independent**: Each can be developed in parallel
- **Incremental**: Each adds value on its own
- **Testable**: Clear success criteria and metrics
- **Bounded**: Realistic scope for 1-2 week sprints

Together, they deliver a platform where humans can seamlessly work with an executive agent assistant, who coordinates teams of specialized agents, all represented in an intuitive visual hierarchy within the terminal itself.

**Next Steps:**
1. Review and refine this proposal with stakeholders
2. Prioritize sub-issues based on business value
3. Create detailed sub-issue tickets
4. Begin Phase 1 implementation
