# Agent Orchestration Guide

> **Internal Reference for LLM Agents**
> This document explains the iterm-mcp approach to multi-agent orchestration for AI agents participating in coordinated workflows.

## Executive Summary

**iterm-mcp** transforms iTerm2 into a visual command center for AI agent orchestration. Rather than running agents in isolation, this system enables:

- **Parallel agent execution** in named terminal sessions
- **Hierarchical team structures** with cascading communication
- **Manager-worker delegation** for complex multi-step tasks
- **Event-driven workflows** with reactive programming patterns
- **Shared memory** for cross-agent context and learning

The core philosophy: **the terminal is the organizational chart**. Each iTerm pane represents an agent, pane arrangements reflect team hierarchy, and visual cues (colors, badges) indicate agent state.

---

## Core Concepts

### 1. Sessions = Agent Workspaces

Every agent operates in an **iTerm session** - a persistent terminal workspace with:

- **Unique identity**: Name, ID, and persistent UUID (survives restarts)
- **Bidirectional I/O**: Send commands, capture output
- **Real-time monitoring**: Callbacks on output patterns
- **Visual state**: Colors, badges, tab indicators

```
┌─────────────────────────────────────────────────────┐
│ iTerm Window                                        │
├─────────────────┬───────────────────────────────────┤
│  CEO Agent      │      Team Lead Agent              │
│  (session-1)    │      (session-2)                  │
│  🟢 Online      │      🟡 Processing                │
├─────────────────┼───────────────────────────────────┤
│  Builder Agent  │      Tester Agent                 │
│  (session-3)    │      (session-4)                  │
│  🔵 Idle        │      🔴 Error                     │
└─────────────────┴───────────────────────────────────┘
```

### 2. Agents = Named Session Bindings

An **Agent** is a named entity bound to a session:

```python
# Registration creates the agent identity
register_agent(
    name="alice",           # Unique identifier
    session_id="session-1", # Bound iTerm session
    teams=["frontend"]      # Team memberships
)
```

**Key Properties:**
- Agents have names for human-readable targeting
- Multiple agents can form teams
- Messages can target by agent name, team name, or session ID
- Agent state persists to `~/.iterm-mcp/agents.jsonl`

### 3. Teams = Agent Groups with Hierarchy

**Teams** group related agents and support parent-child relationships:

```
Company (root team)
├── Engineering
│   ├── Frontend (team)
│   │   ├── alice (agent)
│   │   └── bob (agent)
│   └── Backend (team)
│       └── charlie (agent)
└── Operations
    └── devops (agent)
```

Teams enable:
- Broadcast messages to all team members
- Hierarchical cascading (parent team messages reach all children)
- Organizational structure that mirrors real teams

### 4. Cascading Messages = Priority-Based Dispatch

When sending messages, **the most specific wins**:

```
Priority Order:
1. Agent-specific message → delivered only to that agent
2. Team-specific message  → delivered to all team members
3. Broadcast message      → delivered to everyone

Example:
cascade = CascadingMessage(
    broadcast="Status check",                    # Everyone else
    teams={"frontend": "Run lint"},              # Frontend team
    agents={"alice": "Review PR #42"}            # Just alice
)

Resolution:
- alice gets: "Review PR #42"      (agent message)
- bob gets: "Run lint"             (team message, same team as alice)
- charlie gets: "Status check"     (broadcast, no specific message)
```

This pattern prevents message flooding while allowing targeted communication.

---

## Orchestration Patterns

### Pattern 1: Parallel Task Execution

Execute commands across multiple agents simultaneously:

```python
# Write to multiple sessions in parallel
write_to_sessions(
    messages=[
        {"content": "npm test", "targets": [{"team": "frontend"}]},
        {"content": "cargo test", "targets": [{"team": "backend"}]},
        {"content": "terraform plan", "targets": [{"agent": "devops"}]}
    ],
    parallel=True,        # All execute concurrently
    skip_duplicates=True  # Prevent double-sends
)

# Read results from multiple sessions
results = read_sessions(
    targets=[
        {"team": "frontend", "max_lines": 100},
        {"team": "backend", "max_lines": 100}
    ],
    parallel=True,
    filter_pattern="ERROR|FAIL"  # Only capture errors
)
```

**When to Use:**
- Running tests across multiple services
- Gathering status from all agents
- Parallel builds or deployments

### Pattern 2: Manager-Worker Delegation (Hierarchical Tasks)

For complex multi-step workflows, use **Manager Agents** to coordinate workers:

```python
# Create a manager with workers
manager = create_manager(
    name="build-orchestrator",
    workers=["builder", "tester", "deployer"],
    worker_roles={
        "builder": "builder",
        "tester": "tester",
        "deployer": "devops"
    },
    delegation_strategy="role_based"  # Match task to role
)

# Delegate a single task
result = delegate_task(
    manager="build-orchestrator",
    task="npm run build",
    role="builder",                    # Requires builder role
    validation="built successfully",   # Regex to validate success
    retry_count=2                      # Retry on failure
)

# Execute a multi-step plan
result = execute_plan(
    manager="build-orchestrator",
    plan={
        "name": "full-pipeline",
        "steps": [
            {"id": "build", "task": "npm run build", "role": "builder"},
            {"id": "test", "task": "npm test", "role": "tester",
             "depends_on": ["build"]},
            {"id": "deploy", "task": "npm run deploy", "role": "devops",
             "depends_on": ["test"]}
        ],
        "stop_on_failure": True
    }
)
```

**Delegation Strategies:**
| Strategy | Behavior |
|----------|----------|
| `role_based` | Match agent role to task requirements |
| `round_robin` | Rotate through available workers |
| `least_busy` | Assign to most idle agent |
| `priority` | Use pre-configured priority order |
| `random` | Random selection |

**When to Use:**
- Multi-stage pipelines (build → test → deploy)
- Tasks requiring specific expertise (debugging, testing)
- Workflows with dependencies between steps

### Pattern 3: Event-Driven Flows

React to terminal events with declarative handlers:

```python
# Define a flow with event handlers
class BuildDeployFlow(Flow):

    @start("build_requested")
    async def start_build(self, project: str):
        """Entry point - triggered by build_requested event"""
        result = await self.run_build(project)
        await trigger("build_complete", result)

    @listen("build_complete")
    async def on_complete(self, result):
        """React to build completion"""
        if result.success:
            await trigger("deploy_requested", result)
        else:
            await trigger("build_failed", result)

    @router("deploy_requested")
    async def route_deploy(self, result) -> str:
        """Dynamic routing based on content"""
        if result.environment == "production":
            return "production_deploy"
        return "staging_deploy"

    @on_output(r"ERROR: .*")
    async def on_error(self, text: str):
        """Pattern matching on terminal output"""
        await trigger("error_detected", {"error": text})

# Trigger the flow
trigger_workflow_event(
    event_name="build_requested",
    payload={"project": "my-app"},
    source="orchestrator"
)
```

**Decorator Types:**
| Decorator | Purpose |
|-----------|---------|
| `@start("event")` | Flow entry point |
| `@listen("event")` | React to event |
| `@router("event")` | Dynamic routing |
| `@on_output(pattern)` | Terminal output matching |

**When to Use:**
- Reactive workflows (error handling, notifications)
- Complex state machines
- Output-driven automation

### Pattern 4: Cross-Agent Memory

Share context between agents using the memory store:

```python
# Store memory with namespace and metadata
memory_store(
    namespace=["project-x", "build-agent"],
    key="last_build_output",
    value={"stdout": "...", "exit_code": 0},
    metadata={"type": "build", "timestamp": "..."}
)

# Retrieve specific memory
memory = memory_retrieve(
    namespace=["project-x", "build-agent"],
    key="last_build_output"
)

# Search across namespaces
results = memory_search(
    namespace=["project-x"],
    query="npm build errors",
    limit=10
)
```

**Namespace Convention:**
```
namespace = [project, agent, category]

Examples:
- ["project-x", "builder", "outputs"]
- ["project-x", "tester", "failures"]
- ["shared", "all", "config"]
```

**When to Use:**
- Sharing build artifacts between agents
- Learning from past failures
- Coordinating state across agents

### Pattern 5: Playbook Orchestration

Combine layout creation, commands, and messaging in a single request:

```python
orchestrate_playbook(
    playbook={
        # 1. Create sessions with layout
        "layout": {
            "sessions": [
                {"name": "Builder", "agent": "builder", "team": "dev"},
                {"name": "Tester", "agent": "tester", "team": "dev"}
            ],
            "layout": "HORIZONTAL_SPLIT"
        },

        # 2. Run command blocks
        "commands": [
            {
                "name": "setup",
                "messages": [
                    {"content": "npm install", "targets": [{"team": "dev"}]}
                ],
                "parallel": True
            }
        ],

        # 3. Send cascade after commands
        "cascade": {
            "broadcast": "Setup complete, starting work"
        },

        # 4. Read final state
        "reads": {
            "targets": [{"team": "dev"}],
            "parallel": True
        }
    }
)
```

**When to Use:**
- Setting up multi-agent workflows from scratch
- Reproducible orchestration patterns
- Self-contained workflow definitions

---

## Session Roles and Access Control

Sessions can have **roles** that define their capabilities:

| Role | Purpose | Allowed Tools |
|------|---------|---------------|
| `orchestrator` | Coordinate other agents | All tools |
| `builder` | Build/compile code | npm, pip, cargo, make, git, docker |
| `tester` | Run tests | pytest, jest, mocha, cargo test |
| `debugger` | Debug issues | gdb, lldb, strace, dtrace |
| `devops` | Infrastructure | docker, kubectl, terraform, aws |
| `researcher` | Investigate | curl, wget, grep, find |
| `monitor` | Observe only | tail, grep, ps (read-only) |

```python
# Assign role to session
assign_session_role(session_id="...", role="builder")

# Check if tool is allowed
can_use = check_tool_permission(session_id="...", tool_name="docker")
```

---

## Communication Patterns

### Direct Targeting

```python
# By session ID
write_to_sessions(messages=[
    {"content": "cmd", "targets": [{"session_id": "abc123"}]}
])

# By session name
write_to_sessions(messages=[
    {"content": "cmd", "targets": [{"name": "Builder"}]}
])

# By agent name
write_to_sessions(messages=[
    {"content": "cmd", "targets": [{"agent": "alice"}]}
])

# By team (all members)
write_to_sessions(messages=[
    {"content": "cmd", "targets": [{"team": "frontend"}]}
])
```

### Locking for Exclusive Access

```python
# Lock session for exclusive write access
lock_session(session_id="...", agent="alice")

# Other agents are blocked
lock_session(session_id="...", agent="bob")  # Returns locked=False

# Request access (politely)
request_session_access(session_id="...", agent="bob")

# Owner releases lock
unlock_session(session_id="...", agent="alice")
```

**When to Use:**
- Critical sections requiring exclusive access
- Long-running operations that shouldn't be interrupted
- Coordination between competing agents

---

## Visual Feedback

Sessions support visual customization for status indication:

```python
modify_sessions(
    modifications=[
        {
            "agent": "alice",
            "focus": True,                          # Bring to foreground
            "set_active": True,                     # Set as default target
            "tab_color": {"red": 0, "green": 255, "blue": 0},  # Green tab
            "badge": "BUILDING"                     # Status badge
        },
        {
            "agent": "bob",
            "background_color": {"red": 50, "green": 0, "blue": 0},  # Red bg
            "badge": "FAILED"
        }
    ]
)
```

**Visual Conventions:**
| Color | Meaning |
|-------|---------|
| Green tab | Success/Ready |
| Yellow tab | Processing |
| Red tab/bg | Error/Blocked |
| Blue tab | Idle |

---

## Best Practices for Agent Participants

### 1. Register on Startup

```python
# First action: register yourself
register_agent(
    name="my-agent-name",
    session_id=current_session_id,
    teams=["relevant-team"]
)
```

### 2. Use Cascading for Multi-Agent Messages

Don't send the same message to multiple agents individually. Use cascading:

```python
# GOOD: Single cascade request
send_cascade_message(
    teams={"dev": "Run tests"}
)

# BAD: Multiple individual sends (inefficient, can cause duplicates)
for agent in ["alice", "bob", "charlie"]:
    write_to_sessions(messages=[{"content": "Run tests", "targets": [{"agent": agent}]}])
```

### 3. Validate Task Results

Always use validation when delegating tasks:

```python
delegate_task(
    manager="orchestrator",
    task="npm run build",
    validation=r"built successfully|Build complete",  # Regex pattern
    retry_count=2
)
```

### 4. Use Memory for Shared Context

Don't repeat information in messages. Store shared context:

```python
# Store once
memory_store(
    namespace=["project", "shared"],
    key="build_config",
    value={"target": "production", "version": "1.2.3"}
)

# Reference in messages
"Build using config from memory://project/shared/build_config"
```

### 5. Clean Up on Exit

```python
# Unregister when done
remove_agent(agent_name="my-agent-name")

# Release any locks
unlock_session(session_id="...", agent="my-agent-name")
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client (Claude)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │ MCP Protocol
┌───────────────────────────▼─────────────────────────────────┐
│                    FastMCP Server                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ 40+ Tools   │ │ Resources   │ │ Prompts                 ││
│  └──────┬──────┘ └──────┬──────┘ └────────────┬────────────┘│
└─────────┼───────────────┼──────────────────────┼────────────┘
          │               │                      │
┌─────────▼───────────────▼──────────────────────▼────────────┐
│                  Core Orchestration Layer                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │ AgentRegistry    │  │ ManagerAgent     │  │ EventBus   │ │
│  │ - agents         │  │ - delegation     │  │ - flows    │ │
│  │ - teams          │  │ - validation     │  │ - triggers │ │
│  │ - cascading      │  │ - plans          │  │ - patterns │ │
│  └────────┬─────────┘  └────────┬─────────┘  └─────┬──────┘ │
│           │                     │                  │         │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌─────▼──────┐ │
│  │ RoleManager      │  │ MemoryStore      │  │ Checkpoint │ │
│  │ - permissions    │  │ - namespace      │  │ - persist  │ │
│  │ - tool filtering │  │ - search         │  │ - restore  │ │
│  └──────────────────┘  └──────────────────┘  └────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Session Layer                             │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ ItermSession     │  │ ItermTerminal    │                 │
│  │ - send_text      │  │ - create_session │                 │
│  │ - get_output     │  │ - parallel_ops   │                 │
│  │ - monitoring     │  │ - layouts        │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
└───────────┼─────────────────────┼───────────────────────────┘
            │                     │
┌───────────▼─────────────────────▼───────────────────────────┐
│                    iTerm2 Python API                         │
│              (WebSocket connection to iTerm2)                │
└─────────────────────────────────────────────────────────────┘
```

---

## Evolution & Design Philosophy

### Why This Architecture?

1. **iTerm as UI**: The terminal already exists; making it an agent dashboard reduces complexity

2. **Sessions as Isolation**: Each agent in its own session provides natural process isolation

3. **Cascading Over Broadcast**: Priority-based messaging prevents floods while enabling targeting

4. **Managers for Complexity**: Delegation pattern handles multi-step workflows cleanly

5. **Events for Reactivity**: Decorator-based flows enable complex state machines

### Inspirations

| Pattern | Inspiration |
|---------|-------------|
| Manager-Worker Delegation | CrewAI hierarchical teams |
| Event Flows | CrewAI Flows |
| Typed Messages | AutoGen message passing |
| Memory Store | LangGraph checkpointing |
| Role-Based Access | Enterprise RBAC patterns |

### What Makes This Different

Unlike single-agent frameworks, iterm-mcp:

- **Visualizes** agent state in terminal panes
- **Persists** across restarts (sessions, memory, state)
- **Scales** to many concurrent agents
- **Integrates** with existing CLI tools (git, npm, docker)
- **Complements** claude-code-mcp for code execution

---

## Quick Reference

### Essential Tools

| Tool | Purpose |
|------|---------|
| `list_sessions` | See all sessions/agents |
| `write_to_sessions` | Send commands |
| `read_sessions` | Capture output |
| `register_agent` | Create agent identity |
| `create_team` | Group agents |
| `send_cascade_message` | Priority-based messaging |
| `delegate_task` | Manager delegation |
| `memory_store` | Persist shared context |
| `trigger_workflow_event` | Start event flows |

### Data Locations

```
~/.iterm-mcp/
├── agents.jsonl      # Agent registry
├── teams.jsonl       # Team definitions
├── managers.jsonl    # Manager agents
├── messages.jsonl    # Message history
└── memory.db         # SQLite memory store
```

### Status Codes

| Level | Meaning |
|-------|---------|
| `info` | Normal operation |
| `warning` | Attention needed |
| `error` | Operation failed |
| `success` | Task completed |
| `blocked` | Waiting on dependency |

---

## Summary

The iterm-mcp orchestration system enables sophisticated multi-agent workflows through:

1. **Session-based agent workspaces** with visual feedback
2. **Hierarchical teams** with cascading communication
3. **Manager-worker delegation** for complex tasks
4. **Event-driven flows** for reactive automation
5. **Shared memory** for cross-agent coordination
6. **Role-based access control** for security

As an agent participant, you should:
- Register yourself on startup
- Use cascading for multi-agent messages
- Delegate complex tasks to managers
- Store shared context in memory
- Clean up on exit

The terminal is your organizational chart. Use it.
