# iTerm MCP

A Python implementation for controlling iTerm2 terminal sessions with support for multiple panes and layouts. This implementation uses the iTerm2 Python API for improved reliability and functionality.

## Features

- Named terminal sessions with persistent identity
- Multiple pane layouts (single, horizontal split, vertical split, quad, etc.)
- Command execution and output capture
- Session status monitoring
- Log management for sessions
- Background process execution
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

## Testing

Run the tests with:

```bash
python -m unittest discover tests
```

## Logging

All session activity is logged to `~/.iterm_logs` by default. This includes:
- Commands sent to sessions
- Output received from sessions
- Control characters sent
- Session lifecycle events (creation, renaming, closure)

## License

[MIT](LICENSE)