# iTerm MCP

A Model Context Protocol server that provides access to iTerm2 terminal sessions with support for multiple panes and layouts.

## Features

**Named Panes with Split Layouts:** Create and manage multiple terminal panes with descriptive names for different tasks. Choose from various predefined layouts (side-by-side, stacked, quad).

**Natural Integration:** Share iTerm with AI models. Models can inspect terminal output and execute commands while you monitor progress.

**Full Terminal Control:** Execute commands, read output, and send control characters (like Ctrl+C) to manage interactive sessions.

**Background Process Support:** Run commands asynchronously and check their status to monitor long-running processes.

**Session Persistence:** Named sessions maintain identity across operations, allowing models to reliably target specific terminal panes.

**Reliable Native API:** Uses the official iTerm2 Python API for maximum reliability and functionality.

<a href="https://glama.ai/mcp/servers/h89lr05ty6"><img width="380" height="200" src="https://glama.ai/mcp/servers/h89lr05ty6/badge" alt="iTerm Server MCP server" /></a>

## Safety Considerations

* The user is responsible for using the tool safely.
* No built-in restrictions: iterm-mcp makes no attempt to evaluate the safety of commands that are executed.
* Models can behave in unexpected ways. The user is expected to monitor activity and abort when appropriate.
* For multi-step tasks, you may need to interrupt the model if it goes off track. Start with smaller, focused tasks until you're familiar with how the model behaves.

## Available Tools

### Terminal Interaction
- `write_to_terminal` - Writes text or commands to a terminal session
- `read_terminal_output` - Reads the specified number of lines from a terminal session
- `send_control_character` - Sends a control character (e.g., Ctrl+C) to a terminal session

### Session Management
- `list_sessions` - Lists all available terminal sessions with their names and status
- `focus_session` - Makes a specific session active for user interaction
- `check_session_status` - Checks if a session is currently processing a command

### Layout Management
- `create_layout` - Creates a predefined layout with named panes (single, split, etc.)

## Requirements

* iTerm2 must be installed and running
* Python 3.8 or greater
* iTerm2 Python API enabled (Settings > General > Enable Python API)

## Installation

### Using pip

```bash
pip install iterm-mcp
```

### From source

```bash
git clone https://github.com/ferrislucas/iterm-mcp.git
cd iterm-mcp
pip install -e .
```

To use with Claude Desktop, add the server config:

On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "iterm-mcp": {
      "command": "iterm-mcp",
      "args": []
    }
  }
}
```

### Installing via Smithery

To install iTerm for Claude Desktop automatically via [Smithery](https://smithery.ai/server/iterm-mcp):

```bash
npx -y @smithery/cli install iterm-mcp --client claude
```
[![smithery badge](https://smithery.ai/badge/iterm-mcp)](https://smithery.ai/server/iterm-mcp)

## Development

Install development dependencies:
```bash
pip install -e ".[dev]"
```

Run the server:
```bash
python -m iterm_mcp_python.server.main
```

### Debugging

Standard Python debugging techniques can be used. Logs are written to `~/.iterm-mcp.log`.

For MCP protocol debugging, we recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
pip install modelcontextprotocol-inspector
python -m modelcontextprotocol_inspector iterm_mcp_python.server.main
```

The Inspector will provide a URL to access debugging tools in your browser.
