# iTerm MCP

A Python implementation for controlling iTerm2 terminal sessions with support for multiple panes and layouts. This implementation uses the iTerm2 Python API for improved reliability and functionality.

## Features

- Named terminal sessions with persistent identity
- Multiple pane layouts (single, horizontal split, vertical split, quad, etc.)
- Command execution and output capture
- Real-time session monitoring with callback support
- Log management with filterable output using regex patterns
- Live output snapshots for LLM access
- Multiple session creation and parallel command execution
- Background process execution and status tracking
- Control character support (Ctrl+C, etc.)

## Requirements

- Python 3.7+
- iTerm2 3.3+ with Python API enabled

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

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
    ├── server/                   # Demo implementation
    │   ├── __init__.py
    │   └── main.py               # Main demo entry point
    └── utils/                    # Utility functions
        ├── __init__.py
        └── logging.py            # Logging utilities
```

## Usage

### Running the Demo

```bash
python -m iterm_mcp_python.server.main
```

This will:
1. Create a new window with a horizontal split layout
2. Send commands to both panes
3. Show the output from each pane
4. Demonstrate focus switching between panes

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
    await code_session.send_text("vim myfile.py\n")
    await terminal_session.send_text("python -m http.server\n")

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
    
    # Initialize terminal
    terminal = ItermTerminal(connection)
    await terminal.initialize()
    
    # Create multiple sessions with different commands
    session_configs = [
        {"name": "Server", "command": "python -m http.server", "monitor": True},
        {"name": "Logs", "command": "tail -f server.log", "layout": True, "vertical": True},
        {"name": "Client", "command": "curl localhost:8000", "layout": True, "vertical": False}
    ]
    
    session_map = await terminal.create_multiple_sessions(session_configs)
    
    # Get the Server session for monitoring
    server_session = await terminal.get_session_by_id(session_map["Server"])
    
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
        # Check snapshot for particular content
        if terminal.log_manager.get_snapshot(server_session.id):
            if "Keyboard interrupt received" in terminal.log_manager.get_snapshot(server_session.id):
                break

# Run the script
asyncio.run(my_advanced_script())
```

## Testing

Run the tests with:

```bash
python -m unittest discover tests
```

## Logging and Monitoring

All session activity is logged to `~/.iterm_logs` by default. This includes:
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

### Snapshots

Real-time snapshots of terminal output are maintained in snapshot files:
- Separate from main log files
- Always contain the latest output
- Available for LLM or other systems to access
- Useful for state monitoring without interfering with user interaction

## License

[MIT](LICENSE)