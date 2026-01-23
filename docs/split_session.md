# split_session Tool Documentation

## Overview

The `split_session` tool allows you to split an existing iTerm2 session in a specific direction (above/below/left/right), creating a new pane relative to the target session. This is a fundamental capability for dynamic session orchestration and building custom layouts.

## API Reference

### Tool Name
`split_session`

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `target` | SessionTarget | Yes | Target session to split (by session_id, agent name, or session name) |
| `direction` | string | Yes | Direction for the split: "above", "below", "left", or "right" |
| `name` | string | No | Name for the new session |
| `profile` | string | No | iTerm2 profile to use (defaults to "MCP Agent" if available) |
| `command` | string | No | Initial command to run in the new session |
| `agent` | string | No | Agent name to register for the new session |
| `agent_type` | string | No | AI agent CLI to launch: "claude", "gemini", "codex", or "copilot" |
| `team` | string | No | Team to assign the agent to |
| `monitor` | boolean | No | Start monitoring the new session (default: false) |
| `role` | string | No | Role for the session (e.g., "BUILDER", "DEBUGGER", "DEVOPS") |
| `role_config` | object | No | Custom role configuration |

### Response Format

```json
{
  "session_id": "w0t0p0:s123456",
  "name": "WorkerPane",
  "agent": "worker-1",
  "persistent_id": "persistent-12345",
  "source_session_id": "w0t0p0:s000000"
}
```

## Direction Mapping

The `direction` parameter maps to iTerm2's split pane API as follows:

| Direction | iTerm2 Parameters | Visual Result |
|-----------|-------------------|---------------|
| `above` | `vertical=False, before=True` | New pane appears above target |
| `below` | `vertical=False, before=False` | New pane appears below target |
| `left` | `vertical=True, before=True` | New pane appears to the left of target |
| `right` | `vertical=True, before=False` | New pane appears to the right of target |

## Usage Examples

### Basic Split

Split a session to create a pane below it:

```json
{
  "target": {"session_id": "w0t0p0:s123456"},
  "direction": "below",
  "name": "DebugPane"
}
```

### Split by Agent Name

Split an agent's session to the right:

```json
{
  "target": {"agent": "orchestrator"},
  "direction": "right",
  "name": "Worker1",
  "agent": "worker-1"
}
```

### Split with Command Execution

Split and immediately run a command:

```json
{
  "target": {"name": "MainSession"},
  "direction": "below",
  "name": "TestRunner",
  "command": "npm test"
}
```

### Split with Agent and Team

Create a worker agent in a team:

```json
{
  "target": {"agent": "orchestrator"},
  "direction": "right",
  "name": "Worker1",
  "agent": "worker-1",
  "team": "workers",
  "command": "python worker.py"
}
```

### Launch AI Agent CLI

Split and launch a Claude agent:

```json
{
  "target": {"session_id": "w0t0p0:s123456"},
  "direction": "below",
  "name": "ClaudeAgent",
  "agent": "claude-helper",
  "agent_type": "claude"
}
```

### Split with Role

Create a specialized session with a role:

```json
{
  "target": {"agent": "orchestrator"},
  "direction": "right",
  "name": "Builder",
  "agent": "builder-1",
  "role": "BUILDER"
}
```

## Use Cases

### 1. Orchestrator Spawning Workers

An orchestrator agent can dynamically create worker sessions as needed:

```json
{
  "target": {"agent": "orchestrator"},
  "direction": "right",
  "name": "Worker1",
  "agent": "worker-1",
  "team": "workers",
  "command": "python worker.py --task=build"
}
```

### 2. Debugging Workflows

Open a debug pane next to your main development session:

```json
{
  "target": {"name": "DevSession"},
  "direction": "below",
  "name": "Debugger",
  "command": "python -m pdb app.py"
}
```

### 3. Parallel Task Execution

Create multiple panes for parallel operations:

```json
// First split
{
  "target": {"session_id": "w0t0p0:s123456"},
  "direction": "right",
  "name": "Task1",
  "command": "npm run build"
}

// Second split
{
  "target": {"session_id": "w0t0p0:s123456"},
  "direction": "below",
  "name": "Task2",
  "command": "npm run test"
}
```

### 4. IDE-like Layouts

Build custom layouts by progressive splitting:

```json
// Start with a main session, then split to create:
// +----------+----------+
// |  Editor  |  Tests   |
// +----------+----------+
// |     Terminal        |
// +---------------------+

// Split 1: Create tests pane to the right
{
  "target": {"name": "Editor"},
  "direction": "right",
  "name": "Tests",
  "command": "npm test -- --watch"
}

// Split 2: Create terminal below editor
{
  "target": {"name": "Editor"},
  "direction": "below",
  "name": "Terminal"
}
```

## Error Handling

The tool will return an error if:

- Target session cannot be resolved
- Target resolves to multiple sessions (be more specific)
- Direction is invalid (must be: above, below, left, right)
- iTerm2 connection fails

Example error response:

```json
{
  "error": "Target session not found"
}
```

## Integration with Other Tools

### After Splitting

Once a session is split, you can use other MCP tools:

1. **write_to_sessions**: Send commands to the new session
2. **read_sessions**: Read output from the new session
3. **register_agent**: Register the session as an agent (if not done during split)
4. **manage_teams**: Add the agent to teams

### Progressive Layout Building

Combine multiple `split_session` calls to build complex layouts:

```python
# Pseudocode workflow
main_session = create_sessions({"name": "Main"})
right_session = split_session(main_session, "right", "Sidebar")
bottom_session = split_session(main_session, "below", "Terminal")
bottom_right = split_session(right_session, "below", "Logs")
```

## Best Practices

1. **Name Your Sessions**: Always provide descriptive names for easier management
2. **Use Agents for Organization**: Register agents to enable targeting by name
3. **Team Assignment**: Use teams to group related sessions
4. **Profile Management**: Use consistent profiles for similar session types
5. **Monitor Critical Sessions**: Enable monitoring for long-running operations

## Comparison with create_sessions

| Feature | split_session | create_sessions |
|---------|---------------|-----------------|
| Creates new window | No | Yes |
| Requires existing session | Yes | No |
| Layout flexibility | High (progressive) | Medium (predefined) |
| Agent registration | Yes | Yes |
| Direction control | Precise (4 directions) | Layout-based |
| Best for | Dynamic growth | Initial setup |

## Technical Details

### Implementation

The tool is implemented in three layers:

1. **Models** (`core/models.py`): Pydantic models for request/response validation
2. **Terminal API** (`core/terminal.py`): `split_session_directional()` method
3. **MCP Tool** (`iterm_mcpy/fastmcp_server.py`): Tool registration and orchestration

### Session Resolution

The `target` parameter supports three ways to identify a session:
- `session_id`: Direct iTerm2 session ID (most precise)
- `agent`: Agent name (requires prior registration)
- `name`: Session name (matches partial names)

### Profile and Color Management

If a team is specified:
1. A team profile is created/retrieved
2. The session's tab color is set to the team color
3. Profiles are automatically saved

## Troubleshooting

### "Target session not found"

- Verify the session exists: Use `list_sessions` to see all available sessions
- Check your target specification: Ensure session_id/agent/name is correct
- Session may have been closed: Recreate the session if needed

### "Target resolved to multiple sessions"

- Be more specific: Use `session_id` instead of `name` for exact matching
- Check for duplicate names: Use `list_sessions` to identify duplicates

### Split appears in wrong direction

- Double-check direction value: Must be exactly "above", "below", "left", or "right"
- Case sensitivity: Use lowercase for direction

### Profile not applied

- Verify profile exists: Use iTerm2's preferences to check available profiles
- Check logs: Look for warnings about profile application
- Use default profile: Omit `profile` parameter to use defaults

## See Also

- `create_sessions`: Create new windows with predefined layouts
- `write_to_sessions`: Send commands to sessions
- `read_sessions`: Read output from sessions
- `register_agent`: Register sessions as agents
- `manage_teams`: Manage agent teams
