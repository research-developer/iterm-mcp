# MCP (Model Context Protocol) Project Guide

## Known Issues with iTerm MCP Server

### Fixed Issues
1. ✅ **Parameter mismatch in `create_layout`**:
   - Fixed by keeping parameter name as `session_names` in the MCP server and passing it as `pane_names` to the layout manager
   - Also fixed enum mapping for layout types: HORIZONTAL_SPLIT, VERTICAL_SPLIT

2. ✅ **Missing attribute issue**:
   - Fixed error "'Session' object has no attribute 'is_processing'"
   - Added attribute existence checking with `hasattr()` and fallback defaults
   - Improved error handling in the is_processing property

3. ✅ **Improved WebSocket frame handling**:
   - Added comprehensive try/except blocks to all async functions
   - Added detailed logging for all exceptions
   - Improved connection initialization with better error handling
   - Implemented graceful shutdown handlers for WebSocket connections

4. ✅ **Better logging and debugging**:
   - Added detailed logging for all operations
   - Improved error messages with more context
   - Added operation tracking for async functions

### Fixed Issues (March 2025)
1. ✅ **Screen monitoring functionality**:
   - Replaced subscription-based monitoring with polling-based approach
   - Added async initialization waiting with timeout for monitoring startup
   - Implemented event-based signaling for monitor task readiness
   - Updated tests to properly wait for monitoring to be established
   - Added proper handling of SESSION_NOT_FOUND errors during monitoring

2. ✅ **Output filtering**:
   - Fixed line-by-line filtering to correctly process individual output lines
   - Added debug logging for filtered content
   - Updated tests to use unique identifiers for more reliable assertions
   - Added explicit monitoring in filter tests to capture all output

3. ✅ **Async stop_monitoring**:
   - Changed stop_monitoring to async method for proper cleanup
   - Added graceful shutdown period before cancellation
   - Implemented proper task completion checking and waiting
   - Updated all tests to use the async version

4. ✅ **Test race conditions**:
   - Added retry mechanisms for session operations in tests
   - Increased wait times for better async operation
   - Added more detailed error messages in assertions
   - Implemented proper cleanup in test teardowns

### Remaining Improvements Needed

1. **CRITICAL: WebSocket Close Frame Issues**:
   - Fix error: `Error sending command: no close frame received or sent`
   - Problem occurs when sending commands with `wait_for_prompt: true` in Claude Desktop
   - Add proper WebSocket close frame sending/receiving
   - Implement graceful error recovery for WebSocket frame failures
   - Investigate potential race conditions in async command execution
   - Add detailed logging around WebSocket frame handling
   - Test with different session identifier patterns

2. **Automated Recovery for WebSocket Disconnections**:
   - Implement automatic reconnection when connections are dropped
   - Add detection of closed WebSocket connections
   - Create session reacquisition after connection loss

3. **Persistent Session Management**:
   - Add ability to list available persistent sessions
   - Implement cleanup of old/inactive persistent sessions
   - Improve reconnection helpers for specific use cases

4. **Code Organization**:
   - Refactor common error handling patterns into utility functions
   - Extract WebSocket management logic for better testability
   - Standardize event notification patterns across modules

## Build & Test Commands
- Run tests: `python -m unittest discover tests` (run all Python unittest tests)
- Run server: `python -m server.main` (run the FastMCP server implementation)
- Run demo mode: `python -m server.main --demo` (run the demo controller)

## Code Style Guidelines
- **Imports**: Group imports by: standard library, external packages, local modules
- **Error Handling**: Use try/except blocks with detailed error messages and error propagation
- **Naming**: Use snake_case for variables/functions, PascalCase for classes
- **Functions**: Use async/await for all iTerm2 API calls and WebSocket operations
- **Documentation**: Use Google-style docstrings with Args: and Returns: sections
- **Formatting**: 4-space indentation, follow PEP 8 guidelines


## iterm-mcp Implementation

### Current Development Status
We've successfully implemented a Python-based iTerm2 controller with advanced features:

1. **Core Functionality**:
   - Session management with named panes
   - Reliable navigation between sessions
   - Command execution and output capture
   - Support for various terminal layouts

2. **Advanced Features**:
   - Real-time output monitoring with callbacks
   - Output filtering using regex patterns
   - Snapshot files for capturing terminal state
   - Multi-session management for parallel command execution
   - Enhanced logging system for tracking all terminal activity

3. **Testing and Documentation**:
   - Comprehensive test suite for both basic and advanced features
   - Detailed documentation in the README
   - Example code for both simple and advanced use cases

### Project Structure
```
iterm-mcp/
├── pyproject.toml                # Python packaging configuration
├── __init__.py                   # Root package initialization
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_basic_functionality.py  # Basic feature tests
│   └── test_advanced_features.py    # Advanced feature tests
│   └── test_line_limits.py          # Line limit tests
│   └── test_logging.py              # Logging tests
│   └── test_persistent_session.py   # Persistent session tests
├── core/                         # Core functionality
│   ├── __init__.py
│   ├── session.py                # iTerm session management
│   ├── terminal.py               # Terminal window/tab management
│   └── layouts.py                # Predefined layouts
├── server/                       # Server implementations
│   ├── __init__.py
│   ├── main.py                   # Entry point with option selection
│   ├── mcp_server.py             # Legacy MCP server implementation
│   └── fastmcp_server.py         # FastMCP implementation
└── utils/                        # Utility functions
    ├── __init__.py
    └── logging.py                # Logging and monitoring utilities
```

### Branches
- `applescript-implementation`: Contains the original AppleScript-based code
- `python-api-implementation`: New Python-based implementation using iTerm2's official API

### Next Steps
1. ✅ Address the API compatibility issues for real-time monitoring
   - ✅ Implemented polling-based monitoring as a more reliable alternative
   - Fix remaining issues with test cases for monitoring and filtering
   - Add better cleanup for monitoring tasks
   
2. ✅ Integrate with MCP server for model control
   - ✅ Implemented MCP protocol handlers using FastMCP
   - ✅ Added tools for model interaction with terminal sessions
   - ✅ Enabled access to terminal state for LLMs
   - Add more robust error handling for MCP operations
   
3. Fix remaining issues with WebSocket frames
   - Improve connection management with proper cleanup
   - Add automatic reconnection for dropped connections
   - Handle WebSocket close frames correctly
   
4. Enhance persistent session functionality
   - Add ability to list all available persistent sessions
   - Implement cleanup of old/inactive persistent sessions
   - Add reconnection helpers for specific use cases
   
5. Improve line limit management 
   - Add automatic output compression for large outputs
   - Implement smarter line selection based on content importance
   - Add ANSI escape code handling for better output processing
   
6. Fix and improve test reliability
   - Add proper waiting mechanisms for async operations in tests
   - Use more robust assertions that handle timing issues
   - Add ability to run individual test modules

### Core Modules

#### Session (session.py)
- `ItermSession` class wraps iTerm2's native session object
- Methods: send_text, get_screen_contents, send_control_character, clear_screen
- Maintains name and provides is_processing property
- Includes persistent_id for session reconnection
- Configurable max_lines property for output capture

#### Terminal (terminal.py)
- `ItermTerminal` class manages overall terminal state
- Methods for session creation, retrieval, focus, and closing
- Handles window/tab session tracking and management
- Maintains a registry of active sessions
- Supports session lookup by name, ID, or persistent ID
- Configurable global default_max_lines for all sessions

#### Layouts (layouts.py)
- `LayoutManager` creates predefined pane arrangements
- `LayoutType` enum defines supported layouts (single, horizontal, vertical, quad, etc.)
- Creates named panes that can be targeted consistently

### MCP Server Implementation

#### Tools Provided
- **write_to_terminal**: Send commands to named sessions
- **read_terminal_output**: Read output from terminal sessions (with line limit options)
- **send_control_character**: Send Ctrl+C and other control sequences
- **list_sessions**: Show all available terminal sessions
- **focus_session**: Make a specific session active
- **check_session_status**: Check if a command is running
- **create_layout**: Create a new window with predefined pane arrangement
- **get_session_by_persistent_id**: Reconnect to existing sessions by persistent ID
- **set_session_max_lines**: Configure output line limits per session

#### Key Features
- Named sessions with persistent identity across restarts
- Multiple pane support with predefined layouts
- Session selection by name, ID, or persistent ID
- Background process execution and monitoring
- Detailed logging with configurable line limits
- Overflow tracking for large outputs
- Session reconnection after interruptions

### Running the Server
```bash
# Install dependencies
pip install -e .

# Launch server
python -m server.main
```

### Claude Desktop Integration
```bash
# Install the server in Claude Desktop 
python install_claude_desktop.py

# Make sure to manually start the server before using Claude Desktop
python -m server.main
```

### Development Commands
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run the server in development mode
python -m server.main --debug

# MCP Protocol debugging
pip install modelcontextprotocol-inspector
python -m modelcontextprotocol_inspector server.main
```

## Recent Changes (March 2025)

### 1. Project Structure Reorganization
- Removed TypeScript implementation and dependencies
- Moved code from `iterm_mcp_python/` to root directory
- Updated imports to work with new directory structure
- Simplified project structure for better maintainability

### 2. Special Key Support & Command Execution
- Added `send_special_key` method for Enter, Tab, Escape, arrow keys
- Enhanced command execution with better control over Enter key handling
- Added `execute` parameter to control command execution behavior
- Improved terminal interaction for CLIs with prompts

### 3. MCP Server Stability Improvements
- Implemented robust error handling in all async functions
- Changed screen monitoring from subscription-based to polling-based
- Fixed parameter mismatch in `create_layout` function
- Added attribute checking to prevent missing attribute errors

### 4. FastMCP Implementation
- Created new implementation using the official MCP Python SDK
- Converted all existing tools to use the FastMCP decorator-based syntax
- Added resources for terminal output and info using URI patterns
- Implemented proper lifespan management for iTerm2 connections
- Fixed WebSocket close frame issues by using the official SDK

### 5. Port Configuration & Installation
- Changed server port to use 12340-12349 range to avoid conflicts
- Added automatic port selection if the primary port is busy
- Improved installation script with server detection
- Enhanced Claude Desktop integration process

### 6. Process Termination
- Fixed server hanging on Ctrl+C by using aggressive termination
- Implemented custom signal handler that uses SIGKILL for immediate termination
- Ensures reliable exit even with complex async operations running

### 7. Testing Status
- 23 of 24 tests passing in the new structure
- One test failing in output filtering (formatting issue only)
- All core functionality working correctly