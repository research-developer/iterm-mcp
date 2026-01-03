# Role-Based Session Specialization

This document describes the role-based session specialization feature, which enables fine-grained access control and tool filtering for terminal sessions.

## Overview

Role-based session specialization allows you to:
- Assign predefined roles to terminal sessions
- Control which tools are available to each session
- Define spawn and modification permissions
- Set session priorities for orchestration
- Create custom role configurations

## Available Roles

### Built-in Roles

| Role | Description | Priority | Can Spawn | Can Modify Roles |
|------|-------------|----------|-----------|------------------|
| `orchestrator` | Main orchestrating session that manages other agents | 1 (highest) | Yes | Yes |
| `devops` | DevOps and infrastructure tasks | 2 | No | No |
| `builder` | Code building and compilation | 2 | No | No |
| `debugger` | Debugging and troubleshooting | 2 | No | No |
| `researcher` | Research and information gathering | 3 | No | No |
| `tester` | Testing and quality assurance | 3 | No | No |
| `monitor` | Read-only monitoring and observation | 4 | No | No |
| `custom` | User-defined custom role | 3 | Configurable | Configurable |

### Role Details

#### Orchestrator
The orchestrator role has the highest priority (1) and full permissions. Use this for the main session that coordinates other agents.

**Capabilities:**
- Can spawn new agent sessions
- Can modify roles of other sessions
- Access to all orchestration tools
- Default commands: status checks, agent management

#### DevOps
For infrastructure and deployment tasks.

**Default Tools:** `docker`, `kubectl`, `terraform`, `ansible`, `aws`, `gcloud`, `az`
**Restricted Tools:** None by default

#### Builder
For compilation and build tasks.

**Default Tools:** `npm`, `yarn`, `pip`, `cargo`, `go`, `make`, `docker`, `git`
**Restricted Tools:** None by default

#### Debugger
For debugging and troubleshooting.

**Default Tools:** `gdb`, `lldb`, `strace`, `dtrace`, `tail`, `grep`, `awk`, `jq`
**Restricted Tools:** None by default

#### Researcher
For information gathering and research.

**Default Tools:** `curl`, `wget`, `git`, `grep`, `find`, `cat`, `less`
**Restricted Tools:** `rm`, `docker`, `kubectl`

#### Tester
For testing and QA.

**Default Tools:** `pytest`, `jest`, `mocha`, `cargo`, `go`, `npm`, `make`
**Restricted Tools:** None by default

#### Monitor
Monitoring role for system observation and diagnostics.

**Capabilities:**
- Can view session output and system logs
- Can run read-only monitoring commands (`tail`, `grep`, `ps`, `top`, `htop`)
- Has access to container/cluster inspection tools (`docker`, `kubectl`) for status checks
- Cannot run destructive commands (`rm`, `kill`, `pkill` are restricted)

## MCP Tools

### assign_session_role

Assign a role to a session.

```json
{
  "session_id": "ABC123",
  "role": "devops",
  "assigned_by": "orchestrator-agent"
}
```

### get_session_role

Get the role assignment for a session.

```json
{
  "session_id": "ABC123"
}
```

Returns:
```json
{
  "session_id": "ABC123",
  "has_role": true,
  "role": "devops",
  "description": "DevOps and infrastructure specialist",
  "can_spawn_agents": false,
  "can_modify_roles": false,
  "priority": 2,
  "assigned_at": "2025-01-03T12:00:00Z",
  "assigned_by": "orchestrator-agent"
}
```

### remove_session_role

Remove the role assignment from a session.

```json
{
  "session_id": "ABC123"
}
```

### list_session_roles

List all role assignments.

```json
{
  "role_filter": "devops"  // optional
}
```

### list_available_roles

List all available roles with their default configurations.

```json
{}
```

### check_tool_permission

Check if a tool is allowed for a session.

```json
{
  "session_id": "ABC123",
  "tool_name": "deploy"
}
```

Returns:
```json
{
  "session_id": "ABC123",
  "tool_name": "deploy",
  "allowed": true,
  "reason": null,
  "role": "devops",
  "has_role": true
}
```

### get_sessions_by_role

Get all sessions with a specific role.

```json
{
  "role": "tester"
}
```

## Python API

### RoleManager

The `RoleManager` class handles role assignments and permission checking.

```python
from core.roles import RoleManager, RolePermissionError
from core.models import SessionRole, RoleConfig

# Initialize
role_manager = RoleManager()

# Assign a role
assignment = role_manager.assign_role(
    session_id="session-123",
    role=SessionRole.DEVOPS,
    assigned_by="admin"
)

# Check permission
allowed, reason = role_manager.is_tool_allowed("session-123", "deploy")

# Check spawn capability
if role_manager.can_spawn_agents("session-123"):
    # Session can create new agents
    pass

# Get priority
priority = role_manager.get_priority("session-123")
```

### Custom Role Configuration

Create custom role configurations:

```python
from core.models import SessionRole, RoleConfig

custom_config = RoleConfig(
    role=SessionRole.CUSTOM,
    description="My custom role",
    available_tools=["tool1", "tool2", "tool3"],
    restricted_tools=["dangerous_tool"],
    default_commands=["echo 'Starting...'"],
    environment={"MY_VAR": "value"},
    can_spawn_agents=True,
    can_modify_roles=False,
    priority=2,
)

role_manager.assign_role(
    session_id="session-123",
    role=SessionRole.CUSTOM,
    role_config=custom_config,
)
```

### Agent Integration

Roles can also be assigned to agents:

```python
from core.agents import AgentRegistry
from core.models import SessionRole

registry = AgentRegistry()

# Register agent with role
agent = registry.register_agent(
    name="devops-agent",
    session_id="session-123",
    role=SessionRole.DEVOPS
)

# Check agent role
if agent.has_role(SessionRole.DEVOPS):
    # Agent is a DevOps specialist
    pass

# Get all agents with a role
devops_agents = registry.get_agents_by_role(SessionRole.DEVOPS)
```

## Tool Filtering Logic

When a role is assigned to a session, tools are filtered as follows:

1. **Restricted tools are always denied** - If a tool is in `restricted_tools`, it's blocked.

2. **Available tools whitelist** - If `available_tools` is non-empty, only tools in that list are allowed.

3. **Empty available_tools allows all** - If `available_tools` is empty, all non-restricted tools are allowed.

4. **No role allows all** - Sessions without a role have access to all tools.

## Persistence

Role assignments are persisted to `~/.iterm-mcp/roles.jsonl` and automatically loaded on startup. Custom role configurations are stored in `~/.iterm-mcp/role_configs.jsonl`.

## Best Practices

1. **Use orchestrator sparingly** - Only assign the orchestrator role to the main coordinating session.

2. **Principle of least privilege** - Assign the most restrictive role that allows the session to complete its tasks.

3. **Use custom roles for specific needs** - When built-in roles don't fit, create custom configurations.

4. **Monitor role assignments** - Use `list_session_roles` to audit current assignments.

5. **Clean up on session close** - Remove role assignments when sessions are closed.
