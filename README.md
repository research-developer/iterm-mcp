# iTerm MCP

A Python implementation for controlling iTerm2 terminal sessions with support for multiple panes and layouts. This implementation uses the iTerm2 Python API for improved reliability and functionality.

**Note:** This project provides multi-agent orchestration infrastructure, complementary to tools like [@steipete/claude-code-mcp](https://github.com/steipete/claude-code-mcp). See [docs/claude-code-mcp-analysis.md](docs/claude-code-mcp-analysis.md) for a detailed comparison.

## Features

- Named terminal sessions with persistent identity across restarts
- Persistent session IDs for reconnection after interruptions
- Multiple pane layouts (single, horizontal split, vertical split, quad, etc.)
- Command execution and output capture with configurable line limits
- Real-time session monitoring with callback support
- Log management with filterable output using regex patterns
- Live output snapshots for LLM access with overflow handling
- Multiple session creation and parallel command execution
- Background process execution and status tracking
- Control character support (Ctrl+C, etc.)

## Requirements

- Python 3.8+
- iTerm2 3.3+ with Python API enabled
- MCP Python SDK (1.3.0+)

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -e .
```

This will install the package with all required dependencies, including the MCP Python SDK.

## Project Structure

```
iterm-mcp/
├── pyproject.toml                # Python packaging configuration
└── iterm_mcp_python/             # Main package
    ├── __init__.py               # Package initialization
    ├── core/                     # Core functionality
    │   ├── __init__.py
    │   ├── session.py            # iTerm session management
    │   ├── terminal.py           # Terminal window/tab management
    │   └── layouts.py            # Predefined layouts
    ├── server/                   # Server implementations
    │   ├── __init__.py
    │   ├── main.py               # Entry point with option selection
    │   ├── mcp_server.py         # Legacy MCP server implementation
    │   └── fastmcp_server.py     # New FastMCP implementation
    └── utils/                    # Utility functions
        ├── __init__.py
        └── logging.py            # Logging utilities
```

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. Run tests:
   ```bash
   ./scripts/watch_tests.sh
   ```
4. Generate gRPC code (if modifying protos):
   ```bash
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/iterm_mcp.proto
   ```

## Usage
### MCP Integration with the Official Python SDK

We provide two server implementations:
1. **FastMCP Implementation** (recommended) - Uses the official MCP Python SDK
2. **Legacy Implementation** - Custom MCP server implementation (for backward compatibility)

### Running the MCP Server

```bash
# Run the FastMCP server (recommended)
python -m iterm_mcp_python.server.main

# Run the legacy MCP server
python -m iterm_mcp_python.server.main --legacy

# Run the demo (not MCP server)
python -m iterm_mcp_python.server.main --demo

# Enable debug logging
python -m iterm_mcp_python.server.main --debug
```

### Installing the MCP Server for Claude Desktop

We provide a script to install the server in Claude Desktop:

```bash
# Run the installation script
python install_claude_desktop.py
```

This will:
1. Register the server in Claude Desktop's configuration
2. Check if the server is already running
3. Offer to start the server if it's not running

**IMPORTANT**: You must have the server running in a separate terminal window while using it with Claude Desktop. The server won't start automatically when Claude Desktop launches.

To start the server manually:
```bash
python -m iterm_mcp_python.server.main
```

If you encounter connection errors in Claude Desktop, you can diagnose them with:
```bash
python install_claude_desktop.py --check-error "your error message"
```

### Debugging with MCP Inspector

For development and debugging, you can use the MCP Inspector:

```bash
mcp dev -m iterm_mcp_python.server.fastmcp_server
```

### Important Implementation Notes

1. **Process Termination**:  
   The server uses SIGKILL for termination to prevent hanging on exit. This ensures clean exit but bypasses Python's normal cleanup process. If you're developing and need proper cleanup, modify the signal handler in `main.py`.

2. **New FastMCP API**:  
   The FastMCP implementation uses the decorator-based API from the official MCP Python SDK. Tools are defined with `@mcp.tool()`, resources with `@mcp.resource()`, and prompts with `@mcp.prompt()`.

3. **Lifespan Management**:  
   The FastMCP implementation uses the lifespan API to properly initialize and clean up iTerm2 connections. The lifespan context provides access to the terminal, layout manager, and logger.

4. **WebSocket Handling**:  
   The FastMCP implementation uses the official SDK which properly handles WebSocket frames, fixing the "no close frame received or sent" error that previously occurred.

5. **Port Selection**:  
   The server uses port range 12340-12349 to avoid conflicts with common services. It automatically tries the next port in the range if one is busy.

### Using in Your Own Scripts

#### Basic Usage

```python
import asyncio
import iterm2
from iterm_mcp_python.core.terminal import ItermTerminal
from iterm_mcp_python.core.layouts import LayoutManager, LayoutType

async def my_script():
    # Connect to iTerm2
    connection = await iterm2.Connection.async_create()
    
    # Initialize terminal and layout manager
    terminal = ItermTerminal(connection)
    await terminal.initialize()
    layout_manager = LayoutManager(terminal)
    
    # Create a layout with named panes
    session_map = await layout_manager.create_layout(
        layout_type=LayoutType.HORIZONTAL_SPLIT,
        pane_names=["Code", "Terminal"]
    )
    
    # Get sessions by name
    code_session = await terminal.get_session_by_name("Code")
    terminal_session = await terminal.get_session_by_name("Terminal")
    
    # Send commands to sessions
    await code_session.send_text("vim myfile.py", execute=True)
    await terminal_session.send_text("python -m http.server", execute=True)
    
    # Type text without executing (for CLIs with prompts)
    await code_session.send_text("i", execute=False)  # Enter insert mode in vim
    await code_session.send_text("print('Hello, world!')", execute=False)
    await code_session.send_special_key("escape")  # Switch to command mode

# Run the script
asyncio.run(my_script())
```

#### Advanced Features

```python
import asyncio
import iterm2
from iterm_mcp_python.core.terminal import ItermTerminal

async def my_advanced_script():
    # Connect to iTerm2
    connection = await iterm2.Connection.async_create()
    
    # Initialize terminal with custom line limits
    terminal = ItermTerminal(
        connection=connection,
        default_max_lines=100,  # Default lines to retrieve per session
        max_snapshot_lines=1000  # Maximum lines to keep in snapshot
    )
    await terminal.initialize()
    
    # Create multiple sessions with different commands and line limits
    session_configs = [
        {
            "name": "Server", 
            "command": "python -m http.server", 
            "monitor": True,
            "max_lines": 200  # Custom line limit for this session
        },
        {
            "name": "Logs", 
            "command": "tail -f server.log", 
            "layout": True, 
            "vertical": True
        },
        {
            "name": "Client", 
            "command": "curl localhost:8000", 
            "layout": True, 
            "vertical": False
        }
    ]
    
    session_map = await terminal.create_multiple_sessions(session_configs)
    
    # Get the Server session for monitoring
    server_session = await terminal.get_session_by_id(session_map["Server"])
    
    # Store the persistent ID for future reconnection
    server_persistent_id = server_session.persistent_id
    print(f"Server session persistent ID: {server_persistent_id}")
    
    # Add real-time output handling
    async def handle_server_output(content):
        if "GET /" in content:
            # React to server events
            client_session = await terminal.get_session_by_id(session_map["Client"])
            await client_session.send_text("echo 'Detected a GET request!'\n")
    
    # Register the callback
    server_session.add_monitor_callback(handle_server_output)
    
    # Add output filtering to Logs session
    logs_session = await terminal.get_session_by_id(session_map["Logs"])
    logs_session.logger.add_output_filter(r"ERROR|WARN")  # Only capture errors and warnings
    
    # Wait for events
    while True:
        await asyncio.sleep(1)
        # Get snapshot with limited lines
        snapshot = terminal.log_manager.get_snapshot(
            server_session.id,
            max_lines=50  # Only get last 50 lines
        )
        if snapshot and "Keyboard interrupt received" in snapshot:
            break

    # Example of reconnecting by persistent ID in a new session
    async def reconnect_later():
        # Create a new terminal instance (simulating a new connection)
        new_connection = await iterm2.Connection.async_create()
        new_terminal = ItermTerminal(new_connection)
        await new_terminal.initialize()
        
        # Reconnect to server session using persistent ID
        reconnected_session = await new_terminal.get_session_by_persistent_id(server_persistent_id)
        if reconnected_session:
            print(f"Successfully reconnected to session: {reconnected_session.name}")
            # Continue working with the reconnected session
            await reconnected_session.send_text("echo 'Reconnected!'\n")

# Run the script
asyncio.run(my_advanced_script())
```

## MCP Tools and Resources

The FastMCP implementation provides the following:

### Tools
- `list_sessions` - List all available terminal sessions
- `focus_session` - Focus on a specific terminal session
- `create_layout` - Create a new terminal layout with named sessions
- `write_to_terminal` - Write a command to a terminal session (with option to type without executing)
- `read_terminal_output` - Read output from a terminal session
- `send_control_character` - Send a control character to a terminal session (Ctrl+C, Ctrl+D, etc.)
- `send_special_key` - Send a special key to a terminal session (Enter, Tab, Escape, Arrow keys, etc.)
- `check_session_status` - Check if a session is currently processing a command
- `get_session_by_persistent_id` - Get a session by its persistent ID
- `set_session_max_lines` - Set the maximum number of lines to retrieve for a session
- `start_monitoring_session` - Start real-time monitoring for a terminal session
- `stop_monitoring_session` - Stop real-time monitoring for a terminal session
- `list_persistent_sessions` - List all persistent sessions available for reconnection

### Resources
- `terminal://{session_id}/output` - Get the output from a terminal session
- `terminal://{session_id}/info` - Get information about a terminal session
- `terminal://sessions` - Get a list of all terminal sessions

### Prompts
- `monitor_terminal` - Prompt for monitoring a terminal session
- `execute_command` - Prompt for executing a command and analyzing the output

## Parallel Multi-Agent Orchestration

The iTerm MCP server supports coordinating multiple Claude Code instances through named agents, teams, and parallel session operations.

### Agent & Team Management

Agents bind a name to an iTerm session, enabling targeted communication. Teams group agents for broadcast operations.

```python
# Register agents
register_agent(name="alice", session_id="session-123", teams=["frontend"])
register_agent(name="bob", session_id="session-456", teams=["frontend", "backend"])

# Create teams
create_team(name="frontend", description="Frontend developers")
create_team(name="backend", description="Backend developers")

# List agents by team
list_agents(team="frontend")  # Returns alice and bob
```

### New MCP Tools for Parallel Operations

- `register_agent` - Register a named agent bound to a session
- `list_agents` - List all registered agents (optionally filtered by team)
- `remove_agent` - Remove an agent registration
- `create_team` - Create a new team for grouping agents
- `list_teams` - List all teams
- `remove_team` - Remove a team
- `assign_agent_to_team` - Add an agent to a team
- `remove_agent_from_team` - Remove an agent from a team
- `set_active_session` - Set active session by ID, name, or agent
- `write_to_sessions` - Write to multiple sessions in parallel
- `read_sessions` - Read from multiple sessions in parallel
- `create_sessions` - Create multiple sessions with layout in one call
- `send_cascade_message` - Send priority-based cascading messages

### Parallel Session Operations

Write to or read from multiple sessions simultaneously:

```python
# Write to multiple sessions by different targets
write_to_sessions(
    messages=[
        {"content": "npm test", "targets": [{"team": "frontend"}]},
        {"content": "cargo test", "targets": [{"agent": "rust-agent"}]},
        {"content": "echo hello", "targets": [{"name": "Session1"}, {"name": "Session2"}]}
    ],
    parallel=True,
    skip_duplicates=True
)

# Read from multiple sessions
read_sessions(
    targets=[
        {"agent": "alice", "max_lines": 50},
        {"team": "backend", "max_lines": 100}
    ],
    parallel=True,
    filter_pattern="ERROR|WARN"
)
```

### Cascading Messages

Send priority-based messages where the most specific wins:

```python
# Cascading priority: agent > team > broadcast
send_cascade_message(
    broadcast="All agents: sync your status",
    teams={
        "frontend": "Frontend team: run lint check",
        "backend": "Backend team: run database migrations"
    },
    agents={
        "alice": "Alice, please handle the API review specifically"
    },
    skip_duplicates=True
)
```

Resolution order:
1. If agent has a specific message → use it
2. Else if agent's team has a message → use team message
3. Else if broadcast exists → use broadcast
4. Messages are deduplicated to prevent sending the same content twice

### gRPC Client

For programmatic access outside MCP, use the gRPC client:

```python
from iterm_mcpy.grpc_client import ITermClient

# Using context manager
with ITermClient(host='localhost', port=50051) as client:
    # List sessions
    sessions = client.list_sessions()

    # Create sessions with layout
    response = client.create_sessions(
        sessions=[
            {"name": "Agent1", "agent": "alice", "team": "frontend"},
            {"name": "Agent2", "agent": "bob", "team": "backend"}
        ],
        layout="HORIZONTAL_SPLIT"
    )

    # Write to multiple sessions
    client.write_to_sessions(
        messages=[{"content": "echo hello", "targets": [{"team": "frontend"}]}],
        parallel=True
    )

    # Send cascade message
    client.send_cascade_message(
        broadcast="Status check",
        teams={"frontend": "Run tests"},
        agents={"alice": "Review PR #42"}
    )
```

### Data Persistence

Agents and teams are persisted to JSONL files in `~/.iterm_mcp_logs/`:
- `agents.jsonl` - Registered agents with session bindings
- `teams.jsonl` - Team definitions and hierarchies

## Testing

Run the tests with:

```bash
python -m unittest discover tests
```

## Logging and Monitoring

All session activity is logged to `~/.iterm_mcp_logs` by default. This includes:
- Commands sent to sessions
- Output received from sessions
- Control characters sent
- Session lifecycle events (creation, renaming, closure)

### Real-time Monitoring

Sessions can be monitored in real-time using the `start_monitoring()` method. This allows:
- Capturing output as it happens without polling
- Setting up custom callbacks for output processing
- Reacting to terminal events dynamically

### Output Filtering

Log output can be filtered using regex patterns:
- Only capture specific patterns like errors or warnings
- Reduce log noise for better analysis
- Multiple filters can be combined

### Snapshots and Line Management

Real-time snapshots of terminal output are maintained in snapshot files:
- Separate from main log files
- Always contain the latest output
- Available for LLM or other systems to access
- Useful for state monitoring without interfering with user interaction

Output line management:
- Configure global default line limits for all sessions
- Set per-session line limits via `set_max_lines()`
- Request specific line counts for individual operations
- Overflow files for tracking historic output beyond the line limit

### Persistent Session Management

Sessions maintain persistent identities across restarts and reconnection:
- Each session has a unique UUID-based persistent ID
- IDs are stored in `~/.iterm_mcp_logs/persistent_sessions.json`
- `get_session_by_persistent_id()` allows reconnection to existing sessions
- State is preserved even after chat or connection interruptions
- Session output history is available across reconnections

## Relationship to Claude Code MCP

This project provides **multi-agent orchestration infrastructure** that complements tools like [@steipete/claude-code-mcp](https://github.com/steipete/claude-code-mcp):

### Use Case Comparison

**@steipete/claude-code-mcp** - Direct code automation
- Wraps a single Claude Code CLI instance
- One-shot code execution with permission bypass
- Stateless operation
- Best for: Direct file/code manipulation by a single agent

**iterm-mcp** - Multi-agent coordination
- Orchestrates multiple Claude Code instances in iTerm sessions
- Agent registry with teams and hierarchies
- Persistent state management
- Best for: Coordinating parallel agents, complex workflows, team-based operations

### Integration Example

You can combine both tools:
1. Use iterm-mcp to create and manage multiple iTerm sessions
2. Run `@steipete/claude-code-mcp` in each session for code automation
3. Use iterm-mcp's agent/team tools to coordinate across sessions

```python
# Create sessions for different agents
create_sessions(
    layout_type="horizontal",
    session_configs=[
        {"name": "Frontend", "agent": "frontend-dev", "team": "dev"},
        {"name": "Backend", "agent": "backend-dev", "team": "dev"}
    ]
)

# Each session can run claude-code-mcp
write_to_terminal(session_id="...", content="npx -y @steipete/claude-code-mcp@latest")

# Coordinate across sessions
send_cascade_message(
    teams={"dev": "Run tests before deployment"}
)
```

For a detailed architectural comparison, see [docs/claude-code-mcp-analysis.md](docs/claude-code-mcp-analysis.md).

## License

[MIT](LICENSE)