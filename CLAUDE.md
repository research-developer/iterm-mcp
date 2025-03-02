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

1. **Automated Recovery for WebSocket Disconnections**:
   - Implement automatic reconnection when connections are dropped
   - Add detection of closed WebSocket connections
   - Create session reacquisition after connection loss

2. **Persistent Session Management**:
   - Add ability to list available persistent sessions
   - Implement cleanup of old/inactive persistent sessions
   - Improve reconnection helpers for specific use cases

3. **Code Organization**:
   - Refactor common error handling patterns into utility functions
   - Extract WebSocket management logic for better testability
   - Standardize event notification patterns across modules

## Build & Test Commands
- Build: `cd fetch-mcp && npm run build` (runs TypeScript compiler)
- Watch mode: `cd fetch-mcp && npm run dev` (runs TypeScript in watch mode)
- Run tests: `cd fetch-mcp && npm test` (runs all Jest tests)
- Run single test: `cd fetch-mcp && npm test -- -t "test name pattern"` (run tests matching pattern)
- Start YouTube server: `cd youtube-mcp-server && npm run dev` (nodemon for development)
- Run iTerm tests: `cd iterm-mcp && python -m unittest discover tests` (run Python unittest tests)
- Run iTerm demo: `cd iterm-mcp && python -m iterm_mcp_python.server.main` (run demo script)

## Code Style Guidelines
- **TypeScript**: Use strict type checking with explicit return types
- **Imports**: Group imports by: external packages, internal modules, types
- **Error Handling**: Use try/catch blocks with detailed error messages and error propagation
- **Naming**: Use camelCase for variables/functions, PascalCase for classes/interfaces
- **Functions**: Prefer async/await over direct Promises, add proper error handling
- **Testing**: Use Jest with descriptive describe/it blocks and mock external dependencies
- **Documentation**: Add JSDoc comments for public APIs and complex functions
- **Formatting**: 2-space indentation, semicolons required, single quotes preferred

## Python Style Guidelines for iterm-mcp
- **Type Hints**: Always use type hints from the typing module
- **Documentation**: Use Google-style docstrings with Args: and Returns: sections
- **Async/Await**: Use async/await for all iTerm2 API calls
- **Error Handling**: Use try/except blocks with specific exceptions
- **Logging**: Use the logging module for all output and debugging
- **Testing**: Use unittest for test cases with descriptive method names

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

### Project Structure (Python Implementation)
```
iterm-mcp/
├── pyproject.toml                # Python packaging configuration
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_basic_functionality.py  # Basic feature tests
│   └── test_advanced_features.py    # Advanced feature tests
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
        └── logging.py            # Logging and monitoring utilities
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
pip install iterm-mcp

# Launch server
python -m iterm_mcp_python.server.main
```

### Claude Desktop Integration
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

### Development Commands
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run the server in development mode
python -m iterm_mcp_python.server.main

# MCP Protocol debugging
pip install modelcontextprotocol-inspector
python -m modelcontextprotocol_inspector iterm_mcp_python.server.main
```

## Recent Changes (March 2025)

### 1. MCP Server Stability Improvements
- Implemented robust error handling in all async functions with detailed logging
- Fixed WebSocket connection issues by improving error handling and adding proper shutdown procedures
- Changed screen monitoring from subscription-based to polling-based for better reliability
- Fixed parameter mismatch in create_layout function (session_names vs pane_names)
- Added attribute checking to prevent missing attribute errors

### 2. Code Robustness
- Added explicit checks with hasattr() before accessing potentially missing attributes
- Added fallback values for missing or failed operations
- Improved logging with more detailed information about errors and operations
- Added comprehensive try/except blocks to all critical functions

### 3. Testing Status
- Basic functionality tests are passing
- Advanced features tests still have 2 failures related to monitoring and filtering
- Next focus should be on fixing the race conditions in these tests and ensuring monitoring starts/stops correctly